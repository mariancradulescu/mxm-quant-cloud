"""Verify independently executed registered trial groups and retain exact monetary decimals."""
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
import argparse
from pathlib import Path

from .merge_eur_scenarios import exact_json, read, require


def collect(protocol_path, reports):
    plan = read(protocol_path)
    protocol_hash = sha256(protocol_path.read_bytes()).hexdigest()
    expected_groups = plan["TrialGroups"]
    expected_stresses = plan["Stresses"]
    trial_order = [x["Id"] for x in plan["Trials"]]
    require(len(reports) == len(expected_groups) * len(expected_stresses), "PARTITION_COUNT")
    prefix = None
    by_scenario = defaultdict(dict)
    for path in reports:
        report = read(path)
        summary = report["Summary"]
        require(summary["ProtocolSha256"] == protocol_hash and summary["Study"] == plan["Study"]
                and summary["EvidenceManifestSha256"] == plan["EvidenceManifestSha256"]
                and summary["InitialFitFrom"] == plan["InitialFitFrom"]
                and summary["TestBoundaries"] == plan["TestBoundaries"]
                and summary["DeclaredScenarioTrialCount"] == len(trial_order)*len(expected_stresses)
                and summary["Orders"] == summary["SourceBrokerRequests"] == 0
                and summary["CloudActivated"] is summary["IndependentConfirmationCertified"] is False
                and summary["DistilledWinnerForPromotion"] is report["BrokerFillEvidence"] is False
                and len(summary["Results"]) == 1, "PARTITION_PROTOCOL")
        result = summary["Results"][0]
        stress, group = result["SpreadMultiplier"], result["TrialGroup"]
        require(stress in expected_stresses and group in expected_groups and group not in by_scenario[stress]
                and result["CommissionAndDebitMultiplier"] == 1 + stress
                and [t["Id"] for t in result["Trials"]] == expected_groups[group]
                and [t["Id"] for t in result["TrialDetails"]] == expected_groups[group]
                and [f["AvailableBefore"] for f in result["Fits"]] == plan["TestBoundaries"][:-1]
                and all(t["Result"]["InitialCapitalEur"] == 300 for t in result["Trials"]), "PARTITION_TRIALS")
        header = dict(report, Summary={k: v for k, v in summary.items() if k != "Results"})
        if prefix is None:
            prefix = header
        require(prefix == header, "PARTITION_SOURCE")
        by_scenario[stress][group] = result

    def keyed(rows, key):
        unique = {}
        for row in rows:
            name = row[key]
            require(name not in unique or unique[name] == row, "PARTITION_SHARED_DIAGNOSTIC")
            unique[name] = row
        return list(unique.values())

    result = []
    for stress in expected_stresses:
        children = list(by_scenario[stress].values())
        require(set(by_scenario[stress]) == set(expected_groups), "PARTITION_MISSING_GROUP")
        first = children[0]
        require(all(r["Markets"] == first["Markets"] for r in children), "PARTITION_MARKET_CLOCKS")
        fits = [dict(AvailableBefore=clock,
            Models=keyed([m for r in children for m in r["Fits"][i]["Models"]], "Id"),
            EstimatorFits=keyed([m for r in children for m in r["Fits"][i]["EstimatorFits"]], "Id"))
            for i, clock in enumerate(plan["TestBoundaries"][:-1])]
        trials = {t["Id"]:t for r in children for t in r["Trials"]}
        details = {t["Id"]:t for r in children for t in r["TrialDetails"]}
        result.append(dict(SpreadMultiplier=stress, CommissionAndDebitMultiplier=1+stress,
            Fits=fits, Markets=first["Markets"], Trials=[trials[t] for t in trial_order],
            TrialDetails=[details[t] for t in trial_order],
            OpportunityObservations=keyed([o for r in children for o in r["OpportunityObservations"]], "Id"),
            CalibrationBooks=keyed([b for r in children for b in r["CalibrationBooks"]], "Id")))
    prefix["Summary"]["Results"] = result
    return prefix


def attribution(study, baseline, plan):
    original = baseline["Summary"]
    current = study["Summary"]
    require(original["ProtocolSha256"] == plan["ArchivedControl"]["ProtocolSha256"]
            and original["SourceSha256"] == current["SourceSha256"]
            and original["TestBoundaries"] == current["TestBoundaries"]
            and original["InitialFitFrom"] == current["InitialFitFrom"], "ARCHIVED_CONTROL_SOURCE")
    pairs = (
        ("LOCAL4_BROAD", "LOCAL_4_FEATURE_CONTROL"),
        ("EXTENDED_CONTEXT_BROAD_OBSERVER", "EXTENDED_CONTEXT"),
        ("ADAPTIVE_LOCAL_BROAD", "LOCAL4_BROAD"),
        ("ADAPTIVE_FULL_BROAD", "ADAPTIVE_LOCAL_BROAD"),
        ("ADAPTIVE_FULL_BROAD", "ADAPTIVE_FULL_NARROW"),
        ("ADAPTIVE_FULL_BROAD_ALLOCATION", "ADAPTIVE_FULL_BROAD"),
        ("ADAPTIVE_FULL_BROAD_MANAGEMENT", "ADAPTIVE_FULL_BROAD"),
        ("ADAPTIVE_FULL_BROAD_GEOMETRY", "ADAPTIVE_FULL_BROAD"),
        ("ADAPTIVE_FULL_BROAD_FEEDBACK", "ADAPTIVE_FULL_BROAD"),
    )
    def difference(a,b):
        return a-b if a is not None and b is not None else None

    def groups(result):
        total = result["Closed"]
        by_symbol_side = defaultdict(int)
        for episode in result["ByMarketFamily"]:
            by_symbol_side[(episode["Symbol"],episode["Side"])] += episode["Rounds"]
        if not by_symbol_side:
            return dict(TopSymbolSide=None, Share=None, Hhi=None)
        (symbol,side), largest=max(by_symbol_side.items(),key=lambda x:x[1])
        return dict(TopSymbolSide=[symbol,side,largest],Share=Decimal(largest)/total,
                    Hhi=sum(Decimal(n)**2 for n in by_symbol_side.values())/Decimal(total)**2)

    rows = []
    for scenario, earlier in zip(current["Results"], original["Results"], strict=True):
        require(scenario["SpreadMultiplier"] == earlier["SpreadMultiplier"], "ARCHIVED_STRESS")
        if "CASH_CONTROL" not in {t["Id"] for t in scenario["Trials"]}:
            raise ValueError("CASH_CONTROL_MISSING")
        trials = {t["Id"]:t["Result"] for t in earlier["Trials"]+scenario["Trials"]}
        for new, control in pairs:
            a,b=trials[new],trials[control]
            rows.append(dict(Stress=scenario["SpreadMultiplier"],Trial=new,Control=control,
                GrossDeltaEur=difference(a["ClosedGrossEur"],b["ClosedGrossEur"]),
                NetDeltaEur=difference(a["ClosedNetEur"],b["ClosedNetEur"]),
                RoundsDelta=a["Closed"]-b["Closed"], Concentration=groups(a), ControlConcentration=groups(b),
                TrialWeeks=[w["Rounds"] for w in a["Weeks"]],ControlWeeks=[w["Rounds"] for w in b["Weeks"]]))
    return dict(Study=plan["Study"], Archived=plan["ArchivedControl"], Scope="DEVELOPMENT_PAIRED_BOOK_COMPARISONS",
                Comparisons=rows)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("protocol",type=Path)
    parser.add_argument("baseline",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("reports",type=Path,nargs="+")
    args=parser.parse_args()
    study=collect(args.protocol,args.reports)
    plan=read(args.protocol)
    audit=attribution(study,read(args.baseline),plan)
    args.output.mkdir(exist_ok=False)
    for name,object_ in (("economic.json",study),("attribution.json",audit)):
        (args.output/name).write_text(exact_json(object_)+"\n")
    print("EUR_ADAPTIVE_TRIALS", study["Summary"]["DeclaredScenarioTrialCount"])
    for scenario in study["Summary"]["Results"]:
        for t in scenario["Trials"]:
            r=t["Result"]
            print(scenario["SpreadMultiplier"],t["Id"],r["Closed"],r["ClosedGrossEur"],r["ClosedNetEur"],
                  r["Hard21AllFullRegisteredWeeks"])


if __name__=="__main__":
    main()

"""Reconcile registered predictive trials and compare archived adaptive books."""
import argparse
from collections import defaultdict
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from .merge_eur_adaptive import collect
from .merge_eur_scenarios import read, require, exact_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("protocol",type=Path)
    parser.add_argument("baseline",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("reports",type=Path,nargs="+")
    args=parser.parse_args()
    plan=read(args.protocol)
    report=collect(args.protocol,args.reports)
    archived=read(args.baseline)["Summary"]
    current=report["Summary"]
    require(archived["Study"]==plan["ArchivedControl"]["Study"] and
            all(archived[k]==current[k] for k in ("SourceSha256","EvidenceManifestSha256","TestBoundaries","InitialFitFrom")),
            "PREDICTIVE_ARCHIVED_COMPARATOR_SOURCE")
    controls={
        "PREDICTIVE_LOSS_BROAD":"ADAPTIVE_FULL_BROAD",
        "PREDICTIVE_UTILITY_BROAD":"ADAPTIVE_FULL_BROAD",
        "PREDICTIVE_UTILITY_GEOMETRY":"ADAPTIVE_FULL_BROAD_GEOMETRY",
        "PREDICTIVE_UTILITY_GEOMETRY_FEEDBACK":"ADAPTIVE_FULL_BROAD_GEOMETRY",
    }
    def delta(a,b): return None if a is None or b is None else a-b
    comparisons=[]
    for scenario, prior in zip(current["Results"],archived["Results"],strict=True):
        require(scenario["SpreadMultiplier"]==prior["SpreadMultiplier"],"PREDICTIVE_STRESS")
        previous={t["Id"]:t["Result"] for t in prior["Trials"]}
        for t in scenario["Trials"]:
            result=t["Result"]
            control=previous[controls[t["Id"]]]
            comparisons.append(dict(Stress=scenario["SpreadMultiplier"],Trial=t["Id"],Control=controls[t["Id"]],
                GrossDeltaEur=delta(result["ClosedGrossEur"],control["ClosedGrossEur"]),
                NetDeltaEur=delta(result["ClosedNetEur"],control["ClosedNetEur"]),
                RoundsDelta=result["Closed"]-control["Closed"],
                GrossEur=result["ClosedGrossEur"],NetEur=result["ClosedNetEur"],
                Weeks=result["Weeks"],Hard21=result["Hard21AllFullRegisteredWeeks"],
                Drawdown=result["SampledDrawdown"],UnknownEquityClocks=result["UnknownEquityClocks"]))
            print(scenario["SpreadMultiplier"],t["Id"],result["Closed"],result["ClosedGrossEur"],
                  result["ClosedNetEur"],result["Hard21AllFullRegisteredWeeks"])
    args.output.mkdir(exist_ok=False)
    (args.output/"economic.json").write_text(exact_json(report)+"\n")
    (args.output/"attribution.json").write_text(exact_json(dict(Study=plan["Study"],
        ProtocolSha256=sha256(args.protocol.read_bytes()).hexdigest(),Archived=plan["ArchivedControl"],
        Scope="EXPOSED_DEVELOPMENT_NOT_INDEPENDENT",Comparisons=comparisons))+"\n")
    print("EUR_PREDICTIVE_TRIALS",current["DeclaredScenarioTrialCount"])


if __name__=="__main__":
    main()

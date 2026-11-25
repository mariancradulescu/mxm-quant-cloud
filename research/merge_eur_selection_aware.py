"""Exact decision-path attribution; identical execution cohorts are not causal randomization."""
import argparse
from itertools import combinations
from pathlib import Path
from .merge_eur_adaptive import collect
from .merge_eur_scenarios import exact_json, read, require


def net(rows):
    return None if any(x["NetEur"] is None for x in rows) else sum(x["NetEur"] for x in rows)


def stats(rows):
    return dict(Rounds=len(rows),GrossEur=sum(x["GrossEur"] for x in rows),NetEur=net(rows))


def closed(details):
    admissions={a["PositionId"]:a for a in details["Details"]["Admissions"]}
    episodes={}
    for e in details["Details"]["Episodes"]:
        key=(e["Symbol"],e["Family"],e["Side"],admissions[e["PositionId"]]["DecisionAt"])
        require(key not in episodes,"ATTRIBUTION_DUPLICATE_DECISION")
        episodes[key]=e
    return episodes


def path_attribution(summary, trial):
    by_stress=[]
    for s in summary["Results"]:
        detail=next(t for t in s["TrialDetails"] if t["Id"]==trial)
        result=next(t["Result"] for t in s["Trials"] if t["Id"]==trial)
        episodes=closed(detail)
        require(len(episodes)==result["Closed"] and net(list(episodes.values()))==result["ClosedNetEur"],
                "ATTRIBUTION_LEDGER_RECONCILIATION")
        fit=[]
        for fold in s["Fits"]:
            estimator=next((m["Fit"] for m in fold.get("EstimatorFits",[]) if m["Id"]==trial),None)
            fit.append(dict(AvailableBefore=fold["AvailableBefore"],Selected=estimator.get("Selected") if estimator else None))
        forecasts=[f for f in detail.get("Forecasts",[]) if f.get("RealizedNetEur") is not None]
        by_stress.append((s["SpreadMultiplier"],episodes,dict(Fits=fit,
            ClosedForecastCount=len(forecasts),
            EstimatedNetEur=sum(f["Payoff"]["NetMeanEur"] for f in forecasts),
            RealizedForecastNetEur=sum(f["RealizedNetEur"] for f in forecasts))))
    comparisons=[]
    for (a,left,lf),(b,right,rf) in combinations(by_stress,2):
        common=left.keys()&right.keys()
        # Strong match: same decision, volume, open/close timestamps and gross
        # outcome. Cost effect is an observed difference on matched paths only.
        matched=sorted(k for k in common if all(left[k][field]==right[k][field]
                       for field in ("Units","OpenAt","CloseAt","GrossEur")))
        same=set(matched)
        def subset(rows,keys): return [rows[k] for k in sorted(keys)]
        m1,m2=stats(subset(left,same)),stats(subset(right,same))
        comparisons.append(dict(StressA=a,StressB=b,CommonDecisions=len(common),
            MatchedExecutionA=m1,MatchedExecutionB=m2,
            MatchedNetDifferenceEur=None if m1["NetEur"] is None or m2["NetEur"] is None else m2["NetEur"]-m1["NetEur"],
            CommonChangedExecutionA=stats(subset(left,common-same)),
            CommonChangedExecutionB=stats(subset(right,common-same)),
            DistinctA=stats(subset(left,left.keys()-common)),DistinctB=stats(subset(right,right.keys()-common)),
            ForecastA=lf,ForecastB=rf))
    return dict(Study=summary["Study"],Trial=trial,Scope="OBSERVED_MATCHED_PATH_NOT_CAUSAL_COST_INTERVENTION",
                Comparisons=comparisons)


def main():
    p=argparse.ArgumentParser()
    p.add_argument("protocol",type=Path)
    p.add_argument("baseline",type=Path)
    p.add_argument("output",type=Path)
    p.add_argument("reports",type=Path,nargs="+")
    args=p.parse_args()
    plan=read(args.protocol)
    report=collect(args.protocol,args.reports)
    archived=read(args.baseline)["Summary"]
    current=report["Summary"]
    require(archived["Study"]==plan["ArchivedControl"]["Study"] and
            all(archived[k]==current[k] for k in ("SourceSha256","EvidenceManifestSha256","TestBoundaries","InitialFitFrom")),
            "SELECTION_AWARE_COMPARATOR_SOURCE")
    audit=[path_attribution(archived,"PREDICTIVE_UTILITY_GEOMETRY")]
    audit.extend(path_attribution(current,t["Id"]) for t in plan["Trials"])
    args.output.mkdir(exist_ok=False)
    (args.output/"economic.json").write_text(exact_json(report)+"\n")
    (args.output/"cross_cost_attribution.json").write_text(exact_json(audit)+"\n")
    for scenario in current["Results"]:
        for t in scenario["Trials"]:
            result=t["Result"]
            print(scenario["SpreadMultiplier"],t["Id"],result["Closed"],result["ClosedGrossEur"],
                  result["ClosedNetEur"],result["Hard21AllFullRegisteredWeeks"],result["SampledDrawdown"])
    print("EUR_SELECTION_AWARE_TRIALS",current["DeclaredScenarioTrialCount"])


if __name__=="__main__":
    main()

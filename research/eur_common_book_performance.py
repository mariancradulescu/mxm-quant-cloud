"""Exact performance summary for a registered common-book report; unknown NET stays unknown."""
from decimal import Decimal
from statistics import median
from collections import defaultdict
from pathlib import Path
from .merge_eur_scenarios import read, exact_json

def performance(result):
    rows=[]
    for scenario in result["Summary"]["Results"]:
        details={t["Id"]:t["Details"] for t in scenario["TrialDetails"]}
        for t in scenario["Trials"]:
            r=t["Result"]; d=details[t["Id"]]; weeks=r["Weeks"]
            net=r["ClosedNetEur"]; gross=r["ClosedGrossEur"]; capital=r["InitialCapitalEur"]
            wn=[w["NetEur"] for w in weeks]; complete=all(x is not None for x in wn)
            known=[x for x in wn if x is not None]
            terminal=r["AllTerminalNetEur"]
            path=d["EquityPath"]
            known_eq=[x["EquityEur"] for x in path if x["EquityEur"] is not None]
            # Margin-time efficiency is descriptive, not annualized.
            margin_samples=[x["UsedMarginEur"]+x["PendingMarginEur"] for x in path
                if x["EquityEur"] is not None and x["UsedMarginEur"] is not None and x["PendingMarginEur"] is not None]
            mean_margin=sum(margin_samples)/Decimal(len(margin_samples)) if margin_samples else None
            rows.append(dict(Stress=scenario["SpreadMultiplier"],Trial=t["Id"],Closed=r["Closed"],
                GrossEur=gross,NetEur=net,ClosedNetReturnPct=100*net/capital if net is not None else None,
                TerminalNetEur=terminal,TerminalReturnPct=100*terminal/capital if terminal is not None else None,
                RegisteredWeeks=len(weeks),WeeksWithKnownNet=len(known),WeeksWithUnknownNet=len(wn)-len(known),
                MeanWeeklyNetEur=sum(known)/Decimal(len(wn)) if complete and wn else None,
                MedianWeeklyNetEur=median(known) if complete and wn else None,
                WorstWeeklyNetEur=min(known) if complete and wn else None,
                ProfitableWeeks=sum(x>0 for x in known),ActiveWeeks=sum(w["Rounds"]>0 for w in weeks),
                NetPerRoundEur=net/Decimal(r["Closed"]) if net is not None and r["Closed"] else None,
                MeanSampledCommittedMarginEur=mean_margin,
                NetPerMeanCommittedMargin=net/mean_margin if net is not None and mean_margin else None,
                MeanSampledHeldPendingMarginFraction=r["MeanSampledHeldPendingMarginFraction"],
                SampledDrawdown=r["SampledDrawdown"],Hard21=r["Hard21AllFullRegisteredWeeks"],
                UnknownEquityClocks=r["UnknownEquityClocks"],UnknownFundingWindows=r["UnknownFundingWindows"],
                SampledMinimumEquityEur=min(known_eq,default=None),OpenPositions=r["OpenPositions"],
                TerminalObservedEquityEur=path[-1]["EquityEur"] if path else None,
                TerminalFloatingEur=(path[-1]["EquityEur"]-path[-1]["CashEur"]) if path and path[-1]["EquityEur"] is not None else None))
    grouped=defaultdict(list)
    for row in rows: grouped[row["Trial"]].append(row)
    robustness=[]
    for trial,rs in grouped.items():
        nets=[x["NetEur"] for x in rs]
        complete=all(x is not None for x in nets)
        robustness.append(dict(Trial=trial,ScenarioCount=len(rs),AllNetKnown=complete,
            WorstScenarioNetEur=min(nets) if complete else None,MeanScenarioNetEur=sum(nets)/Decimal(len(nets)) if complete else None,
            AllPositive=complete and all(x>0 for x in nets),AllHard21=all(x["Hard21"] for x in rs),
            MaxSampledDrawdown=max((x["SampledDrawdown"] for x in rs if x["SampledDrawdown"] is not None),default=None),
            AllEquityClocksKnown=all(x["UnknownEquityClocks"]==0 for x in rs),Promotion=False))
    return dict(Study=result["Summary"]["Study"],Scope="CONDITIONAL_DEVELOPMENT_NO_PROMOTION",Rows=rows,Robustness=robustness)

if __name__=="__main__":
    import sys
    out=Path(sys.argv[2])
    out.write_text(exact_json(performance(read(Path(sys.argv[1]))))+"\n")

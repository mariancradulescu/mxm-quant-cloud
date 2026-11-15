"""RDE1 protected ORIGINAL source replay, economic gate first; never broker orders.

Pure historical research. Uses original BDP1/AIP1 sealed source recoverers,
new RDE1 risk rules and original C#-extracted current-term contract cost
contexts. NO RDE1 policy is passed to a cash ledger in this stage; conditional
minimum-unit EUR values are unfunded and are never claimed as a EUR300 portfolio.
"""
from __future__ import annotations
import json
import os
from collections import Counter,defaultdict
from hashlib import sha256
from pathlib import Path
from statistics import mean
from .multiscale_conditional_research import recover,extract_costs
from .integrated_predictive_funded import cost_context
from .rde1_risk_distribution import (
    causal_clocks,realized_labels,fit_training,forecast,paired_weekly,
    mandatory_economic_gate,current_term_roundtrip_friction_bps,M5
)

PROTOCOL=Path("research/rde1_protocol.json")
OUT=Path("rde1-authentic-risk-eur-economic-gating-original.json")

def need(condition,tag):
    if not condition:raise ValueError("RDE1_"+tag)


def money_schedules(rows,fit,cost,gates,phase):
    """Study intent set + individual EUR audit, never a cash/funding replay."""
    policies=("FIXED_SIGNAL_WITHOUT_RISK_OVERLAY",
              "SIMPLE_REALIZED_VOLATILITY_TAIL_RESERVE",
              "CONDITIONAL_DISTRIBUTION_TAIL_RESERVE")
    state={name:Counter() for name in policies}
    snapshots={name:dict(intent=0,eligible=0,knownForward=0,
                         unknownForward=0,conditionalCentralEur=0.,
                         conditionalAdverseEur=0.,
                         lastSymbolExit={}) for name in policies}
    for r in (x for x in rows if x["phase"]==phase):
        s=r["s"];side=r["direction"]
        if side==0:continue
        eligible=gates[(s,side)]
        if not eligible["admitted"]:
            for name in policies:state[name][eligible["reason"]]+=1
            continue
        c=cost.get(s)
        if c is None:
            for name in policies:state[name]["FINANCIAL_UNKNOWN"]+=1
            continue
        friction=current_term_roundtrip_friction_bps(c,side,
            r["entryClock"],r["entryClock"]+24*M5)
        if friction is None or not 0<c["minimumNotionalEur"] or c["minimumMarginEur"]>=300:
            for name in policies:state[name]["COST_MARGIN_OR_FINANCING_UNKNOWN"]+=1
            continue
        tail=forecast(r,fit,side)
        for name in policies:
            z=snapshots[name];z["intent"]+=1
            if r["entryClock"]<z["lastSymbolExit"].get(s,-1):
                state[name]["EXISTING_MODELED_SYMBOL_HOLD"]+=1;continue
            q=(tail["simple"] if name=="SIMPLE_REALIZED_VOLATILITY_TAIL_RESERVE" else
               tail["conditional"] if name=="CONDITIONAL_DISTRIBUTION_TAIL_RESERVE" else None)
            if q is not None and (q+friction)*c["minimumNotionalEur"]/10000>15:
                state[name]["TAIL_RESERVE_EXCEEDS_EUR15_AT_LEGAL_MINIMUM"]+=1;continue
            z["eligible"]+=1
            z["lastSymbolExit"][s]=r["entryClock"]+24*M5
            if not r["known"]:
                z["unknownForward"]+=1;continue
            z["knownForward"]+=1
            z["conditionalCentralEur"]+=c["minimumNotionalEur"]*(
                side*r["returnBps"]-(
                    current_term_roundtrip_friction_bps(
                        {**c,"adverseBps":c["centralBps"]},
                        side,r["entryClock"],r["entryClock"]+24*M5) or friction))/10000
            z["conditionalAdverseEur"]+=c["minimumNotionalEur"]*(
                side*r["returnBps"]-friction)/10000
    out={}
    for name,z in snapshots.items():
        out[name]=dict(
            scheduledCausalIntents=z["intent"],preliminarilyRiskAdmissible=z["eligible"],
            selectedForwardPriced=z["knownForward"],
            selectedForwardUnknown=z["unknownForward"],
            conditionalCentralEurSumUNFUNDED=round(z["conditionalCentralEur"],8),
            conditionalAdverseEurSumUNFUNDED=round(z["conditionalAdverseEur"],8),
            preliminarilyRejected=dict(state[name]),
            nativeCommonEur300PortfolioExecuted=False,
            moneyNotHistoricallyFilledOrSpendable=True)
    out["CASH_NO_TRADE"]=dict(
        scheduledCausalIntents=0,preliminarilyRiskAdmissible=0,
        selectedForwardPriced=0,selectedForwardUnknown=0,
        conditionalCentralEurSumUNFUNDED=0.,conditionalAdverseEurSumUNFUNDED=0.,
        nativeCommonEur300PortfolioExecuted=False)
    return out


def main():
    p=json.loads(PROTOCOL.read_text())
    need(p["id"]=="RDE1" and p["status"]=="FROZEN_UNSCORED","PROTOCOL")
    scope=p["scope"];need(scope["originalM5Count"]==836087,"BAR_CONTROL")
    bars={};observed_cost=[];source_receipts=[]
    for source,folder in zip(p["sources"],("bdp-source","aip-source")):
        obj,decoded,audit=recover(Path(folder),source["originalRun"],
            source["sourceSha256"],source["schema"],source["protocol"])
        need(set(obj["bars"]).isdisjoint(bars),"ORIGINAL_SOURCE_OVERLAP")
        bars.update(obj["bars"])
        samples,cov=extract_costs(obj,decoded)
        observed_cost.extend(samples)
        source_receipts.append(dict(originalRun=source["originalRun"],
                                    sourceAudit=audit,costCoverage=cov))
        print("RDE1_ORIGINAL_SOURCE_READBACK",source["study"],flush=True)
    need(set(bars)==set(scope["universe"]),"ASSET_UNIVERSE")
    bar_count=sum(map(len,bars.values()))
    need(bar_count==836087,"ORIGINAL_BAR_COUNT")
    events=[];census={}
    for symbol in scope["universe"]:
        causals,actual,streak=causal_clocks(symbol,bars[symbol],scope)
        outcomes=realized_labels(causals,actual,streak,scope)
        need(len(outcomes)==len(causals),"CAUSAL_INTENT_LOST")
        census[symbol]=dict(originalBars=len(actual),causalHourlyClocks=len(causals),
                            knownForward=sum(r["known"] for r in outcomes),
                            unknownForward=sum(not r["known"] for r in outcomes))
        events.extend(outcomes)
    events.sort(key=lambda r:(r["t"],r["s"]))
    fit=fit_training(events)
    risk=[paired_weekly(events,fit,scope,phase,side)
         for phase in ("selection","exposed_audit") for side in (1,-1)]
    train_cost=cost_context([x for x in observed_cost if x["At"]<scope["trainEnd"]])
    gates={(symbol,side):mandatory_economic_gate(
            events,symbol,side,scope,train_cost.get(symbol))
           for symbol in scope["universe"] for side in (1,-1)}
    admitted=[{"symbol":sym,"side":side,**value}
              for (sym,side),value in gates.items() if value["admitted"]]
    diagnostics=[{"symbol":sym,"side":side,**value}
              for (sym,side),value in gates.items()]
    economics={ph:money_schedules(events,fit,train_cost,gates,ph)
              for ph in ("selection","exposed_audit")}
    # The original BDP1/AIP1 current-term quote snapshots do NOT prove BID/ASK
    # at each RDE1 hourly decision/hold/exit clock. No native funded replay
    # may be certified by interpolating these missing observations.
    result=dict(
        schema="MXM_RDE1_FIRST_ORIGINAL_PRELIMINARY_RISK_AND_EUR_GATE_V1",
        frozenProtocolSha256=sha256(PROTOCOL.read_bytes()).hexdigest(),
        originalProtectedRunId=int(os.environ["GITHUB_RUN_ID"]),
        originalSourceReadbacks=source_receipts,
        originalGenuineM5Bars=bar_count,sourceCensus=census,
        causalHourlyDecisionIntents=len(events),
        maturedTrainingRows=fit["trainKnown"],
        riskTrainingOnlyVolatilityTerciles=fit["terciles"],
        riskTrainingOnlySimpleTailQuantiles={
            str(k):v for k,v in fit["simple"].items()},
        riskPerformancePanels=risk,
        trainOnlyEconomicGate=diagnostics,
        trainOnlyEligibleDirectionalRoutes=admitted,
        trainOnlyCostContextCount=sum(x["At"]<scope["trainEnd"] for x in observed_cost),
        conditionalEconomicIntentPanels=economics,
        verdict="RDE1_PRELIMINARY_ECONOMIC_GATES_ONLY_NO_COMMON_NATIVE_EUR300_EVIDENCE",
        historicEventBidAskFillProof=False,
        completeHistoricFloatingMarkProof=False,
        oneNativeCSharpEur300LedgerExecuted=False,
        capitalResetOrExtraCashAllowed=False,
        globallyExposedHistoryDevelopmentOnly=True,
        independentConfirmation=False,
        promotionalSelectionAuthorized=False,
        modelQualified=False,ordersSubmitted=0,cloudActivated=False,
        newPepperstoneReadOnlyRequests=0,closedModelForecastsRerun=0)
    OUT.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False,
                              default=float)+"\n")
    print("RDE1_ORIGINAL_ECONOMIC_GATE",json.dumps(dict(
        genuineBars=bar_count,intents=len(events),trainKnown=fit["trainKnown"],
        qualifiedDirectionalRoutes=len(admitted),
        selectionRiskPanels=[{"side":x["side"],"n":x["n"],
            "pairedLower":x["pairedWeekDifferenceLowerBonferroni"]}
            for x in risk if x["phase"]=="selection"],
        exposedEconomicConditional=[
            {"policy":key,"adverseEUR_UNFUNDED":v["conditionalAdverseEurSumUNFUNDED"],
             "priced":v["selectedForwardPriced"]}
            for key,v in economics["exposed_audit"].items()],
        nativeEur300Executed=False,brokerOrders=0),sort_keys=True),flush=True)


if __name__=="__main__":
    main()

"""SPDE1: new systematic OHLCV categorical conditional prediction and EUR study.

Original BDP1/AIP1 source only. No broker API, trades, new account,
WIDE_REGIME grid, IPF1 models, closed study replay or Cloud activation.
All seven source feature families share identical 12-symbol clocks.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from math import log, sqrt
from pathlib import Path
from statistics import NormalDist, mean
import json
import os

from .multiscale_conditional_research import recover, extract_costs
from .integrated_predictive_funded import cost_context

P = Path("research/spde1_protocol.json")
M5 = 300000
HR = 3600000
WEEK = 7*24*HR
SCALE = 10000.0
FAM = (
    "CANDLE_GEOMETRY", "IMPULSE_PERSISTENCE", "VOLATILITY_TRANSITION",
    "CONSOLIDATION_BREAKOUT", "PULLBACK_CONTINUATION",
    "CLOSED_BAR_INDICATOR", "SYNCHRONIZED_PEER_CONTEXT",
)
PEERS = ("US500", "NAS100", "GER40", "XAUUSD", "EURUSD")
PSEUDO = 16.0
Z_DIR = NormalDist().inv_cdf(.975)
Z_SELECT = NormalDist().inv_cdf(1-.05/(len(FAM)*2*2))


def need(value, reason):
    if not value:
        raise ValueError("SPDE1_"+reason)


def sign(x):
    return (x>0)-(x<0)


def session_clocks(p):
    start=date(2025,11,3)
    times=[]
    for w in range(52):
        for d in range(5):
            day=start+timedelta(weeks=w, days=d)
            for h in p["calendar"]["decisionUtcHours"]:
                t=int(datetime(day.year, day.month, day.day, h,
                               tzinfo=timezone.utc).timestamp()*1000)
                if p["calendar"]["start"]<=t<p["calendar"]["end"]:
                    times.append(t)
    need(len(times)==52*5*len(p["calendar"]["decisionUtcHours"]),
         "EXPECTED_SCHEDULED_WEEKDAY_CLOCKS")
    return times


def state_phase(t, c):
    if t<c["trainEnd"]:
        return "training"
    if t<c["selectionEnd"]:
        return "selection"
    return "exposed_audit"


def ema(values, period):
    a=2/(period+1)
    result=values[0]
    for v in values[1:]:
        result=a*v+(1-a)*result
    return result


def feature_states(history, t):
    """49 EXACT completed consecutive M5 bars ending t, no future access.

    All primitive formulas are expressible from native cTrader Bars and
    RegimeDiscovery candle OHLCV/volatility primitives. No labels/quotes.
    """
    seq=[history.get(t-i*M5) for i in range(48,-1,-1)]
    if any(r is None or len(r)!=7 or int(r[1])!=t-(48-i)*M5
           for i,r in enumerate(seq)):
        return None
    if any(r[5]<=0 or r[4]<=0 or r[2]<=0 or r[3]<r[4] or
           not r[4]<=r[2]<=r[3] or not r[4]<=r[5]<=r[3]
           for r in seq):
        return None
    closes=[r[5]/1e5 for r in seq]
    bar=seq[-1];bar_range=max(1,bar[3]-bar[4])
    body=(bar[5]-bar[2])/bar_range
    upper=(bar[3]-max(bar[5],bar[2]))/bar_range
    lower=(min(bar[5],bar[2])-bar[4])/bar_range
    r6=log(closes[-1]/closes[-7])
    r12=log(closes[-1]/closes[-13])
    r24=log(closes[-1]/closes[-25])
    r48=log(closes[-1]/closes[0])
    last=[log(closes[i]/closes[i-1]) for i in range(1,49)]
    rv8=sqrt(sum(x*x for x in last[-8:])/8)
    rv32=sqrt(sum(x*x for x in last[-32:])/32)
    # Fully mature trailing volatility is the unit of normalization.
    norm_scale=max(.4,rv32*SCALE)*sqrt(12)  # fixed 60m forecast scale
    prev_hi=max(r[3] for r in seq[-25:-1])
    prev_lo=min(r[4] for r in seq[-25:-1])
    last14=last[-14:]
    up=sum(max(0,x) for x in last14)
    down=sum(max(0,-x) for x in last14)
    rsi=100*up/(up+down) if up+down else 50
    e12=ema(closes,12);e26=ema(closes,26)
    states={
        "CANDLE_GEOMETRY":sign(body+lower-upper),
        "IMPULSE_PERSISTENCE":sign(r6) if r6*r24>0 else 0,
        "VOLATILITY_TRANSITION":sign(rv8-rv32),
        "CONSOLIDATION_BREAKOUT":(
            1 if bar[5]>prev_hi else -1 if bar[5]<prev_lo else 0
        ),
        "PULLBACK_CONTINUATION":sign(r48) if r48*r12<0 else 0,
        "CLOSED_BAR_INDICATOR":(
            1 if rsi>50 and e12>e26 else
            -1 if rsi<50 and e12<e26 else 0
        ),
    }
    return {"state":states,"price":closes[-1],"scale60":norm_scale,
            "r48":r48,"r24":r24,"last8Rv":rv8,"last32Rv":rv32}


def build_tape(bars,p):
    """Feature-only pass over ALL scheduled clocks BEFORE outcome readback.

    The outcome stage below reads separate price maps. No target availability
    affects an intent, learned state, feature or ranking.
    """
    maps={}
    for s in p["universe"]:
        seen={}
        for item in bars[s]:
            need(len(item)==7 and item[1]-item[0]==M5 and
                 item[1] not in seen,"ORIGINAL_BAR_SHAPE_OR_DUPLICATE")
            seen[int(item[1])]=item
        maps[s]=seen
    times=session_clocks(p)
    slots=[]
    for t in times:
        cache={s:feature_states(maps[s],t) for s in p["universe"]}
        for s in p["universe"]:
            f=cache[s]
            if f is None:
                slots.append({"t":t,"symbol":s,"sourceState":"FEATURE_UNKNOWN",
                              "f":None})
                continue
            peers=[cache[x]["r48"] for x in PEERS
                   if x!=s and x in cache and cache[x] is not None]
            state=dict(f["state"])
            state["SYNCHRONIZED_PEER_CONTEXT"]=(
                sign(sum(peers)) if len(peers)>=2 else None
            )
            slots.append({"t":t,"symbol":s,"sourceState":"FEATURE_KNOWN",
                          "f":{**f,"state":state}})
    need(len(slots)==len(times)*len(p["universe"]),"SLOT_POPULATION")
    return slots,maps


def outcomes(slots,maps,p):
    """Only AFTER all features are frozen; never drop missing target slots."""
    result=[]
    for row in slots:
        for h in p["horizonsMinutes"]:
            phase=state_phase(row["t"],p["calendar"])
            f=row["f"]
            costless={"t":row["t"],"s":row["symbol"],"h":h,"phase":phase,
                      "f":f,"featureKnown":f is not None,"labelKnown":False,
                      "targetBps":None,"normalizedTarget":None}
            if f is None:
                result.append(costless)
                continue
            entry=maps[row["symbol"]].get(row["t"]+M5)
            exit_=maps[row["symbol"]].get(row["t"]+(h+5)*60000)
            phase_end=(p["calendar"]["trainEnd"] if phase=="training" else
                       p["calendar"]["selectionEnd"] if phase=="selection"
                       else p["calendar"]["end"])
            if (entry is None or exit_ is None or
                entry[5]<=0 or exit_[5]<=0 or
                row["t"]+(h+5)*60000 >= phase_end):
                result.append(costless)
                continue
            gross=SCALE*log(exit_[5]/entry[5])
            # Risk-normalized conditional mean across assets with different vol.
            scale=f["scale60"]*sqrt(h/60)
            result.append({**costless,"labelKnown":True,
                           "targetBps":gross,
                           "normalizedTarget":max(-6.,min(6.,gross/scale))})
    return result


def fit_training(rows):
    observed=defaultdict(list)
    global_rate=defaultdict(list)
    for r in rows:
        if r["phase"]!="training" or not r["labelKnown"]:
            continue
        global_rate[(r["s"],r["h"])].append(r["targetBps"]>0)
        for family in FAM:
            state=r["f"]["state"][family]
            if state is not None:
                observed[(r["s"],r["h"],family,state)].append(r["normalizedTarget"])
    models={}
    for key,values in observed.items():
        n=len(values);mu=sum(values)/(n+PSEUDO)
        var=max(.01,(sum(v*v for v in values)+PSEUDO)/(n+PSEUDO)-mu*mu)
        se=sqrt(var/(n+PSEUDO))
        positives=sum(v>0 for v in values)
        models[key]={"n":n,"mu":mu,"se":se,
                     "probUp":(positives+1)/(n+2)}
    prior={k:(sum(v)+1)/(len(v)+2) for k,v in global_rate.items()}
    return models,prior


def forecast(row,family,models,prior,cost):
    """Causal model trained only on earlier 26w. No future label access."""
    f=row["f"]
    if f is None:
        return {"state":"SOURCE_UNKNOWN","side":None}
    st=f["state"][family]
    if st is None:
        return {"state":"PEER_FEATURE_UNKNOWN","side":None}
    m=models.get((row["s"],row["h"],family,st))
    if m is None or m["n"]<1:
        return {"state":"TRAINING_SUPPORT_UNKNOWN","side":None}
    mean_bps=m["mu"]*f["scale60"]*sqrt(row["h"]/60)
    se_bps=m["se"]*f["scale60"]*sqrt(row["h"]/60)
    possible=sign(mean_bps)
    # Statistical uncertainty -> true ABSTAIN, never a compulsory order.
    if possible==0 or abs(mean_bps)<=Z_DIR*se_bps:
        return {"state":"PREDICTIVE_ABSTAIN","side":0,
                "forecastBps":mean_bps,"seBps":se_bps,
                "probUp":m["probUp"],"sourceState":st}
    if cost is None or cost["minimumMarginEur"]>=300 or not cost["fundingKnown"]:
        return {"state":"ECONOMIC_UNKNOWN","side":None,
                "forecastBps":mean_bps,"seBps":se_bps,
                "probUp":m["probUp"],"sourceState":st}
    lower=(abs(mean_bps)-Z_DIR*se_bps-cost["adverseBps"])
    if lower<=0:
        return {"state":"COST_ADVERSE_ABSTAIN","side":0,
                "forecastBps":mean_bps,"seBps":se_bps,
                "probUp":m["probUp"],"sourceState":st}
    # This is research-only opportunity, not funded/native admission.
    return {"state":"MODELLED_OPPORTUNITY","side":possible,
            "forecastBps":mean_bps,"seBps":se_bps,
            "probUp":m["probUp"],"sourceState":st,
            "conservativeNetEur":lower*cost["minimumNotionalEur"]/SCALE}


def economic_candidate(r, side, cost, scenario):
    if side is None or not r["labelKnown"] or cost is None:
        return None
    if side==0:
        return 0.0
    c=cost["adverseBps" if scenario=="adverse" else "centralBps"]
    return cost["minimumNotionalEur"]*(side*r["targetBps"]-c)/SCALE


def weekly_bound(x):
    if len(x)<8:
        return None
    sigma=sqrt(sum((v-mean(x))**2 for v in x)/(len(x)-1))
    return mean(x)-Z_SELECT*sigma/sqrt(len(x))


def study(rows,models,prior,cost,p):
    """Rank one candidate per scheduled clock in each model counterfactual.

    All policies scored on same clock population; only selected reference
    symbol/clock is compared to its own 4h momentum under identical costs.
    These counterfactuals are NOT 14 deployable or additive EUR300 books.
    """
    result={}
    times=session_clocks(p)
    groups=defaultdict(list)
    for r in rows:
        groups[(r["phase"],r["h"],r["t"])].append(r)
    for phase in ("selection","exposed_audit"):
        phase_times=[t for t in times if state_phase(t,p["calendar"])==phase]
        for h in p["horizonsMinutes"]:
            for family in FAM:
                weekly=defaultdict(lambda:{"net":[],"increment":[]})
                counts=Counter()
                quality={"brier":[],"brierPrior":[],"directionCorrect":[]}
                sample_by_symbol=Counter()
                for t in phase_times:
                    market=groups[(phase,h,t)]
                    need(len(market)==len(p["universe"]),"MISSING_GLOBAL_MARKET_SLOTS")
                    prepared=[]
                    for r in market:
                        y=r["targetBps"]
                        q=forecast(r,family,models,prior,cost.get(r["s"]))
                        counts[q["state"]]+=1
                        if y is not None and q.get("probUp") is not None:
                            actual=int(y>0)
                            quality["brier"].append((q["probUp"]-actual)**2)
                            q0=prior.get((r["s"],h),.5)
                            quality["brierPrior"].append((q0-actual)**2)
                            quality["directionCorrect"].append(
                                sign(q.get("forecastBps",0))==sign(y))
                        if q["state"]=="MODELLED_OPPORTUNITY":
                            sample_by_symbol[r["s"]]+=1
                            prepared.append((q["conservativeNetEur"],r["s"],r,q))
                    # Direction/availability fixed BEFORE reading any target;
                    # chosen opportunity never depends on future quote/label.
                    prepared.sort(key=lambda z:(-z[0],z[1]))
                    winner=prepared[0] if prepared else None
                    counts["selectedIntents"]+=int(winner is not None)
                    week=(t-p["calendar"]["start"])//WEEK
                    if winner:
                        _,_,r,q=winner
                        counts["selectedBySymbol:"+r["s"]]+=1
                        if not r["labelKnown"]:
                            counts["selectedOutcomeUNKNOWN"]+=1
                            continue
                        counts["selectedPriced"]+=1
                        for scenario in ("central","adverse"):
                            net=economic_candidate(r,q["side"],cost[r["s"]],scenario)
                            if net is not None:
                                counts[scenario+"Priced"]+=1
                                counts[scenario+"Positive"]+=int(net>0)
                                counts[scenario+"Negative"]+=int(net<0)
                                counts[scenario+"NetTotal10000"]+=round(net*SCALE)
                        adv=economic_candidate(r,q["side"],cost[r["s"]],"adverse")
                        own_side=sign(r["f"]["r48"])
                        own=economic_candidate(r,own_side,cost[r["s"]],"adverse")
                        weekly[week]["net"].append(adv)
                        weekly[week]["increment"].append(adv-own)
                    else:
                        weekly[week]["net"].append(0.)
                        weekly[week]["increment"].append(0.)
                base=26 if phase=="selection" else 39
                weeks=[sum(weekly[w]["net"]) for w in range(base,base+13)]
                incr=[sum(weekly[w]["increment"]) for w in range(base,base+13)]
                sig=[r["net"] for r in weekly.values()]
                ans={
                    "phase":phase,"horizonMinutes":h,"family":family,
                    "scheduledClocks":len(phase_times),
                    "scheduledSymbolIntents":len(phase_times)*len(p["universe"]),
                    "sourceSignalStates":{k:v for k,v in counts.items()
                                          if not k.endswith("NetTotal10000")},
                    "conditionalCentralNetEur":counts["centralNetTotal10000"]/SCALE,
                    "conditionalAdverseNetEur":counts["adverseNetTotal10000"]/SCALE,
                    "selectedKnownOutcomeCount":counts["selectedPriced"],
                    "selectedMissingOutcomeCount":counts["selectedOutcomeUNKNOWN"],
                    "directionalAccuracy":mean(quality["directionCorrect"])
                                          if quality["directionCorrect"] else None,
                    "brier":mean(quality["brier"]) if quality["brier"] else None,
                    "brierTrainPrior":mean(quality["brierPrior"]) if quality["brierPrior"] else None,
                    "weeklyAdverseModelledNetEur":weeks,
                    "weeklyIncrementalVsOwnMomentumEur":incr,
                    "weeklyLowerAbsoluteAdverseEur":weekly_bound(weeks),
                    "weeklyLowerIncrementalAdverseEur":weekly_bound(incr),
                    "selectedIntentsNotFundedNativeRoundTrips":True,
                    "sampledSymbolSignalCounts":dict(sample_by_symbol),
                }
                ans["selectionGate"]=(
                    phase=="selection" and
                    counts["selectedOutcomeUNKNOWN"]==0 and
                    counts["selectedPriced"]>=13 and
                    ans["weeklyLowerAbsoluteAdverseEur"] is not None and
                    ans["weeklyLowerAbsoluteAdverseEur"]>0 and
                    ans["weeklyLowerIncrementalAdverseEur"]>0
                )
                result[(phase,h,family)]=ans
    qualified=[r for (phase,h,f),r in result.items()
               if phase=="selection" and r["selectionGate"]]
    if len(qualified)!=1:
        # Precommitted familywide discovery cannot choose best of >1
        # after seeing selection performance without a secondary protocol.
        family=None
        reason=("NO_FAMILY_PASSED_STRICT_SELECTION" if not qualified
                else "MULTIPLE_FAMILIES_NO_EX_ANTE_TIEBREAK")
    else:
        family=(qualified[0]["family"],qualified[0]["horizonMinutes"])
        reason="ONE_SELECTION_SURVIVOR_DEVELOPMENT_ONLY"
    return {
        "panels":[result[k] for k in sorted(result)],
        "selectionQualifiedCount":len(qualified),
        "frozenSelectionFamilyHorizon":family,
        "status":reason,
        "selectedNativeFundedNetEur":None,
        "brokerRealizedNetEur":None,
        "brokerOrders":0,
        "fullYearHistoricalSourceGloballyExposed":True,
        "independentConfirmation":False,
    }


def main():
    p=json.loads(P.read_text())
    need(p["status"]=="PRE-SOURCE_FROZEN_BEFORE_ORIGINAL_RESULTS","PROTOCOL")
    need(tuple(p["feature"]["families"])==FAM,"FEATURE_CATALOG_CHANGED")
    merged={}
    cost_samples=[]
    receipt=[]
    for spec,dirname in zip(p["source"],("bdp-source","aip-source")):
        original,decoded,audit=recover(
            Path(dirname),spec["run"],spec["sha256"],
            spec["schema"],spec["protocol"]
        )
        need(set(original["bars"]).isdisjoint(merged),"SOURCE_SYMBOL_COLLISION")
        merged.update(original["bars"])
        costs,cov=extract_costs(original,decoded)
        cost_samples.extend(costs)
        receipt.append({"source":spec["name"],"run":spec["run"],
                        "reconstruction":audit,"historicalCostCoverage":cov})
        print("SPDE1_SOURCE_AUTHENTICATED",spec["name"],sum(len(v) for v in original["bars"].values()),flush=True)
    need(set(merged)==set(p["universe"]),"UNIVERSE_MISMATCH")
    original_count=sum(len(x) for x in merged.values())
    # Explicit stage separation: feature intents and forecast coordinates
    # populated BEFORE any future source price is accessed for the labels.
    intents,maps=build_tape(merged,p)
    observed=outcomes(intents,maps,p)
    training=[x for x in observed if x["phase"]=="training"]
    models,priors=fit_training(training)
    cost=cost_context([x for x in cost_samples
                       if x["At"]<p["calendar"]["trainEnd"]])
    for x in cost.values():
        for k in ("minimumNotionalEur","minimumMarginEur","centralBps","adverseBps"):
            need(x[k]>=0,"INVALID_AUTHENTIC_COST_CONTEXT")
    results=study(observed,models,priors,cost,p)
    sourceCensus={}
    for phase in ("training","selection","exposed_audit"):
        chosen=[x for x in observed if x["phase"]==phase]
        sourceCensus[phase]={
            "scheduledHorizonSymbolSlots":len(chosen),
            "featureKnown":sum(x["featureKnown"] for x in chosen),
            "labelKnown":sum(x["labelKnown"] for x in chosen),
            "featureUnknown":sum(not x["featureKnown"] for x in chosen),
            "forwardLabelUnknown":sum(x["featureKnown"] and not x["labelKnown"] for x in chosen)
        }
    out={
        "schema":"MXM_SPDE1_AUTHENTIC_ORIGINAL_SYSTEMATIC_PREDICTIVE_EUR_V1",
        "originalProtocolSha256":sha256(P.read_bytes()).hexdigest(),
        "executionRunId":int(os.environ["GITHUB_RUN_ID"]),
        "sourceOriginalRuns":[s["run"] for s in p["source"]],
        "sourceOriginalHashes":[s["sha256"] for s in p["source"]],
        "sourceAuthenticityReceipts":receipt,
        "sourceOriginalM5BarCount":original_count,
        "originalSourceUniverse":{s:len(x) for s,x in merged.items()},
        "historicalCostSamplesAllExposed":len(cost_samples),
        "trainingCostSamplesOnly":sum(x["At"]<p["calendar"]["trainEnd"] for x in cost_samples),
        "trainingAuthenticCostBySymbol":cost,
        "sourceCensus":sourceCensus,
        "modelConditionalStatesFit":len(models),
        "systematicCategoricalResults":results,
        "sourceGlobalExposureNotIndependent":True,
        "historicalBidAskAtAllStudyDecisions":False,
        "actualBrokerFillProven":False,
        "nativeFundedContinuousEur300BookProven":False,
        "continuousFloatingDrawdown30Proven":False,
        "hard21SystemProven":False,
        "historicalCostScenarioOnlyNoNativeExecution":True,
        "closedStudiesReexecuted":False,
        "newBrokerRequests":0,
        "ordersSubmitted":0,
        "cloudActivated":False,
    }
    Path("spde1-systematic-ohlcv-authentic-eur.json").write_text(
        json.dumps(out,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("SPDE1_AUTHENTIC_SYSTEMATIC_RESULT",json.dumps({
        "sourceBars":original_count,"sourceCostSamples":len(cost_samples),
        "stateModels":len(models),"selectionQualified":
            results["selectionQualifiedCount"],"selectedPolicy":
            results["frozenSelectionFamilyHorizon"],
        "bestCentralDescriptive":sorted(
            [(z["conditionalCentralNetEur"],z["family"],z["horizonMinutes"])
             for z in results["panels"] if z["phase"]=="selection"],
            reverse=True)[:2],
        "noTrading":True,"nativeFundedNetEur":None
    },sort_keys=True),flush=True)


if __name__=="__main__":
    main()

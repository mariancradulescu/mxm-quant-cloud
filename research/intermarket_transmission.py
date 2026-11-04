"""IMT1: PRE-REGISTERED exposed intermarket transmission and underreaction.

Never imports/runs a frozen forecast. Reuses ONLY authenticated raw source readback
and causal cost-observation routines already verified for the same two sealed
Pepperstone sources. Output is PUBLIC aggregate CONDITIONAL_COST_MODEL bps, not
historical fills, EUR200 funded NET, independent confirmation or HARD21.
"""
import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from .multiscale_conditional_research import recover, extract_costs

P = Path("research/intermarket_transmission_protocol.json")
WEEK_MS = 604800000
BAR_MS = 300000
HOUR_MS = 3600000
DAYS_MS = 86400000

def require(ok, message):
    if not ok:
        raise ValueError(message)

def digest(x):
    return hashlib.sha256(x).hexdigest()

def quantile(values, q):
    a = sorted(values)
    if not a:
        return None
    at = q * (len(a)-1)
    lo = int(at)
    hi = min(lo+1, len(a)-1)
    return a[lo] * (hi-at) + a[hi] * (at-lo)

def close_map(rows):
    # Explicit complete-bar End time and strictly monotone increasing clocks.
    rows = sorted(rows, key=lambda x: x[1])
    require(all(x[0] < x[1] and x[5] > 0 and x[1]-x[0] == BAR_MS for x in rows),
            "IMT1_INVALID_SOURCE_BAR")
    require(all(a[1] < b[1] for a,b in zip(rows,rows[1:])), "IMT1_DUPLICATE_BAR")
    return {x[1]:x[5] for x in rows}

def complete_pair(data, t, horizon_minutes):
    end = t + horizon_minutes * 60000
    if t not in data or end not in data:
        return None
    # No bars may be invented in an observed gap; all exact M5 closes required.
    if any(t + k * BAR_MS not in data for k in range(1, horizon_minutes//5+1)):
        return None
    return math.log(data[end]/data[t]) * 10000

def hour_return(data, t):
    v = complete_pair(data, t-HOUR_MS, 60)
    return v

def phase(t, p):
    if p["start"] <= t < p["developmentEnd"]:
        return "development", p["developmentEnd"]
    if p["developmentEnd"] <= t < p["selectionEnd"]:
        return "selection", p["selectionEnd"]
    if p["selectionEnd"] <= t < p["end"]:
        return "exposed_audit", p["end"]
    return None,None

def costs_by_symbol(costs):
    groups = defaultdict(list)
    for x in costs:
        groups[x["Symbol"]].append(x)
    out = {}
    for symbol, rows in groups.items():
        spreads = [float(x["SpreadBps"]) for x in rows]
        commissions = [float(x["CommissionBps"]) for x in rows]
        one_sec = [max(0.0,float(x["PastVolBps"]))/math.sqrt(300) for x in rows]
        if len(rows) < 3:
            continue
        avg_spread = mean(spreads)
        p90_spread = quantile(spreads,.9)
        commission = max(commissions)
        vol = max(one_sec)  # Conservative development reference, not a measured fill.
        out[symbol] = dict(
            contexts=len(rows),marginEur=max(float(x["CurrentMinimumMarginEur"]) for x in rows),
            centralBps=avg_spread+commission+2*(.25*avg_spread+vol),
            adverseBps=p90_spread+1.25*commission+2*(.5*p90_spread+2*vol),
            stressBps=2*p90_spread+2*commission+2*(p90_spread+3*vol),
            spreadMeanBps=avg_spread,spreadP90Bps=p90_spread,
            currentCommissionMaxBps=commission
        )
    return out

def assess(market,p):
    targets=p["targets"]
    cost=costs_by_symbol(market["costs"])
    expected=set(targets)|set(p["sourceIndices"])
    require(expected.issubset(market["bars"]) and set(targets).issubset(cost),
            "IMT1_MISSING_AUTHENTIC_SOURCE_OR_COST_CONTEXT")
    mapped={s:close_map(rows) for s,rows in market["bars"].items()}
    source=p["sourceIndices"]
    all_indices=sorted(set().union(*(mapped[s] for s in source)))
    results=defaultdict(lambda:dict(known=[],unknown=0,proposalCount=0,
                                    weeks=defaultdict(list),unknownWeeks=set()))
    last_planned_end={}
    joint=defaultdict(set)
    source_gates=dict(candidateIndexClocks=0,usableIndexBreadthClocks=0,unavailableIndexClocks=0)
    for t in all_indices:
        current_phase,boundary=phase(t,p)
        if current_phase is None:
            continue
        clock=datetime.fromtimestamp(t/1000,timezone.utc)
        if clock.hour < p["sampling"]["hourUtcMin"] or clock.hour>p["sampling"]["hourUtcMaxInclusive"] or clock.minute not in p["sampling"]["minutes"]:
            continue
        source_gates["candidateIndexClocks"] += 1
        index_moves=[]
        for s in source:
            r=hour_return(mapped[s],t)
            if r is not None and abs(r)>=p["sampling"]["minIndexImpulseAbsBps"]:
                index_moves.append(1 if r>0 else -1)
        direction=1 if index_moves.count(1)>=2 else -1 if index_moves.count(-1)>=2 else 0
        if not direction:
            source_gates["unavailableIndexClocks"]+=1
            continue
        source_gates["usableIndexBreadthClocks"]+=1
        for symbol,side_factor in targets.items():
            own=mapped[symbol]
            if t not in own:
                continue
            own_prev=hour_return(own,t)
            side=direction*side_factor
            for family in p["families"]:
                if family=="TARGET_UNDERREACTION":
                    if own_prev is None or own_prev*side >= -p["sampling"]["minUnderreactionAbsBps"]:
                        continue
                for horizon in p["horizonsMinutes"]:
                    key=(symbol,family,horizon,current_phase)
                    # No ex-post use of the target price to decide whether to
                    # create a proposal or avoid its overlap with earlier plans.
                    plan_key=(symbol,family,horizon)
                    if t<last_planned_end.get(plan_key,-1):
                        continue
                    # Crossing the UTC calendar/phase prevents unmeasured
                    # financing; this is a fixed predecision clock rule.
                    end=t+horizon*60000
                    if (end-1)//DAYS_MS!=t//DAYS_MS or end>boundary:
                        continue
                    last_planned_end[plan_key]=end
                    group=results[key]
                    group["proposalCount"]+=1
                    week=(t-p["start"])//WEEK_MS
                    y=complete_pair(own,t,horizon)
                    if y is None:
                        group["unknown"]+=1
                        group["unknownWeeks"].add(week)
                        continue
                    gross=side*y
                    c=cost[symbol]
                    vals=dict(grossBps=gross,
                        centralBps=gross-c["centralBps"],
                        adverseBps=gross-c["adverseBps"],
                        stressBps=gross-c["stressBps"])
                    group["known"].append(vals)
                    group["weeks"][week].append(vals)
                    joint[t].add(symbol)
    report=[]
    for symbol in targets:
        for family in p["families"]:
            for horizon in p["horizonsMinutes"]:
                for stage in ("development","selection","exposed_audit"):
                    item=results[(symbol,family,horizon,stage)]
                    known=item["known"]
                    weeks=item["weeks"]
                    vals={}
                    for k in ("grossBps","centralBps","adverseBps","stressBps"):
                        z=[x[k] for x in known]
                        vals[k]=dict(observed=len(z),mean=(mean(z) if z else None),
                                     sum=(sum(z) if z else None))
                    rangeWeeks=range({"development":0,"selection":26,"exposed_audit":39}[stage],
                        {"development":26,"selection":39,"exposed_audit":52}[stage])
                    weekly=[sum(z["adverseBps"] for z in weeks[w]) for w in rangeWeeks]
                    lower=quantile(weekly,.1)
                    ready=(stage=="selection" and len(known)>=30 and len(weeks)>=8 and
                        item["unknown"]==0 and lower is not None and lower>0)
                    report.append(dict(symbol=symbol,family=family,horizonMinutes=horizon,
                        phase=stage,proposed=item["proposalCount"],complete=len(known),unknown=item["unknown"],
                        activeWeeks=len(weeks),fullWeeks=13 if stage!="development" else 26,
                        adverseWeeklyTenthPercentileBpsProxy=lower,
                        followupEligibleSelectionOnly=ready,costBps=cost[symbol],conditional=vals))
    return dict(schema="IMT1_CONDITIONAL_DEVELOPMENT",readOnly=True,
        independentConfirmation=False,fundedNetEur=None,systemHard21Proven=False,
        completeRoundTrips=0,ordersSubmitted=0,cloudActivated=False,
        sourceGates=source_gates,groupCount=len(report),groups=report,
        observedJointCandidateClocks=len(joint),
        maxDistinctTargetsAtCommonClock=max((len(x) for x in joint.values()),default=0),
        allCurrentMarginIsNotHistorical=True,
        selectionSupport=[dict(symbol=x["symbol"],family=x["family"],horizonMinutes=x["horizonMinutes"])
            for x in report if x["followupEligibleSelectionOnly"]],
        # Confirms no allocation to an unqualified candidate: caller must use
        # the sole native C# orchestrator on fully priced EUR scenarios later.
        nativeFundedAllocationNotRun=True)

def run():
    p=json.loads(P.read_text())
    require(p["id"]=="IMT1" and not Path("docs/IMT1_CONDITIONAL_RESULT.json").exists(),
            "IMT1_FROZEN_RESCORING_PROHIBITED")
    refs=[("bdp-source","mxm-bdp1-source-v1","research/portfolio_discovery_protocol.json"),
          ("aip-source","mxm-aip1-source-v1","research/auction_inventory_protocol.json")]
    bars={};costs=[];audits=[]
    for i,(folder,schema,source_p) in enumerate(refs):
        b,decoded,audit=recover(Path(folder),p["sourceRuns"][i],
            p["sourceCiphertextSha256"][i],schema,source_p)
        for sym,rows in b["bars"].items():
            require(sym not in bars,"IMT1_DUPLICATE_SYMBOL_SOURCE")
            bars[sym]=rows
        c,coverage=extract_costs(b,decoded)
        costs.extend(c)
        audits.append(dict(sourceRunId=p["sourceRuns"][i],readback=audit,observedCostContexts=len(c),
                           costMissing=[x["Symbol"] for x in coverage if x["ObservedCompleteCostWindows"]==0]))
        print("IMT1_AUTHENTIC_SOURCE_BOUND "+str(p["sourceRuns"][i]),flush=True)
    output=assess(dict(bars=bars,costs=costs),p)
    output.update(protocolSha256=digest(P.read_bytes()),sourceAudits=audits,
        totalOriginalM5Bars=sum(len(x) for x in bars.values()),executionRunId=int(os.environ["GITHUB_RUN_ID"]),
        sourceRecollected=False,closedForecastsCalled=0)
    Path("intermarket-public.json").write_text(json.dumps(output,sort_keys=True,indent=2,allow_nan=False)+"\n")
    summary=dict(run=output["executionRunId"],M5bars=output["totalOriginalM5Bars"],
        groups=output["groupCount"],sourceClocks=output["sourceGates"],
        jointClocks=output["observedJointCandidateClocks"],selectionSupport=output["selectionSupport"],
        fundedNetEur=None,qualified=False)
    print("IMT1_EXPOSED_CONDITIONAL "+json.dumps(summary,sort_keys=True),flush=True)

if __name__=="__main__":
    run()

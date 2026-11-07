"""FLS1 one preregistered EURUSD -> GBPUSD lead/lag research, no broker calls.

Frozen 52-week Pepperstone sources are globally exposed: this is exploratory
conditional economics only, NOT independent trading/fill/NET EUR certification.
Original encrypted source, broker identity, cost contexts, and C# source readback
are verified by already-installed research utilities. No closed predictor runs.
"""
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev, NormalDist

from .multiscale_conditional_research import recover, extract_costs
from .integrated_predictive_funded import cost_context
from .f2_preflight import prospective_economic_futility

PROTOCOL = Path("research/fls1_protocol.json")
HOUR = 3_600_000
M5 = 300_000
WEEK = 7 * 24 * HOUR


def require(condition, reason):
    if not condition:
        raise ValueError("FLS1_" + reason)


def signal(prices_eur, prices_gbp, clock, minimum_leader_bps=2.,
           maximum_lagger_fraction=.75):
    """Exactly 13 prior, completed five-minute closes for EACH currency."""
    times = [clock-i*M5 for i in range(13)]
    if any(t not in prices_eur or t not in prices_gbp for t in times):
        return None, "PAST_M5_GAP"
    if any(prices_eur[t] <= 0 or prices_gbp[t] <= 0 for t in times):
        return None, "INVALID_PRIOR_PRICE"
    lead = 10000*math.log(prices_eur[clock]/prices_eur[clock-HOUR])
    lag = 10000*math.log(prices_gbp[clock]/prices_gbp[clock-HOUR])
    if abs(lead) < minimum_leader_bps:
        return None, "LEADER_SMALL"
    if abs(lag) > maximum_lagger_fraction*abs(lead):
        return None, "LAGGER_NOT_UNDERREACTED"
    return dict(side=1 if lead>0 else -1,
                benchmarkSide=(1 if lag>0 else -1 if lag<0 else 0),
                leaderPastBps=lead,laggerPastBps=lag), "CAUSAL_SIGNAL"


def eligible(p, leader, lagger):
    """Fix source eligibility without inspecting ANY future price values."""
    cal=p["calendar"];mech=p["mechanism"]
    counters=defaultdict(Counter)
    rows=defaultdict(list)
    for clock in range(cal["start"],cal["selectionEnd"],HOUR):
        dt=datetime.fromtimestamp(clock/1000,timezone.utc)
        if dt.weekday() not in cal["weekdaysUtc"] or dt.hour not in cal["decisionHoursUtc"]:
            continue
        phase="development" if clock<cal["developmentEnd"] else "selection"
        counters[phase]["declaredClock"]+=1
        feature,why=signal(leader,lagger,clock,
            mech["minAbsLeaderReturnBps"],
            mech["maxAbsoluteLaggerReturnFractionOfLeader"])
        if feature is None:
            counters[phase][why]+=1
            continue
        entry=clock+mech["entryDelayMinutes"]*60_000
        exit_at=entry+mech["holdingMinutes"]*60_000
        phase_end=cal["developmentEnd"] if phase=="development" else cal["selectionEnd"]
        if exit_at>=phase_end:
            counters[phase]["labelCrossesPhase"]+=1
            continue
        forward_clocks=range(entry,exit_at+M5,M5)
        if any(t not in lagger for t in forward_clocks):
            counters[phase]["missingFutureSourceClock"]+=1
            continue
        week=(clock-cal["start"])//WEEK
        rows[phase].append(dict(week=week,clock=clock,entry=entry,exit=exit_at,
                                 side=feature["side"],benchmarkSide=feature["benchmarkSide"]))
        counters[phase]["completeCausalSourceOpportunity"]+=1
    return rows,counters


def weekly_score(rows, target_prices, cost, base_week, number_weeks):
    """At fixed signals only, observed M5 closes are EXPLORATORY fill proxies."""
    metrics=defaultdict(list)
    events=[]
    for row in rows:
        e,x=target_prices[row["entry"]],target_prices[row["exit"]]
        require(e>0 and x>0,"NONPOSITIVE_SOURCE_PRICE")
        move=10000*math.log(x/e)
        gross=row["side"]*move
        bench_side=row["benchmarkSide"]
        benchmark_gross=bench_side*move
        bench_cost=cost["adverseBps"] if bench_side else 0.
        item=dict(week=row["week"],grossBps=gross,
                  centralNetBps=gross-cost["centralBps"],
                  adverseNetBps=gross-cost["adverseBps"],
                  stressNetBps=gross-cost["stressBps"],
                  sameClockBenchmarkGrossBps=benchmark_gross,
                  matchedIncrementalAdverseNetBps=gross-cost["adverseBps"]-
                                               (benchmark_gross-bench_cost))
        events.append(item)
        for k in ("grossBps","centralNetBps","adverseNetBps","stressNetBps",
                  "matchedIncrementalAdverseNetBps"):
            metrics[(row["week"],k)].append(item[k])
    keys=("grossBps","centralNetBps","adverseNetBps","stressNetBps",
          "matchedIncrementalAdverseNetBps")
    weekly={k:[mean(metrics[(w,k)]) if metrics[(w,k)] else 0.
                for w in range(base_week,base_week+number_weeks)] for k in keys}
    return dict(signalCount=len(events),
                activeWeeks=len({row["week"] for row in rows}),
                meanPerSignalBps=({k:mean(e[k] for e in events) for k in keys} if events else {}),
                weeklyEqualCalendarBps={k:mean(v) for k,v in weekly.items()},
                weekly=weekly)


def hac_lower(values, total_tests=2, alpha=.05, lags=3):
    """Two Bonferroni one-sided Newey-West(3) bounds, even empty weeks included."""
    n=len(values)
    if n<3 or stdev(values)<=0 or any(not math.isfinite(x) for x in values):
        return None
    avg=mean(values)
    centered=[v-avg for v in values]
    variance=sum(x*x for x in centered)/n
    for lag in range(1,lags+1):
        cov=sum(centered[i]*centered[i-lag] for i in range(lag,n))/n
        variance+=2*(1-lag/(lags+1))*cov
    se=max(stdev(values)/math.sqrt(n),math.sqrt(max(0,variance)/n))
    return avg-NormalDist().inv_cdf(1-alpha/total_tests)*se


def run():
    raw=PROTOCOL.read_bytes()
    p=json.loads(raw)
    require(p["id"]=="FLS1" and p["locked"] and
            p["status"]=="PREDECLARED_UNSCORED" and
            p["prospectiveInitialCapitalEur"]==300 and
            p["originalSource"]["fullyGloballyExposedWeeks"]==52 and
            p["restrictions"]["noLiveDemoOrders"] and
            p["restrictions"]["noTokenRefresh"],"PROTOCOL_AUTHORITY")
    cal=p["calendar"];mech=p["mechanism"];source=p["originalSource"]
    require(cal["developmentEnd"]-cal["start"]==26*WEEK and
            cal["selectionEnd"]-cal["developmentEnd"]==13*WEEK and
            cal["end"]-cal["selectionEnd"]==13*WEEK,"CALENDAR")
    require(mech["entryDelayMinutes"]==5 and mech["holdingMinutes"]==60
            and cal["decisionHoursUtc"]==[8,12,16],"LOCKED_CLOCK")
    source_manifest=json.loads(Path(source["sourceManifest"]).read_text())
    require([r["run"] for r in source_manifest["source"]]==source["sealedRuns"],
            "ORIGINAL_SOURCE_RUNS")
    all_bars={};contexts=[];receipts=[]
    for row in source_manifest["source"]:
        bundle,decoded,proof=recover(Path(row["folder"]),row["run"],row["hash"],
                                     row["schema"],row["protocol"])
        require(proof and not set(bundle["bars"]).intersection(all_bars),
                "ORIGINAL_CUSTODY_OR_ASSET_DUPLICATE")
        all_bars.update(bundle["bars"])
        new_costs,_=extract_costs(bundle,decoded)
        contexts.extend(new_costs)
        receipts.append(dict(sourceRunId=row["run"],originalAuthentic=True,
                             exactOriginalCryptographicAccount=True))
    require(sum(len(v) for v in all_bars.values())==
            source["expectedOriginalM5Bars"],"ORIGINAL_BARS")
    require(len(contexts)==source["expectedAuthenticatedCostContexts"],
            "AUTHENTIC_COST_CONTEXT_COUNT")
    target=source["target"]
    require(all(s in all_bars for s in source["universe"]),"SOURCE_UNIVERSE")
    costs=cost_context(contexts)
    available=costs.get(target,{})
    need_cost=("observed","minimumNotionalEur","minimumMarginEur",
               "centralBps","adverseBps","stressBps")
    cost_ok=(all(k in available and isinstance(available[k],(int,float))
                 and math.isfinite(available[k]) for k in need_cost)
             and available.get("observed",0)>=p["costs"]["requireOriginalObservedSamplesAtLeast"]
             and 0<available.get("minimumMarginEur",0)<300
             and 0<available.get("minimumNotionalEur",0)
             and 0<available.get("adverseBps",0))
    prices={s:{int(bar[1]):bar[5] for bar in all_bars[s]} for s in source["universe"]}
    records,source_counts=eligible(p,prices["EURUSD"],prices["GBPUSD"])
    result=dict(schema="MXM_FLS1_ORIGINAL_AUTHENTIC_EXPOSED_RESEARCH_V1",
       protocolSha256=hashlib.sha256(raw).hexdigest(),
       runId=int(os.environ.get("GITHUB_RUN_ID","0")),
       originalProofs=receipts,originalSourceM5Bars=sum(len(x) for x in all_bars.values()),
       authenticatedCurrentTermCostContexts=len(contexts),sourceSymbols=source["universe"],
       originalLiveAccountBoundByReadback=True,
       noNewBrokerRequests=True,modelledCostsNotHistoricalFills=True,
       sourceCounts={k:dict(v) for k,v in source_counts.items()},
       sourceEligibleByPhase={k:len(records[k]) for k in ("development","selection")},
       currentCostAndContract={k:available.get(k) for k in (
           "observed","minimumMarginEur","minimumNotionalEur",
           "centralBps","adverseBps","stressBps","fundingKnown")},
       costPreflightPass=cost_ok,
       development=None,existingF2EconomicFutilityPreflight=None,
       selection=None,selectionOutcomeInspected=False,
       sourceHistoricalWeeksGloballyExposed=52,sourceUnscoredAuditWeeks=13,
       independentConfirmation=False,noClosedStudyModelCalls=True,
       modeledFundingEurNet=None,nativeCSharpFundedRoundTrips=0,
       systemHard21Proven=False,globalFloatingDrawdown30Certified=False,
       ordersSubmitted=0,refreshTokenConsumed=False,cloudActivated=False)
    if not cost_ok:
        result["verdict"]="CLOSED_NO_VERIFIABLE_TARGET_COST_OR_EUR300_CONTRACT"
    else:
        dev=weekly_score(records["development"],prices[target],available,0,26)
        result["development"]={k:v for k,v in dev.items() if k!="weekly"}
        preflight=prospective_economic_futility(
          dev["weekly"]["adverseNetBps"],
          dev["weekly"]["matchedIncrementalAdverseNetBps"],
          model_cost_context_complete=True,predeclared_comparisons=2,
          active_development_weeks=dev["activeWeeks"],
          required_incremental_surplus_bps=0.,
          alpha_family=.05,hac_lags=3)
        result["existingF2EconomicFutilityPreflight"]=preflight
        if not preflight.get("scoreSelectionAllowed",False):
            result["verdict"]="CLOSED_EXACT_DEVELOPMENT_F2_FUTILITY_OR_INSUFFICIENT_POWER"
        else:
            selected=weekly_score(records["selection"],prices[target],available,26,13)
            net_lower=hac_lower(selected["weekly"]["adverseNetBps"])
            inc_lower=hac_lower(selected["weekly"]["matchedIncrementalAdverseNetBps"])
            support=bool(net_lower is not None and inc_lower is not None
                         and net_lower>0 and inc_lower>0)
            result["selection"]={k:v for k,v in selected.items() if k!="weekly"}
            result["selection"].update(dict(
                adjustedAdverseNetLowerBps=net_lower,
                adjustedIncrementalVsSameClockOwnMomentumLowerBps=inc_lower,
                supportsNewNativeCSharpFundingResearch=support,
                globallyExposedNotIndependent=True,
                historicalActualFillsKnown=False))
            result["selectionOutcomeInspected"]=True
            result["verdict"]=("SELECTION_CONDITIONAL_SUPPORT_NATIVE_FUNDING_NEXT"
                              if support else
                              "CLOSED_EXACT_NO_ADVERSE_AND_BENCHMARK_SELECTION_SUPPORT")
    Path("fls1-authentic-public.json").write_text(json.dumps(
        result,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    summary={k:result.get(k) for k in (
        "runId","originalSourceM5Bars","authenticatedCurrentTermCostContexts",
        "costPreflightPass","sourceEligibleByPhase","development","existingF2EconomicFutilityPreflight",
        "selection","verdict","nativeCSharpFundedRoundTrips","ordersSubmitted")}
    print("FLS1_AUTHENTIC_RESULT "+json.dumps(summary,sort_keys=True),flush=True)


if __name__=="__main__":
    run()

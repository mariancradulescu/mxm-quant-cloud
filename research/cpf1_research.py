"""CPF1: three independent Cloud-native H1 OHLCV economic families.

Only originally sealed Pepperstone source and cost observations. This module
never connects to a broker and never imports or scores a closed study model.
All historical dates are globally exposed; no independent promotion.
"""
import hashlib
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, median, stdev, NormalDist

from .multiscale_conditional_research import recover, extract_costs
from .integrated_predictive_funded import cost_context
from .f2_preflight import prospective_economic_futility

PROTOCOL=Path("research/cpf1_protocol.json")
HOUR=3_600_000
M5=300_000
WEEK=7*24*HOUR
FAMILIES=("DONCHIAN_TREND_VOLUME","BOLLINGER_OVEREXTENSION_REVERSION",
          "H1_FALSE_BREAK_LIQUIDITY_SWEEP")
METRICS=("grossBps","centralNetBps","adverseNetBps","stressNetBps",
         "incrementalVsFourHourMomentumAdverseBps")


def require(condition,reason):
    if not condition:
        raise ValueError("CPF1_"+reason)


def h1_from_m5(rows):
    """Exact, causally closed hourly OHLC+tick-volume, no calendar bar filling."""
    slots=defaultdict(list)
    seen=set()
    for r in rows:
        a,b=int(r[0]),int(r[1])
        require(b-a==M5 and b not in seen and
                float(r[2])>0 and float(r[5])>0 and
                float(r[3])>=float(r[4])>0 and int(r[6])>=0,
                "ORIGINAL_M5_GEOMETRY")
        seen.add(b)
        end=((b-1)//HOUR+1)*HOUR
        slots[end].append(r)
    h={}
    for end,items in slots.items():
        if len(items)!=12:
            continue
        items.sort(key=lambda r:r[1])
        if [int(x[1]) for x in items] != list(range(end-11*M5,end+M5,M5)):
            continue
        h[end]=(float(items[0][2]),max(float(x[3]) for x in items),
                min(float(x[4]) for x in items),float(items[-1][5]),
                sum(int(x[6]) for x in items))
    return h


def family_sides(current,previous):
    """Returns signed predictions using ONLY 21 exact completed H1 observations.

    'previous' is in reverse time order: [t-1h,..,t-20h].
    No future fractal confirmation, chart recalc or ML external to the cBot.
    """
    require(len(previous)==20,"LOOKBACK_FIXED_20")
    out={name:0 for name in FAMILIES}
    op,hi,lo,close,volume=current
    if not (lo>0 and hi>=lo and close>0):
        return out
    prior_high=max(x[1] for x in previous)
    prior_low=min(x[2] for x in previous)
    prior_vol=[x[4] for x in previous]
    if min(prior_vol)>0 and volume>=1.2*median(prior_vol):
        if close>prior_high:
            out["DONCHIAN_TREND_VOLUME"]=1
        elif close<prior_low:
            out["DONCHIAN_TREND_VOLUME"]=-1
    past_close=[x[3] for x in previous]
    avg=mean(past_close)
    sigma=math.sqrt(sum((v-avg)**2 for v in past_close)/20)
    if sigma>0:
        z=(close-avg)/sigma
        if z>=2:
            out["BOLLINGER_OVEREXTENSION_REVERSION"]=-1
        elif z<=-2:
            out["BOLLINGER_OVEREXTENSION_REVERSION"]=1
    # Current candle may sweep ONE old side; double-sweeps are ambiguous.
    prior12=previous[:12]
    old_hi=max(x[1] for x in prior12)
    old_lo=min(x[2] for x in prior12)
    amplitude=hi-lo
    if amplitude>0:
        swept_hi=hi>old_hi
        swept_lo=lo<old_lo
        if swept_hi and not swept_lo and close<old_hi and lo>=old_lo:
            upper=hi-max(op,close)
            if upper>=.45*amplitude:
                out["H1_FALSE_BREAK_LIQUIDITY_SWEEP"]=-1
        elif swept_lo and not swept_hi and close>old_lo and hi<=old_hi:
            lower=min(op,close)-lo
            if lower>=.45*amplitude:
                out["H1_FALSE_BREAK_LIQUIDITY_SWEEP"]=1
    return out


def candidate_source_events(protocol,hourly,prices,eligible_symbols):
    """Source clocks and causal past-only signals; never inspect forward values."""
    cal=protocol["clock"]
    output={k:defaultdict(list) for k in FAMILIES}
    counters={k:defaultdict(Counter) for k in FAMILIES}
    all_clocks=range(cal["start"],cal["selectionEnd"],HOUR)
    for symbol in eligible_symbols:
        hours=hourly[symbol]
        observed=prices[symbol]
        for t in all_clocks:
            d=datetime.fromtimestamp(t/1000,timezone.utc)
            if d.weekday() not in cal["utcWeekdays"] or d.hour not in cal["utcHours"]:
                continue
            phase="development" if t<cal["developmentEnd"] else "selection"
            for name in FAMILIES:
                counters[name][phase]["scheduledSymbolClock"]+=1
            if t not in hours or any((t-i*HOUR) not in hours for i in range(1,21)):
                for name in FAMILIES:
                    counters[name][phase]["pastClosedH1Incomplete"]+=1
                continue
            previous=[hours[t-i*HOUR] for i in range(1,21)]
            predictions=family_sides(hours[t],previous)
            past4=previous[3][3]
            momentum=(1 if hours[t][3]>past4 else
                      -1 if hours[t][3]<past4 else 0)
            for name,side in predictions.items():
                if not side:
                    counters[name][phase]["causalAbstention"]+=1
                    continue
                entry=t+M5
                exit_at=entry+cal["holdMinutes"]*60_000
                end=(cal["developmentEnd"] if phase=="development"
                     else cal["selectionEnd"])
                if exit_at>=end:
                    counters[name][phase]["crossesPhaseBoundary"]+=1
                    continue
                if any(at not in observed for at in range(entry,exit_at+M5,M5)):
                    counters[name][phase]["futureM5SourceGapNoImputation"]+=1
                    continue
                output[name][phase].append(dict(symbol=symbol,week=(t-cal["start"])//WEEK,
                    clock=t,entry=entry,exit=exit_at,side=side,benchmarkSide=momentum))
                counters[name][phase]["completeSourceOpportunity"]+=1
    return output,counters


def score(rows,price_maps,costs,first_week,count):
    """Costed source-close PROXY; equal-asset within week; zero-signal weeks zero."""
    events=[]
    cells=defaultdict(list)
    for r in rows:
        q=costs[r["symbol"]]
        p0=price_maps[r["symbol"]][r["entry"]]
        p1=price_maps[r["symbol"]][r["exit"]]
        require(p0>0 and p1>0,"NONPOSITIVE_SOURCE_OUTCOME")
        gross=r["side"]*10000*math.log(p1/p0)
        bench_gross=r["benchmarkSide"]*10000*math.log(p1/p0)
        bench_net=bench_gross-(q["adverseBps"] if r["benchmarkSide"] else 0.)
        values=dict(grossBps=gross,centralNetBps=gross-q["centralBps"],
                    adverseNetBps=gross-q["adverseBps"],
                    stressNetBps=gross-q["stressBps"],
                    incrementalVsFourHourMomentumAdverseBps=
                        gross-q["adverseBps"]-bench_net)
        events.append(values)
        cells[(r["week"],r["symbol"])].append(values)
    byweek={key:[] for key in METRICS}
    for w in range(first_week,first_week+count):
        groups=[xs for (wk,symbol),xs in cells.items() if wk==w]
        for key in METRICS:
            byweek[key].append(mean(mean(e[key] for e in xs) for xs in groups)
                               if groups else 0.)
    signalavg={key:mean(e[key] for e in events) if events else None for key in METRICS}
    weekavg={key:mean(byweek[key]) for key in METRICS}
    return dict(signals=len(events),activeWeeks=len({x["week"] for x in rows}),
                activeSymbols=len({x["symbol"] for x in rows}),
                meanSourceProxyPerSignalBps=signalavg,
                equalCalendarWeekMeanBps=weekavg,
                weeks=byweek)


def hac_lower(values,alpha_family=.05,comparisons=6,lags=3):
    n=len(values)
    if n<3 or stdev(values)<=0 or any(not math.isfinite(x) for x in values):
        return None
    avg=mean(values)
    centered=[x-avg for x in values]
    longvar=sum(x*x for x in centered)/n
    for lag in range(1,lags+1):
        autocov=sum(centered[i]*centered[i-lag] for i in range(lag,n))/n
        longvar+=2*(1-lag/(lags+1))*autocov
    se=max(stdev(values)/math.sqrt(n),math.sqrt(max(0,longvar)/n))
    return avg-NormalDist().inv_cdf(1-alpha_family/comparisons)*se


def cost_eligible(protocol,source_bars,contexts,hourly):
    allcost=cost_context(contexts)
    ep=protocol["eligibility"]
    selected={}
    reasons={}
    for symbol in protocol["source"]["sourceSymbols"]:
        q=allcost.get(symbol,{})
        why=[]
        development=protocol["clock"]
        n_h1_dev=sum(development["start"]<=t<development["developmentEnd"]
                     for t in hourly[symbol])
        if n_h1_dev<ep["minOriginalDevelopmentH1BarsEach"]:
            why.append("INSUFFICIENT_COMPLETE_DEVELOPMENT_H1")
        if q.get("observed",0)<ep["minQuoteCostContextsEach"]:
            why.append("AUTHENTIC_QUOTE_COST_CONTEXTS_INSUFFICIENT")
        if not (isinstance(q.get("minimumMarginEur"),(int,float)) and
                math.isfinite(q["minimumMarginEur"]) and
                0<q["minimumMarginEur"]<300):
            why.append("UNKNOWN_OR_UNFINANCEABLE_CURRENT_MINIMUM_MARGIN")
        if not (isinstance(q.get("minimumNotionalEur"),(int,float)) and
                math.isfinite(q["minimumNotionalEur"]) and
                q["minimumNotionalEur"]>0):
            why.append("MINIMUM_NOTIONAL_UNKNOWN")
        if any(not (isinstance(q.get(k),(int,float)) and math.isfinite(q[k])
                    and q[k]>0) for k in ("centralBps","adverseBps","stressBps")):
            why.append("CURRENT_ROUNDTRIP_COST_UNKNOWN")
        reasons[symbol]=why
        if not why:
            selected[symbol]=q
    return selected,reasons


def run():
    original=PROTOCOL.read_bytes()
    p=json.loads(original)
    cal=p["clock"];source=p["source"]
    require(p["id"]=="CPF1" and p["locked"] and
        p["status"]=="PREDECLARED_UNSCORED" and
        p["finance"]["prospectiveInitialCapitalEur"]==300 and
        p["security"]["prohibitedLiveDemoOrders"] and
        p["security"]["noTokenRefresh"],"LOCKED_OWNER_POLICY")
    require(cal["developmentEnd"]-cal["start"]==26*WEEK and
            cal["selectionEnd"]-cal["developmentEnd"]==13*WEEK and
            cal["end"]-cal["selectionEnd"]==13*WEEK and
            cal["utcHours"]==[8,12,16] and
            cal["holdMinutes"]==60 and
            len(p["families"])==len(FAMILIES)==3 and
            [row["id"] for row in p["families"]]==list(FAMILIES),
            "LOCKED_CALENDAR_FAMILY")
    manifest=json.loads(Path(source["originalManifest"]).read_text())
    require([z["run"] for z in manifest["source"]]==
            source["originalAuthenticatedSealedRuns"],"ORIGINAL_SOURCE_MANIFEST")
    all_bars={};contexts=[];original_reconciliation=[]
    for item in manifest["source"]:
        bundle,raw_responses,proof=recover(Path(item["folder"]),item["run"],
             item["hash"],item["schema"],item["protocol"])
        require(proof and not (set(bundle["bars"]) & set(all_bars)),
                "SOURCE_CUSTODY_OR_DUPLICATE")
        all_bars.update(bundle["bars"])
        c,_=extract_costs(bundle,raw_responses)
        contexts.extend(c)
        original_reconciliation.append(dict(runId=item["run"],originalBound=True,
             sourceSymbols=len(bundle["bars"])))
    require(sum(len(x) for x in all_bars.values())==
            source["originalAuthenticatedM5BarCount"] and
            len(contexts)==source["originalAuthenticQuoteCostContexts"],
            "ORIGINAL_BAR_COST_PROVENANCE")
    require(sorted(all_bars)==sorted(source["sourceSymbols"]),
            "PREDECLARED_TWELVE_ASSETS")
    h1={symbol:h1_from_m5(rows) for symbol,rows in all_bars.items()}
    price={symbol:{int(x[1]):float(x[5]) for x in rows}
           for symbol,rows in all_bars.items()}
    selected,reasons=cost_eligible(p,all_bars,contexts,h1)
    results=dict(schema="MXM_CPF1_GENUINE_ORIGINAL_CLOUD_INDICATOR_FAMILY_RESEARCH_V1",
        runId=int(os.environ.get("GITHUB_RUN_ID","0")),
        originalLockedProtocolSha256=hashlib.sha256(original).hexdigest(),
        sourceAuthentication=original_reconciliation,
        exactOriginalM5Bars=sum(len(x) for x in all_bars.values()),
        authenticatedOriginalQuoteCostContexts=len(contexts),
        sourceH1Count={s:len(v) for s,v in h1.items()},
        eligibility={s:dict(eligible=s in selected,reasons=reasons[s],
            originalCurrentTermCostSamples=
                selected[s]["observed"] if s in selected else None,
            currentMinimumMarginEur=
                selected[s]["minimumMarginEur"] if s in selected else None,
            centralModeledCostBps=
                selected[s]["centralBps"] if s in selected else None,
            adverseModeledCostBps=
                selected[s]["adverseBps"] if s in selected else None,
            stressModeledCostBps=
                selected[s]["stressBps"] if s in selected else None)
            for s in source["sourceSymbols"]},
        financiallyObservableSymbols=sorted(selected),
        sourceWeeksGloballyExposed=52,
        independentConfirmation=False,previousClosedStudiesCalled=0,
        authenticatedNewBrokerRequests=0,refreshTokenConsumed=False,
        cloudActivated=False,ordersSubmitted=0,
        historicalActualFillsVerified=False,
        conditionalModelNetEur=None,nativeCSharpFundedClosedTrips=0,
        hard21SystemProven=False,globalFloatingDrawdown30Certified=False,
        families={},selectionPromotableGroups=[],
        sourceUnscoredAuditWeeks=13,auditOutcomeScored=False)
    if len(selected)<p["eligibility"]["minimumEligibleSourceSymbolsForFamilyScreen"]:
        results["verdict"]="SOURCE_COST_PREFLIGHT_NO_ELIGIBLE_ORIGINAL_SYMBOL"
    else:
        proposed,counts=candidate_source_events(p,h1,price,sorted(selected))
        for name in FAMILIES:
            dev=score(proposed[name]["development"],price,selected,0,26)
            entry=dict(sourceCounters={stage:dict(counts[name][stage])
                        for stage in ("development","selection")},
                       sourceEligibleSignalsByStage={
                           stage:len(proposed[name][stage])
                           for stage in ("development","selection")},
                       selectionOutcomeInspected=False,
                       development={k:v for k,v in dev.items() if k!="weeks"},
                       f2DevelopmentFutility=None,selection=None)
            f2=prospective_economic_futility(
                dev["weeks"]["adverseNetBps"],
                dev["weeks"]["incrementalVsFourHourMomentumAdverseBps"],
                model_cost_context_complete=True,
                predeclared_comparisons=p["statistics"]["wholeProgramOneSidedComparisons"],
                active_development_weeks=dev["activeWeeks"],
                required_incremental_surplus_bps=0.,alpha_family=.05,hac_lags=3)
            entry["f2DevelopmentFutility"]=f2
            if not f2.get("scoreSelectionAllowed",False):
                entry["verdict"]="CLOSED_EXACT_DEVELOPMENT_F2_FUTILITY_OR_UNINFORMATIVE"
            else:
                selection=score(proposed[name]["selection"],price,selected,26,13)
                netlower=hac_lower(selection["weeks"]["adverseNetBps"])
                inclower=hac_lower(
                    selection["weeks"]["incrementalVsFourHourMomentumAdverseBps"])
                supported=(netlower is not None and inclower is not None and
                           netlower>0 and inclower>0)
                entry["selection"]={k:v for k,v in selection.items() if k!="weeks"}
                entry["selection"].update(dict(
                    BonferroniHacAdverseNetLowerBps=netlower,
                    BonferroniHacIncrementalVsMomentumLowerBps=inclower,
                    exploratorySupport=supported,
                    actualBrokerFundedNetEur=None,
                    independentConfirmation=False))
                entry["selectionOutcomeInspected"]=True
                entry["verdict"]=("EXPLORATORY_CONDITIONAL_SELECTION_SUPPORT_NEEDS_CSHARP_PARITY"
                                   if supported else
                                   "CLOSED_EXACT_SELECTION_NO_ADVERSE_BENCHMARK_SUPPORT")
                if supported:
                    results["selectionPromotableGroups"].append(name)
            results["families"][name]=entry
        results["verdict"]=("EXPLORATORY_SELECTION_SUPPORT_NOT_PRODUCT_QUALIFIED"
                 if results["selectionPromotableGroups"] else
                 "ALL_THREE_EXACT_FAMILIES_CLOSED_WITHOUT_CSHARP_PROMOTION")
    Path("cpf1-authentic-public.json").write_text(json.dumps(results,
        sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    overview=dict(runId=results["runId"],
         authenticM5=results["exactOriginalM5Bars"],
         originalCostContexts=results["authenticatedOriginalQuoteCostContexts"],
         eligibleSymbols=results["financiallyObservableSymbols"],
         groups={k:dict(verdict=v["verdict"],
                 development=v["development"],
                 f2=v["f2DevelopmentFutility"],
                 selection=v["selection"])
                 for k,v in results["families"].items()},
         selectionPromotableGroups=results["selectionPromotableGroups"],
         verdict=results["verdict"],orders=0)
    print("CPF1_AUTHENTIC_RESEARCH "+json.dumps(overview,
        separators=(",",":"),sort_keys=True),flush=True)


if __name__=="__main__":
    run()

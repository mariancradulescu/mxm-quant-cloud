"""LFX1 one fixed London-fixing economic hypothesis. A registered source-only program.

No HRC1, TWC1, PVE or closed model called. Entire pre-scoring source
coverage/financial-power pilot executes before any predictor/selection outcome.
Returns are read only as development-only unsigned/orientation-agnostic noise
for the pilot; selection is never inspected on a failing pilot.
"""
from collections import defaultdict
from datetime import datetime,timedelta,timezone
from statistics import mean,stdev,NormalDist
from zoneinfo import ZoneInfo
from pathlib import Path
import hashlib,json,math,os
from .multiscale_conditional_research import recover,extract_costs
from .integrated_predictive_funded import cost_context
M5=300000;H=3600000;W=604800000
P=Path("research/lfx1_protocol.json")
def ok(x,why):
    if not x:raise ValueError("LFX1_"+why)
def phase(t,c):
    return "development" if t<c["developmentEnd"] else "selection" if t<c["selectionEnd"] else "exposed"
def candidate_clocks(c):
    start=datetime.fromtimestamp(c["start"]/1000,timezone.utc).date()
    finish=datetime.fromtimestamp(c["end"]/1000,timezone.utc).date()
    d=start
    while d<=finish:
        if d.weekday()<5:
            local=datetime(d.year,d.month,d.day,16,tzinfo=ZoneInfo("Europe/London"))
            t=int(local.timestamp()*1000)
            if c["start"]<=t<c["end"]:yield t
        d+=timedelta(days=1)
def time_rows(bars,p):
    e=p["eligibility"];cal=p["calendar"];symbols=p["source"]["universe"]
    clocks=list(candidate_clocks(cal));views={s:{int(x[1]):x for x in bars[s]} for s in symbols}
    complete=defaultdict(list);stats=defaultdict(lambda:defaultdict(int))
    for t in clocks:
        w=(t-cal["start"])//W;stage=phase(t,cal)
        cutoff=cal["developmentEnd"] if stage=="development" else cal["selectionEnd"] if stage=="selection" else cal["end"]
        for s in symbols:
            v=views[s]
            if not all(t-j*M5 in v for j in range(e["causalLookbackHours"]*12+1)):
                stats[(stage,w)]["noHistory"]+=1;continue
            stats[(stage,w)]["features"]+=1
            if t+M5+e["holdingMinutes"]*60000>=cutoff or not all(
                t+j*M5 in v for j in range(1,2+e["holdingMinutes"]//5)):
                stats[(stage,w)]["noFutureLabel"]+=1;continue
            complete[t].append((s,w,stage))
    records=defaultdict(list)
    for t,rs in complete.items():
        if len(rs)<e["minSimultaneousAssets"]:
            for s,w,stage in rs:stats[(stage,w)]["notSimultaneous"]+=1
            continue
        for s,w,stage in rs:
            records[stage].append((t,s,w))
            stats[(stage,w)]["ready"]+=1
    return records,stats,views
def screen(p,records,stats,views,cost):
    e=p["eligibility"];sci=p["scientific"];symbols=p["source"]["universe"]
    dev=records["development"];sel=records["selection"]
    dw=sorted({w for t,s,w in dev});sw=sorted({w for t,s,w in sel})
    reasons=[]
    def block(condition,why):
        if condition:reasons.append(why)
    block(len(dw)<e["minimumDevelopmentInformativeWeeks"],"DEVELOPMENT_WEEKS_BELOW_PROTOCOL")
    block(len(sw)<e["minimumSelectionInformativeWeeks"],"SELECTION_WEEKS_BELOW_PROTOCOL")
    block(len(dev)<e["minimumDevelopmentOpportunities"],"DEVELOPMENT_ELIGIBLE_OBSERVATIONS_TOO_FEW")
    block(len(sel)<e["minimumSelectionOpportunities"],"SELECTION_ELIGIBLE_OBSERVATIONS_TOO_FEW")
    missing=[x for x in symbols if x not in cost or cost[x]["observed"]<3
             or cost[x]["minimumNotionalEur"]<=0 or cost[x]["minimumMarginEur"]<=0
             or not math.isfinite(cost[x]["adverseBps"]) or cost[x]["adverseBps"]<=0]
    block(bool(missing),"AUTHENTIC_FX_COST_OR_MINIMUM_CONTRACT_INCOMPLETE")
    margin=sum(cost[x]["minimumMarginEur"] for x in symbols if x in cost)
    block(margin>p["financial"]["initialCashEur"],"FIVE_SIMULTANEOUS_MINIMUM_MARGINS_EXCEED_EUR300")
    pilot={}
    if not any(z.endswith("TOO_FEW") or z=="AUTHENTIC_FX_COST_OR_MINIMUM_CONTRACT_INCOMPLETE" for z in reasons):
        byweek=defaultdict(list)
        # Pilot target variance is UNCONDITIONAL and has no predictor features,
        # direction, benchmark, cost-adjusted alpha or selection outcomes.
        for t,s,w in dev:
            entry=views[s][t+M5][5]
            out=views[s][t+M5+e["holdingMinutes"]*60000][5]
            ok(entry>0 and out>0,"NONPOSITIVE_PILOT_PRICE")
            byweek[w].append(10000*math.log(out/entry))
        weekly=[mean(v) for w,v in sorted(byweek.items())]
        sigma=stdev(weekly) if len(weekly)>1 else None
        n=min(len(sw),(p["calendar"]["selectionEnd"]-p["calendar"]["developmentEnd"])//W)
        threshold=1.25*max(cost[s]["adverseBps"] for s in symbols)
        z=NormalDist().inv_cdf(1-sci["alphaFamily"]/sci["oneSidedComparisons"])+NormalDist().inv_cdf(sci["powerTarget"])
        mde=z*sigma/math.sqrt(n) if sigma is not None and n>=2 else None
        pilot=dict(developmentUnconditionalWeeklyNoiseSdBps=sigma,
                   selectionEffectiveWeeksUpperBound=n,
                   economicallyRelevantEffectBps=threshold,
                   modeledAdverseRoundTripBySymbolBps={s:cost[s]["adverseBps"] for s in symbols},
                   mdeProxyBps=mde,
                   noiseModelCaveat="weekly all-long return covariance proxy, NOT the contrarian signed-outcome variance")
        block(mde is None or mde>threshold,"DEVELOPMENT_PILOT_POWER_PROXY_EXCEEDS_ECONOMIC_EFFECT")
    return dict(passPreScoring=len(reasons)==0,reasons=reasons,
        developmentInformativeWeeks=len(dw),selectionInformativeWeeks=len(sw),
        developmentLabelReady=len(dev),selectionLabelReady=len(sel),
        currentMinimumMarginAllFiveEur=margin,
        costsFromCurrentHistoricalDevelopmentQuotesNotPerFill=True,pilot=pilot,
        missingCostSymbols=missing)
def score(p,records,views,cost):
    e=p["eligibility"];cal=p["calendar"]
    result={}
    for stage in ("development","selection"):
        observations=[];weekly=defaultdict(list)
        for t,s,w in records[stage]:
            v=views[s];past=v[t-4*H][5];now=v[t][5]
            if past==now:continue
            side=-1 if now>past else +1
            entry=v[t+M5][5];out=v[t+M5+e["holdingMinutes"]*60000][5]
            outcome=10000*math.log(out/entry)
            gross=side*outcome;baseline=-gross
            z=dict(gross=gross,baseline=baseline,
                   central=gross-cost[s]["centralBps"],
                   adverse=gross-cost[s]["adverseBps"],
                   againstMomentum=2*gross)
            observations.append(z);weekly[w].append(z)
        means={k:mean(o[k] for o in observations) if observations else None for k in
               ("gross","baseline","central","adverse","againstMomentum")}
        weeks=sorted(weekly)
        weekly_adverse=[mean(y["adverse"] for y in weekly[w]) for w in weeks]
        weekly_increment=[mean(y["againstMomentum"] for y in weekly[w]) for w in weeks]
        z=NormalDist().inv_cdf(1-p["scientific"]["alphaFamily"]/p["scientific"]["oneSidedComparisons"])
        def lower(xs):
            return mean(xs)-z*stdev(xs)/math.sqrt(len(xs)) if len(xs)>1 else None
        result[stage]=dict(completeDirectionalEpisodes=len(observations),eligibleWeeks=len(weeks),
            meanBps=means,selectionWeeklyAdverseLowerBps=lower(weekly_adverse) if stage=="selection" else None,
            selectionWeeklyIncrementalMomentumLowerBps=lower(weekly_increment) if stage=="selection" else None,
            weeklyCompleteEpisodes=[len(weekly[w]) for w in weeks],
            returnSamplesNotIndependent=True)
    selection=result["selection"];a=selection["selectionWeeklyAdverseLowerBps"];b=selection["selectionWeeklyIncrementalMomentumLowerBps"]
    supported=bool(a is not None and b is not None and a>0 and b>0)
    return dict(phases=result,positiveAfterAdverseAndBothBenchmarks=supported,
        eligibleForNativeFundingFollowup=supported,
        nativeFundedLedgerExecuted=False,
        fundedNetEur=None,
        financialStatus="UNQUALIFIED_NO_EXECUTION_QUOTES_OR_NATIVE_FILLS",
        independentConfirmation=False)
def run():
    original=P.read_bytes();p=json.loads(original)
    ok(p["id"]=="LFX1" and p["status"]=="REGISTERED_UNSCORED" and p["financial"]["initialCashEur"]==300
       and p["source"]["originalSourceGloballyExposed"] and p["locked"],"REGISTERED_POLICY")
    base=json.loads(Path("research/hrc1_protocol.json").read_text())
    ok(tuple(p["source"]["runs"])==tuple(x["run"] for x in base["source"]),"ORIGINAL_SOURCE_EXPECTATION")
    bars={};costs=[]
    for item in base["source"]:
        b,decoded,auth=recover(Path(item["folder"]),item["run"],item["hash"],item["schema"],item["protocol"])
        ok(auth,"ORIGINAL_AUTHENTICATION")
        ok(not (set(b["bars"]) & set(bars)),"DUPLICATE_SOURCE")
        bars.update(b["bars"])
        c,_=extract_costs(b,decoded);costs.extend(c)
    frozen=json.loads(Path("docs/HRC1_AUTHENTIC_PILOT.json").read_text())
    ok(sum(map(len,bars.values()))==frozen["rawSourceBars"] and len(costs)==frozen["originalCostContexts"],"HISTORIC_SOURCE_INTEGRITY")
    # The new program has its OWN five-FX economic rationale, but the 12
    # original encrypted source symbols remain present and immutable.
    cost=cost_context(costs)
    records,stats,views=time_rows(bars,p)
    preflight=screen(p,records,stats,views,cost)
    score_report=score(p,records,views,cost) if preflight["passPreScoring"] else None
    week_rows=[]
    for (stage,w),x in sorted(stats.items()):
        week_rows.append(dict(stage=stage,week=w,**x))
    report=dict(schema="MXM_LFX1_AUTHENTIC_ECONOMIC_SOURCE_V1",study="LFX1",
       sourceRuns=p["source"]["runs"],sourceAuthenticated=True,
       originalM5Bars=sum(map(len,bars.values())),sourceCostContexts=len(costs),
       protocolSha256=hashlib.sha256(original).hexdigest(),workflowRunId=int(os.environ.get("GITHUB_RUN_ID","0")),
       noClosedStudyCalls=True,sourceAllGloballyExposed=True,auditOutcomesNeverScored=True,
       candidateByClockWithMatchedM5Labels=week_rows,
       preflight=preflight,scored=score_report,
       selectionViewed=score_report is not None,independentConfirmation=False,
       ordersSubmitted=0,cloudActivated=False,brokerRequests=0,
       finalCapitalEur=None,hard21Certified=False,
       continuousFloatingDrawdownCertified=False,
       brokerReconciled=False)
    Path("lfx1-authentic-public.json").write_text(json.dumps(report,separators=(",",":"),sort_keys=True,allow_nan=False)+"\n")
    print("LFX1_AUTHENTIC "+json.dumps({k:v for k,v in report.items() if k in
        ("workflowRunId","sourceAuthenticated","originalM5Bars","sourceCostContexts","preflight","scored",
         "selectionViewed","brokerRequests","ordersSubmitted")},sort_keys=True),flush=True)
    print("LFX1_WEEKS "+json.dumps(week_rows,separators=(",",":"),sort_keys=True),flush=True)
if __name__=="__main__":run()

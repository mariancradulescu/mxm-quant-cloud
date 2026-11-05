"""New HRC1 authenticated, prespecified development-power pilot.

Never calls PVE1/PVE2 score, closed algorithms, Python Book, broker API or orders.
Select only if development-only power/support gate passes, otherwise no selection
price/return is inspected. Last 13 weeks stay entirely unscored and exposed.
"""
import hashlib,json,math,os
from collections import defaultdict
from pathlib import Path
from statistics import mean,stdev,NormalDist
from .multiscale_conditional_research import recover,extract_costs
from .integrated_predictive_funded import cost_context

PROTOCOL=Path("research/hrc1_protocol.json")
HOUR=3600000;M5=300000;WEEK=604800000

def side(returns,threshold=.2):
    if len(returns)!=21 or any(not math.isfinite(x) for x in returns):
        return 0
    left=returns[:-1];right=returns[1:]
    m1=mean(left);m2=mean(right)
    num=sum((a-m1)*(b-m2) for a,b in zip(left,right))
    den=math.sqrt(sum((a-m1)**2 for a in left)*sum((b-m2)**2 for b in right))
    if den<=0 or returns[-1]==0:return 0
    r=num/den
    return (1 if returns[-1]>0 else -1)*(1 if r>threshold else -1 if r< -threshold else 0)

def feature(rows,t):
    # Complete H1 price path only: every underlying 5-minute source
    # timestamp must exist, not just the two hourly endpoints.
    if any(t-k*M5 not in rows for k in range(21*12+1)):return None
    clocks=[t-i*HOUR for i in range(21,-1,-1)]
    prices=[rows[x][5] for x in clocks]
    if min(prices)<=0:return None
    returns=[math.log(y/x) for x,y in zip(prices,prices[1:])]
    return side(returns), (1 if returns[-1]>0 else -1 if returns[-1]<0 else 0)

def phase_stats(bars,cost,begin,end,p):
    weekly=defaultdict(lambda:defaultdict(list));active=defaultdict(set)
    known=signals=unknown=0
    totalBars=0
    for symbol in p["sourceSymbols"]:
        indexed={int(row[1]):row for row in bars[symbol]};totalBars+=len(indexed)
        fee=cost[symbol]["adverseBps"]
        if fee<0 or not math.isfinite(fee):raise ValueError("HRC1_COST_CONTRACT_INVALID")
        for t in sorted(k for k in indexed if begin+21*HOUR<=k<end-(65*60000) and k%HOUR==0):
            state=feature(indexed,t)
            if state is None or state[1]==0:continue
            decision,baseline=state
            # Delayed entry/exit and all intermediate M5 prices are required.
            entry=t+M5;exit=entry+60*60000
            if any(z not in indexed for z in range(entry,exit+M5,M5)):
                unknown+=1;continue
            p0=indexed[entry][5];p1=indexed[exit][5]
            if p0<=0 or p1<=0:raise ValueError("HRC1_NONPOSITIVE_LABEL")
            outcome=10000*math.log(p1/p0)
            signed=decision*outcome if decision else 0.
            benchmark=baseline*outcome
            increment=signed-benchmark
            incrementalNet=increment+fee*(1 if not decision else 0)
            week=int((t-p["calendar"]["start"])//WEEK)
            weekly[week][symbol].append((increment,incrementalNet))
            known+=1
            if decision:signals+=1;active[week].add(symbol)
    rows=[];eligible=[]
    week0=(begin-p["calendar"]["start"])//WEEK
    for w in range(week0,week0+(end-begin)//WEEK):
        assets=weekly[w]
        if len(assets)<p["scientific"]["minSymbolCoverageInWeek"]:continue
        inc=mean(mean(x[0] for x in items) for items in assets.values())
        net=mean(mean(x[1] for x in items) for items in assets.values())
        rows.append(dict(week=w,assetCoverage=len(assets),incrementalGrossBps=inc,
                         modeledIncrementalAdverseBps=net,activeAssets=len(active[w])))
        if active[w]:eligible.append(w)
    return dict(knownCompleteLabels=known,activeSignals=signals,missingFutureOutcomes=unknown,
       informativeActiveWeeks=len(eligible),completeAssetWeeks=len(rows),weekly=rows,
       bars=totalBars)

def run():
    p=json.loads(PROTOCOL.read_text())
    if p["id"]!="HRC1" or p["status"]!="REGISTERED_UNSCORED" or p["initialCapitalEur"]!=300 or Path("docs/HRC1_AUTHENTIC_PILOT.json").exists():
        raise ValueError("HRC1_STUDY_ALREADY_FROZEN_OR_POLICY_MISMATCH")
    bars={};costs=[];proven=[]
    for item in p["source"]:
        b,decoded,authenticated=recover(Path(item["folder"]),item["run"],item["hash"],item["schema"],item["protocol"])
        if not authenticated:raise ValueError("HRC1_ORIGINAL_AUTHENTICATION_FAIL")
        for sym,rows in b["bars"].items():
            if sym in bars:raise ValueError("HRC1_DUPLICATE_SOURCE")
            bars[sym]=rows
        c,_=extract_costs(b,decoded);costs.extend(c);proven.append(item["run"])
    if set(bars)!=set(p["sourceSymbols"]) or len(costs)!=166 or sum(map(len,bars.values()))!=836087:
        raise ValueError("HRC1_AUTHENTIC_SOURCE_CONTEXT_MISMATCH")
    fee=cost_context(costs)
    if set(fee)!=set(bars):raise ValueError("HRC1_MISSING_CURRENT_TERM_CONTEXT")
    cal=p["calendar"]
    dev=phase_stats(bars,fee,cal["start"],cal["developmentEnd"],p)
    informative=dev["informativeActiveWeeks"]
    # Development observations and their variance estimate support only
    # a hypothesis about selection power; overlapping clocks are NOT trials.
    vals=[x["incrementalGrossBps"] for x in dev["weekly"] if x["activeAssets"]>0]
    projected=min(cal["selectionWeeks"],informative//2)
    sigma=stdev(vals) if len(vals)>1 else None
    z=NormalDist().inv_cdf(1-p["scientific"]["familywiseAlpha"]/p["scientific"]["oneSidedComparisons"])+NormalDist().inv_cdf(p["scientific"]["powerTarget"])
    mde=z*sigma/math.sqrt(projected) if sigma is not None and projected>=2 else None
    passPilot=(informative>=p["scientific"]["minInformativeDevelopmentWeeks"] and
        dev["activeSignals"]>=p["scientific"]["minDevelopmentSignalsWithLabels"] and
        projected>=p["scientific"]["minSelectionEquivalentEffectiveWeeks"] and
        mde is not None and mde<=p["scientific"]["requiredEconomicallyDetectableEffectBps"])
    reasons=[]
    if informative<p["scientific"]["minInformativeDevelopmentWeeks"]:reasons.append("DEVELOPMENT_INFORMATIVE_WEEKS_TOO_FEW")
    if dev["activeSignals"]<p["scientific"]["minDevelopmentSignalsWithLabels"]:reasons.append("DEVELOPMENT_SIGNAL_COUNT_TOO_FEW")
    if projected<p["scientific"]["minSelectionEquivalentEffectiveWeeks"]:reasons.append("SELECTION_EFFECTIVE_WEEKS_TOO_FEW")
    if mde is None or mde>p["scientific"]["requiredEconomicallyDetectableEffectBps"]:reasons.append("MIN_DETECTABLE_EFFECT_EXCEEDS_ECONOMIC_THRESHOLD")
    # Selection is observed ONLY after a successful development-only gate.
    selection=phase_stats(bars,fee,cal["developmentEnd"],cal["selectionEnd"],p) if passPilot else None
    report=dict(schema="HRC1_AUTHENTIC_DEV_PREFLIGHT_V1",study="HRC1",
        sourceRuns=proven,sourceAuthenticated=True,rawSourceBars=sum(map(len,bars.values())),
        sourceAssets=len(bars),originalCostContexts=len(costs),
        prescoringProtocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        workflowRunId=int(os.environ.get("GITHUB_RUN_ID","0")),development=dev,
        projectedEffectiveSelectionWeeks=projected,developmentWeeklyStdBps=sigma,
        requiredEconomicEffectBps=p["scientific"]["requiredEconomicallyDetectableEffectBps"],
        detectableEffectBps=mde,developmentPilotPassed=passPilot,blockReasons=reasons,
        selectionNotViewedUnlessPilotPassed=selection is None,selection=selection,
        globallyExposedAuditNotScored=True,allSourceWeeksGloballyExposed=True,
        independentConfirmation=False,financialNativeLedgerUsed=False,
        fundedNetEur=None,hard21Proven=False,continuousDDCertified=False,
        ordersSubmitted=0,brokerRequests=0,cloudActivated=False)
    Path("hrc1-authentic-pilot-public.json").write_text(json.dumps(report,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n")
    print("HRC1_AUTHENTIC_DEV_PILOT "+json.dumps(dict(runId=report["workflowRunId"],
        sourceBars=report["rawSourceBars"],assets=report["sourceAssets"],
        developmentSignals=dev["activeSignals"],developmentInformativeWeeks=informative,
        projectedEffectiveSelectionWeeks=projected,mdeBps=mde,
        pilotPassed=passPilot,selectionScored=selection is not None,
        qualification=False,blockReasons=reasons),sort_keys=True),flush=True)

if __name__=="__main__":run()

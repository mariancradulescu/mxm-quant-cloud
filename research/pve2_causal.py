"""PVE2 fixed daily-direction/H1-pullback research on authenticated Pepperstone M5.

No closed strategy is called, no outcome-derived direction is fitted, no new
broker requests, no historical fill is invented. All 52 weeks are exposed.
"""
import hashlib
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from statistics import mean
from .multiscale_conditional_research import recover,extract_costs
from .integrated_predictive_funded import market_view,cost_context

PROTOCOL=Path("research/pve2_protocol.json")
M5=300000
H=3600000
WEEK=7*24*H
HORIZONS=(60,240)

def need(ok,why):
    if not ok:raise ValueError("PVE2_"+why)

def phase(t,p):
    c=p["calendar"]
    if t<c["developmentEnd"]:return "development",c["developmentEnd"]
    if t<c["selectionEnd"]:return "selection",c["selectionEnd"]
    if t<c["end"]:return "globally_exposed_audit",c["end"]
    return None,None

def _beta_cf(a,b,x):
    # Continued fraction for regularized incomplete beta. No scipy dependency.
    qab=a+b;qap=a+1;qam=a-1
    c=1.;d=1.-qab*x/qap
    if abs(d)<1e-300:d=1e-300
    d=1./d;h=d
    for m in range(1,300):
        m2=2*m
        aa=m*(b-m)*x/((qam+m2)*(a+m2))
        d=1.+aa*d
        if abs(d)<1e-300:d=1e-300
        c=1.+aa/c
        if abs(c)<1e-300:c=1e-300
        d=1./d;h*=d*c
        aa=-(a+m)*(qab+m)*x/((a+m2)*(qap+m2))
        d=1.+aa*d
        if abs(d)<1e-300:d=1e-300
        c=1.+aa/c
        if abs(c)<1e-300:c=1e-300
        d=1./d;delta=d*c;h*=delta
        if abs(delta-1.)<3e-13:break
    return h

def _beta_i(a,b,x):
    if x<=0:return 0.
    if x>=1:return 1.
    bt=math.exp(math.lgamma(a+b)-math.lgamma(a)-math.lgamma(b)
                +a*math.log(x)+b*math.log1p(-x))
    if x<(a+1)/(a+b+2):
        return bt*_beta_cf(a,b,x)/a
    return 1.-bt*_beta_cf(b,a,1.-x)/b

def one_sided_weekly_t(x):
    """Conservative one-sided Student t on week clusters, never on M5 rows."""
    if len(x)<3:return 1.
    mu=mean(x)
    if mu<=0:return 1. if mu==0 else max(.5,1.-one_sided_weekly_t([-v for v in x]))
    variance=sum((v-mu)**2 for v in x)/(len(x)-1)
    if variance<=0:return 1. # zero variance does not invent statistical power
    t=mu/math.sqrt(variance/len(x))
    nu=len(x)-1
    return min(1.,max(0.,.5*_beta_i(nu/2.,.5,nu/(nu+t*t))))

def causal_state(rows,t):
    """Exact past 13 consecutive completed M5 closes, plus t-24h endpoint."""
    hour=[rows.get(t-i*M5) for i in range(13)]
    day=rows.get(t-24*H)
    if day is None or any(x is None for x in hour):return None
    if min(x[5] for x in hour)<=0 or day[5]<=0:return None
    hr=math.log(hour[0][5]/hour[-1][5])
    d=math.log(hour[0][5]/day[5])
    if d==0:return None # benchmark also needs a nonzero causal side
    side=1 if d>0 else -1
    pulled=hr!=0 and d*hr<0 and abs(d)>abs(hr)
    return dict(side=side,pullback=pulled,dayBps=d*10000,hourBps=hr*10000)

def _weekly_equal_asset(rows,p,metric):
    week_assets=defaultdict(lambda:defaultdict(list))
    for r in rows:
        week_assets[r["week"]][r["symbol"]].append(r[metric])
    nweek=p["calendar"]["phaseWeeks"][1]
    if rows:
        phase_name=rows[0]["phase"]
        base=0 if phase_name=="development" else 26 if phase_name=="selection" else 39
        nweek=26 if phase_name=="development" else 13
    else:
        base=0
    series=[]
    asset_counts=[]
    for w in range(base,base+nweek):
        groups=week_assets.get(w,{})
        asset_counts.append(len(groups))
        if len(groups)>0:
            series.append(mean(mean(v) for v in groups.values()))
    return series,asset_counts

def summarize(rows,p,costs):
    # Every known eligible completed label belongs in exactly one row.
    result=dict(known=len(rows),signals=sum(r["signal"] for r in rows),
        weeksWithAtLeast8Assets=0,weeklyGrossMeanBps=None,weeklyGrossVsDailyBps=None,
        weeklyAdverseNetMeanBps=None,weeklyAdverseNetVsDailyBps=None,
        grossP=1.,incrementalP=1.,centralNetMeanBps=None,stressNetMeanBps=None,
        meanSignalGrossBps=None,assetCoverageByWeek=[])
    if not rows:return result
    keys=("gross","incrementalGross","adverseNet","incrementalAdverse","centralNet","stressNet")
    weekly={k:_weekly_equal_asset(rows,p,k)[0] for k in keys}
    coverage=_weekly_equal_asset(rows,p,"gross")[1]
    result["weeksWithAtLeast8Assets"]=sum(n>=8 for n in coverage)
    result["assetCoverageByWeek"]=coverage
    means={k:mean(v) if v else None for k,v in weekly.items()}
    result["weeklyGrossMeanBps"]=means["gross"]
    result["weeklyGrossVsDailyBps"]=means["incrementalGross"]
    result["weeklyAdverseNetMeanBps"]=means["adverseNet"]
    result["weeklyAdverseNetVsDailyBps"]=means["incrementalAdverse"]
    result["centralNetMeanBps"]=means["centralNet"]
    result["stressNetMeanBps"]=means["stressNet"]
    result["grossP"]=one_sided_weekly_t(weekly["gross"])
    result["incrementalP"]=one_sided_weekly_t(weekly["incrementalGross"])
    signals=[r["gross"] for r in rows if r["signal"]]
    result["meanSignalGrossBps"]=mean(signals) if signals else None
    return result

def score(bars,p,cost):
    markets={s:{int(x[1]):x for x in bars[s]} for s in p["sourceSymbols"]}
    rows=defaultdict(list)
    raw_signals=defaultdict(list)
    misses=defaultdict(int)
    missingByPhase=defaultdict(int)
    coverage={}
    for s in p["sourceSymbols"]:
        indexed=markets[s]
        observed=sorted(x for x in indexed if p["calendar"]["start"]<=x<p["calendar"]["end"] and x%(4*H)==0)
        eligible=0;features=0;signals=0
        for t in observed:
            state=causal_state(indexed,t)
            if state is None:
                misses[s+":MISSING_H1_OR_DAILY_CAUSAL_PRICE"]+=1
                continue
            features+=1
            label,boundary=phase(t,p)
            if label is None:continue
            for h in HORIZONS:
                due=t+M5+h*60000
                if due>=boundary:
                    misses[s+":"+str(h)+":CROSSES_PHASE_BOUNDARY"]+=1
                    continue
                eligible+=1
                week=(t-p["calendar"]["start"])//WEEK
                if state["pullback"] and label=="globally_exposed_audit":
                    # This proposal is built from ONLY the known source at t.
                    # Never inspect entry, future exit or model fill before offer.
                    raw_signals[h,t].append(dict(symbol=s,horizon=h,side=state["side"],
                        family="DAILY_TREND_H1_PULLBACK",knownAt=t))
                entry=indexed.get(t+M5)
                finish=indexed.get(due)
                if state["pullback"]:signals+=1
                if entry is None or finish is None:
                    misses[s+":"+str(h)+":ENTRY_OR_EXIT_UNKNOWN"]+=1
                    missingByPhase[label,h]+=1
                    continue
                if entry[5]<=0 or finish[5]<=0:raise ValueError("PVE2_NONPOSITIVE_SOURCE_CLOSE")
                r=10000*math.log(finish[5]/entry[5])
                side=state["side"]
                signal=bool(state["pullback"])
                strategy=side*r if signal else 0.
                bench=side*r
                term=cost[s]
                central=term["centralBps"]
                adverse=term["adverseBps"]
                stress=term["stressBps"]
                need(min(central,adverse,stress)>=0,"NEGATIVE_COST_CONTEXT")
                row=dict(phase=label,week=week,symbol=s,t=t,horizon=h,
                    signal=signal,side=side,rawBps=r,
                    gross=strategy,incrementalGross=strategy-bench,
                    adverseNet=strategy-adverse if signal else 0.,
                    incrementalAdverse=(strategy-adverse if signal else 0.)-(bench-adverse),
                    centralNet=strategy-central if signal else 0.,
                    stressNet=strategy-stress if signal else 0.)
                rows[label,h].append(row)
        coverage[s]=dict(m5Bars=len(indexed),decisionClocks=len(observed),
            causalFeatureClocks=features,causalSignalHorizonOpportunities=signals,
            completedEligibleHorizonClocks=eligible)
    results=[]
    selection={}
    supported=set()
    alpha=.05/4
    for h in HORIZONS:
        dev=summarize(rows["development",h],p,cost)
        sel=summarize(rows["selection",h],p,cost)
        audit=summarize(rows["globally_exposed_audit",h],p,cost)
        possible=missingByPhase["selection",h]
        sample=sel["known"]+possible
        selectionCoverage=sel["known"]/sample if sample else 0.
        minimum=p["statisticalPolicy"]
        pass_gate=(sel["known"]>0 and sel["signals"]>=minimum["minimumSelectionSignals"] and
            sel["weeksWithAtLeast8Assets"]>=minimum["minimumSelectionWeeks"] and
            selectionCoverage>=minimum["minimumKnownLabelCoverage"] and
            sel["weeklyGrossMeanBps"] is not None and sel["weeklyGrossMeanBps"]>0 and
            sel["weeklyGrossVsDailyBps"]>0 and
            sel["grossP"]<=alpha and sel["incrementalP"]<=alpha and
            sel["weeklyAdverseNetMeanBps"]>0 and sel["weeklyAdverseNetVsDailyBps"]>0)
        if pass_gate:supported.add(h)
        selection[h]=sel
        results.append(dict(horizonMinutes=h,development=dev,selection=sel,
            globallyExposedAudit=audit,selectionSupported=bool(pass_gate),
            conservativePairedLabelCoverage=selectionCoverage,
            currentTermCostsModeledNotHistorical=True))
    offers=defaultdict(list)
    for (h,t),signaled in raw_signals.items():
        if h not in supported:continue
        # Fixed pooled SELECTION expected signed gross; no asset winner, no
        # audit label in the predictor and no future-entry availability filter.
        pred=selection[h]["meanSignalGrossBps"]
        if pred is None or pred<=0:continue
        for v in signaled:offers[t].append(dict(v,predBps=pred))
    assetRows=[]
    for s in p["sourceSymbols"]:
        for h in HORIZONS:
            v=[x for x in rows["selection",h] if x["symbol"]==s]
            signalValues=[x["gross"] for x in v if x["signal"]]
            assetRows.append(dict(symbol=s,horizonMinutes=h,knownClocks=len(v),
                signals=len(signalValues),meanSignalGrossBps=mean(signalValues) if signalValues else None,
                selectedIndividually=False))
    return dict(coverage=coverage,tests=results,perAssetDescriptive=assetRows,
        selectedHorizons=sorted(supported),offers=offers,misses=dict(sorted(misses.items())),
        sourceBars=sum(len(x) for x in bars.values()),alpha=alpha,
        allWeeksGloballyExposed=True)

def source():
    p=json.loads(PROTOCOL.read_text())
    need(p["id"]=="PVE2" and p["status"]=="PREDECLARED_UNSCORED" and
        p["economicPolicy"]["initialCapitalEur"]==300,"EXACT_PREDECLARED_CAPITAL")
    need(not Path("docs/PVE2_AUTHENTIC_RESULT.json").exists(),"STUDY_ALREADY_FROZEN")
    bars={};costs=[];reception=[]
    for item in p["immutableSource"]:
        b,decoded,a=recover(Path(item["folder"]),item["run"],item["hash"],item["schema"],item["protocol"])
        for symbol,values in b["bars"].items():
            need(symbol not in bars,"DUPLICATE_AUTHENTIC_SOURCE")
            bars[symbol]=values
        c,availability=extract_costs(b,decoded)
        costs.extend(c)
        reception.append(dict(sourceRunId=item["run"],originalAuthenticated=a,
            originalCostContexts=len(c),availability=availability))
    need(set(bars)==set(p["sourceSymbols"]) and len(costs)==166,"SOURCE_UNIVERSE_OR_COST_CONTEXT")
    cost=cost_context(costs)
    need(set(cost)==set(bars),"CURRENT_TERM_COST_CONTEXT_MISSING")
    return p,bars,cost,reception

def main():
    p,bars,cost,reception=source()
    research=score(bars,p,cost)
    from .pve2_portfolio import evaluate
    economics=evaluate({s:market_view(x) for s,x in bars.items()},research["offers"],cost,p)
    receipt=dict(schema="PVE2_AUTHENTIC_DAILY_PULLBACK_GROSS_AND_CONDITIONAL_V1",
        authority=p["authority"],protocolSha256=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest(),
        runId=int(os.environ["GITHUB_RUN_ID"]),sourceReception=reception,
        originalRuns=[x["run"] for x in p["immutableSource"]],
        originalAuthenticatedM5Bars=research["sourceBars"],
        all12AssetCoverage=research["coverage"],
        preregisteredPooledTests=4,weeklyPValueBonferroniAlpha=research["alpha"],
        pooledHorizonTests=research["tests"],perAssetDescriptiveNoWinner=research["perAssetDescriptive"],
        selectedHorizons=research["selectedHorizons"],causalOmissions=research["misses"],
        commonEUR300ModelledConditionalPortfolio=economics,
        allWeeksGloballyExposed=True,independentHoldout=False,
        brokerConfirmedNetEur=None,continuousDrawdownCertified=False,
        costsAreHistoricalFills=False,closedStudiesRescored=False,
        brokerRequestsThisRun=0,ordersSubmitted=0,cloudActivated=False,
        tradingQualified=False)
    Path("pve2-authentic-public.json").write_text(json.dumps(receipt,sort_keys=True,
        separators=(",",":"),allow_nan=False)+"\n")
    print("PVE2_AUTHENTIC_PULLBACK_ECONOMICS "+json.dumps(dict(
        runId=receipt["runId"],bars=receipt["originalAuthenticatedM5Bars"],
        horizons=2,supported=len(receipt["selectedHorizons"]),
        selectionSignals=[r["selection"]["signals"] for r in receipt["pooledHorizonTests"]],
        modeledNetEur=economics["FULL"]["netClosedEur"],
        completedTrades=economics["FULL"]["modeledRoundTrips"],
        initialCapitalEur=300,certifiedNet=False,independent=False),sort_keys=True),flush=True)

if __name__=="__main__":main()

"""IPF1: causal portfolio-wide multi-resolution economic discovery.

This is a new, predeclared model on authenticated *existing* Pepperstone M5
source; it does not invoke any closed hypothesis or broker API. Future labels
update only after maturity. The shared-capital replay invokes the *existing*
native C# selector, never a Python substitute for its ranking.
"""
from bisect import bisect_right
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from math import exp,log,sqrt,tanh
import hashlib,heapq,json,os

from .multiscale_conditional_research import recover,extract_costs

P=Path("research/integrated_predictive_funded_protocol.json")
HOUR=3600000
WEEK=7*24*HOUR
DAY=24*HOUR
M5=300000
FAMS=("MULTISCALE_REPRICING","ACTIVITY_VOLATILITY_REGIME","CROSS_ASSET_RELATIVE")

def require(ok,why):
    if not ok:raise ValueError("IPF1_"+why)
def clip(v,cap):return max(-cap,min(cap,v))
def sha(data):return hashlib.sha256(data).hexdigest()
def phase(t,p):
    return ("development" if t<p["calendar"]["developmentEnd"] else
            "selection" if t<p["calendar"]["selectionEnd"] else
            "exposed_audit" if t<p["calendar"]["end"] else None)
def limit(t,p):
    for name in ("developmentEnd","selectionEnd","end"):
        v=p["calendar"][name]
        if t<v:return v
    return None

def market_view(rows):
    # Preserve actual completed M5 close at its exact clock. An absent close
    # remains missing; no forward-fill from weekend/closed-market periods.
    by5={};hours=defaultdict(list)
    for x in rows:
        require(x[1]-x[0]==M5 and x[5]>0 and x[3]>=x[4]>0, "M5_GEOMETRY")
        require(x[1] not in by5,"DUPLICATE_M5")
        by5[x[1]]=x[5]
        hour=((x[1]-1)//HOUR+1)*HOUR
        hours[hour].append(x)
    h={}
    for t,rs in hours.items():
        if len(rs)<6:continue
        rs.sort(key=lambda x:x[1])
        h[t]=(rs[0][2],max(x[3] for x in rs),min(x[4] for x in rs),
              rs[-1][5],sum(x[6] for x in rs),len(rs))
    return dict(price=by5,observed=sorted(by5),h=h,hr=sorted(h))

def window(view,t,span,minhours):
    end=view["hr"];a=bisect_right(end,t-span*HOUR);b=bisect_right(end,t)
    ts=end[a:b]
    if len(ts)<minhours:return None
    v=[view["h"][c] for c in ts]
    close=v[-1][3];start=v[0][0]
    if start<=0:return None
    rets=[]
    for i in range(1,len(ts)):
        if ts[i]-ts[i-1]==HOUR:
            rets.append(10000*log(v[i][3]/v[i-1][3]))
    if len(rets)<max(2,minhours//3):return None
    sig=sqrt(sum(x*x for x in rets)/len(rets))
    totvol=sum(x[4] for x in v)
    high=max(x[1] for x in v);low=min(x[2] for x in v)
    return dict(ret=10000*log(close/start),sig=sig,vol=totvol/len(v),
                loc=(close-low)/(high-low)-.5 if high>low else 0,
                barCount=len(v),h=high,l=low)

def features(views,t,symbol,all_data,p):
    v=views[symbol]
    z4=window(v,t,4,p["clock"]["featureMinimumObservedHours4h"])
    z24=window(v,t,24,p["clock"]["featureMinimumObservedHours24h"])
    z72=window(v,t,72,p["clock"]["featureMinimumObservedHours72h"])
    if z4 is None or z24 is None or z72 is None or t not in v["price"]:return None
    sig=max(.4,z72["sig"])
    vol4=max(0.01,z4["vol"]);vol24=max(0.01,z24["vol"])
    r4=z4["ret"]/max(1,sig*sqrt(4))
    r24=z24["ret"]/max(1,sig*sqrt(24))
    r72=z72["ret"]/max(1,sig*sqrt(72))
    act=clip(log(vol4/vol24),3)
    expansion=clip(log(max(.01,z4["sig"])/max(.01,z24["sig"])),3)
    others=[]
    for peer in ("US500","NAS100","GER40"):
        if peer==symbol:continue
        w=all_data.get(peer)
        if w is None:continue
        f4=window(w,t,4,p["clock"]["featureMinimumObservedHours4h"])
        f24=window(w,t,24,p["clock"]["featureMinimumObservedHours24h"])
        if f4 and f24:
            others.append((clip(f4["ret"]/max(1,f4["sig"]*sqrt(4)),3),
                           clip(f24["ret"]/max(1,f24["sig"]*sqrt(24)),3)))
    if len(others)<2:return None
    peer4=mean(x[0] for x in others);peer24=mean(x[1] for x in others)
    loc4=2*z4["loc"];loc24=2*z24["loc"]
    cap=p["training"]["featureClip"]
    out={
        "MULTISCALE_REPRICING":[1,r4,r24,r72,act,expansion],
        "ACTIVITY_VOLATILITY_REGIME":[1,loc4,loc24,act,expansion,clip(r4,3)],
        "CROSS_ASSET_RELATIVE":[1,r4-peer4,r24-peer24,peer4,peer24,clip((peer4+peer24)/2,3)]
    }
    return {k:[clip(x,cap) for x in v] for k,v in out.items()},sig

class OnlineModel:
    def __init__(self):
        self.w=[0.]*6;self.n=0;self.loss=1.
    def predict(self,x):
        return clip(sum(a*b for a,b in zip(self.w,x)),3)
    def learn(self,x,pred,y,p):
        diff=clip(pred-y,6)
        lr=p["training"]["learningRate"];decay=p["training"]["weightDecay"]
        self.w=[clip(w*(1-lr*decay)-lr*diff*z,3) for w,z in zip(self.w,x)]
        self.n+=1
        a=p["training"]["ensembleDecay"]
        self.loss=a*self.loss+(1-a)*(pred-y)**2

def cost_context(samples):
    a=defaultdict(list)
    for v in samples:a[v["Symbol"]].append(v)
    res={}
    for s,rs in a.items():
        spreads=sorted(float(x["SpreadBps"]) for x in rs)
        fees=[float(x["CommissionBps"]) for x in rs]
        vol=[float(x["PastVolBps"])/sqrt(300) for x in rs]
        if len(rs)<3:continue
        p90=spreads[int(.9*(len(spreads)-1))]
        avg=mean(spreads);c=max(fees);v=max(vol)
        margins=[float(x["CurrentMinimumMarginEur"]) for x in rs]
        notionals=[float(x["MinimumNotionalEur"]) for x in rs]
        # Costs are explicit current-tariff/statistical scenarios. Not fills.
        res[s]=dict(
            observed=len(rs),minimumNotionalEur=max(notionals),
            minimumMarginEur=max(margins),
            centralBps=avg+c+2*(.25*avg+v),
            adverseBps=p90+1.25*c+2*(.5*p90+2*v),
            stressBps=2*p90+2*c+2*(p90+3*v),
            fundingKnown=all(bool(x["DailyFundingKnown"]) for x in rs),
            swapMinute=int(rs[0]["SwapMinute"]),
            longDailyDebitBps=max(float(x["LongDailyDebitBps"]) for x in rs),
            shortDailyDebitBps=max(float(x["ShortDailyDebitBps"]) for x in rs),
            observedSpreadP90Bps=p90,
            currentCommissionMaxBps=c)
    return res

def score_market(views,p):
    names=p["sourceSymbols"]
    clocks=sorted(set(t for s in names for t in views[s]["price"]
                      if t%DAY in (x*HOUR for x in p["clock"]["utcHours"])
                      and p["calendar"]["start"]<=t<p["calendar"]["end"]))
    pending=[];seq=0
    states=defaultdict(OnlineModel);stats=defaultdict(list)
    forecasts=defaultdict(list)
    proposalCount=defaultdict(int)
    errors=defaultdict(int)
    for t in clocks+[p["calendar"]["end"]+1]:
        while pending and pending[0][0]<=t:
            _,_,item=heapq.heappop(pending)
            s=item["symbol"];h=item["horizon"];target=t if False else item["due"]
            outcome=views[s]["price"].get(target)
            key=(item["phase"],s,h)
            if outcome is None:
                errors[key]+=1
                continue
            y=10000*log(outcome/item["entry"])
            normalized=clip(y/item["scale"],p["training"]["targetClipSigma"])
            for fam in FAMS:
                st=states[(s,fam,h)]
                pred=item["pred"][fam]
                stats[(item["phase"],s,h,fam)].append(dict(
                    actual=y,forecast=pred*item["scale"],naive=item["naive"],
                    brier=((1/(1+exp(-clip(pred,8)))-(1 if y>0 else 0))**2),
                    baselineBrier=.25))
                st.learn(item["x"][fam],pred,normalized,p)
            combo=item["combo"]
            stats[(item["phase"],s,h,"FUSION")].append(dict(
                actual=y,forecast=combo*item["scale"],naive=item["naive"],
                brier=((1/(1+exp(-clip(combo,8)))-(1 if y>0 else 0))**2),
                baselineBrier=.25))
        if t>=p["calendar"]["end"]:break
        stage=phase(t,p)
        if stage is None:continue
        if t<p["calendar"]["start"]+p["training"]["warmupWeeks"]*WEEK:continue
        flimit=limit(t,p)
        # Features may be shared across multiple true target resolutions.
        ft={s:features(views,t,s,views,p) for s in names}
        for s,v in ft.items():
            if v is None:continue
            x,sig=v;price=views[s]["price"][t]
            for h in p["holdingHorizonsMinutes"]:
                due=t+h*60000
                if due>=flimit:continue
                models=[states[(s,f,h)] for f in FAMS]
                if min(m.n for m in models)<p["training"]["minimumMaturedObservations"]:
                    # Warm-up labels must be matured from predictions; do not
                    # admit on synthetic zero outcomes.
                    # Below this threshold forecasts still train causally.
                    decisionAvailable=False
                else:decisionAvailable=True
                pr={f:states[(s,f,h)].predict(x[f]) for f in FAMS}
                raw=[exp(-clip(states[(s,f,h)].loss,10)) for f in FAMS]
                total=sum(raw);combo=sum(pr[f]*raw[i] for i,f in enumerate(FAMS))/total
                scale=sig*sqrt(h/60)
                naive=clip(x["MULTISCALE_REPRICING"][1]*.25,3)*scale
                seq+=1;it=dict(clock=t,due=due,symbol=s,horizon=h,phase=stage,entry=price,
                    x=x,scale=scale,pred=pr,combo=combo,naive=naive,available=decisionAvailable)
                heapq.heappush(pending,(due,seq,it))
                proposalCount[(stage,s,h)]+=1
                if decisionAvailable:
                    forecasts[t].append(dict(symbol=s,horizon=h,phase=stage,
                        familyPredBps={f:pr[f]*scale for f in FAMS},
                        familyWeights={f:raw[i]/total for i,f in enumerate(FAMS)},
                        predictedBps=combo*scale,scale=scale,
                        confidenceBlocks=min(m.n for m in models),clock=t))
    rows=[]
    for stage in ("development","selection","exposed_audit"):
        for s in names:
            for h in p["holdingHorizonsMinutes"]:
                for fam in FAMS+("FUSION",):
                    a=stats[(stage,s,h,fam)]
                    if not a:
                        rows.append(dict(phase=stage,symbol=s,horizonMinutes=h,family=fam,
                            complete=0,missing=errors[(stage,s,h)],meanSqError=None,
                            normalizedSkillVsZero=None,meanBrier=None,neutralBrier=.25,
                            meanGrossSignAlignedBps=None,naiveSquaredError=None))
                        continue
                    mse=mean((v["actual"]-v["forecast"])**2 for v in a)
                    zero=mean(v["actual"]**2 for v in a)
                    naïve=mean((v["actual"]-v["naive"])**2 for v in a)
                    rows.append(dict(phase=stage,symbol=s,horizonMinutes=h,family=fam,
                        complete=len(a),missing=errors[(stage,s,h)],
                        meanSqError=mse,normalizedSkillVsZero=1-mse/zero if zero>0 else None,
                        meanBrier=mean(x["brier"] for x in a),neutralBrier=.25,
                        meanGrossSignAlignedBps=mean((1 if v["forecast"]>0 else -1)*
                                                    v["actual"] for v in a),
                        naiveSquaredError=naïve))
    return dict(rows=rows,clocks=len(clocks),forecasts=forecasts,
                candidateClocks=len(forecasts),proposalsByPhase={
                    stage:sum(v for (phase,_,_),v in proposalCount.items() if phase==stage)
                    for stage in ("development","selection","exposed_audit")},
                missingOutcomes=sum(errors.values()),numberModels=len(states))

def execute_source():
    p=json.loads(P.read_text())
    require(p["id"]=="IPF1" and p["status"]=="REGISTERED_UNSCORED" and
            not Path("docs/IPF1_RESULT.json").exists(),"FROZEN_NO_REPLAY")
    specs=[("bdp-source","mxm-bdp1-source-v1","research/portfolio_discovery_protocol.json"),
           ("aip-source","mxm-aip1-source-v1","research/auction_inventory_protocol.json")]
    bars={};costs=[];sourceChecks=[]
    for i,(folder,schema,sourcep) in enumerate(specs):
        blob,decoded,receipt=recover(Path(folder),p["sourceRuns"][i],p["sourceHashes"][i],schema,sourcep)
        for s,rows in blob["bars"].items():
            require(s not in bars,"DUPLICATE_SOURCE_SYMBOL")
            bars[s]=rows
        c,cov=extract_costs(blob,decoded);costs.extend(c)
        sourceChecks.append(dict(originalRun=p["sourceRuns"][i],audit=receipt,
                                 contexts=len(c),coverage=cov))
        print("IPF1_ORIGINAL_SOURCE_READBACK "+str(p["sourceRuns"][i]),flush=True)
    require(set(bars)==set(p["sourceSymbols"]),"SOURCE_UNIVERSE_MISMATCH")
    views={s:market_view(rows) for s,rows in bars.items()}
    cost=cost_context(costs)
    require(set(cost)==set(bars),"SOURCE_COST_CONTEXT_GAP")
    return p,views,cost,sourceChecks,sum(len(v) for v in bars.values())

def main():
    p,views,cost,sources,bars=execute_source()
    score=score_market(views,p)
    from .integrated_funded_book import evaluate
    economy=evaluate(views,score["forecasts"],cost,p)
    full=economy["FULL"]
    marginal={k:(round(full["closedNetEur"]-v["closedNetEur"],7)
                 if full["unresolvedPositions"]==0 and v["unresolvedPositions"]==0
                 else None) for k,v in economy.items() if k!="FULL"}
    data=dict(schema="IPF1_INTEGRATED_EXPOSED_CONDITIONAL_ECONOMICS",
        authority=p["authority"],run=int(os.environ["GITHUB_RUN_ID"]),
        originalM5Bars=bars,originalDevelopmentCostContexts=sum(x["contexts"] for x in sources),
        sourceChecks=sources,protocolSha256=sha(P.read_bytes()),closedModelsCalled=0,
        newBrokerRequests=0,ordersSubmitted=0,cloudActivated=False,
        allSourceGloballyExposed=True,independentConfirmation=False,
        genuineHistoricalFills=False,brokerHistoricalNetEur=None,
        modelReturnComparisons=score["rows"],scoreClocks=score["clocks"],
        modelStates=score["numberModels"],forecastDecisionClocks=score["candidateClocks"],
        prospectiveProposalsByPhase=score["proposalsByPhase"],
        missingTargetOutcomes=score["missingOutcomes"],originalCosts=cost,
        modeledFundedScenarios=economy,modeledMarginalEurAgainstFixedAblations=marginal,
        nativeExecutionLedgerReconciliationCertified=False,qualified=False)
    Path("ipf1-integrated-public.json").write_text(
        json.dumps(data,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n")
    summary=dict(run=data["run"],bars=bars,predictiveGroups=len(score["rows"]),
        candidateClocks=score["candidateClocks"],skillSelectionPositive=sum(
            x["normalizedSkillVsZero"] is not None and x["normalizedSkillVsZero"]>0
            for x in score["rows"] if x["phase"]=="selection" and x["family"]=="FUSION"),
        commonBooks={k:dict(**{a:v for a,v in x.items() if a in (
            "endCashEur","closedNetEur","completeRoundTrips","unresolvedPositions",
            "sampledMaxDrawdown","nativeSelectorCalls","nativeAllocations")}) for k,x in economy.items()},
        qualified=False)
    print("IPF1_AUTHENTIC_INTEGRATED_RESULT "+json.dumps(summary,sort_keys=True),flush=True)

if __name__=="__main__":
    main()

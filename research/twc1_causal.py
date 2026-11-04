"""TWC1: prospectively frozen calendar-time conditional return economics.

Original authenticated Pepperstone OHLCV source and broker contract/cost context
only. No historical model/forecast/ablation is imported or rerun. Development
calendar is globally exposed, never independent confirmation.
"""
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
from statistics import mean
from math import log,sqrt,exp
import hashlib,heapq,json,os
from .multiscale_conditional_research import recover,extract_costs
from .integrated_predictive_funded import market_view,cost_context
from .rcp1_portfolio import WEEK,MS,HR
P=Path("research/twc1_protocol.json")
FAMILY="CALENDAR_WEEKDAY_H4_SLOT"
DAY=24*HR

def require(value,why):
    if not value: raise ValueError("TWC1_"+why)
def key(t):
    dt=datetime.fromtimestamp(t/1000,timezone.utc)
    return (dt.weekday(),dt.hour//4)
def stage(t,p):
    x=p["phase"]
    if t<x["developmentEnd"]:return "development",x["developmentEnd"]
    if t<x["selectionEnd"]:return "selection",x["selectionEnd"]
    if t<x["end"]:return "exposed_audit",x["end"]
    return None,None
def clamp(v,lim):
    return max(-lim,min(lim,v))
class Bucket:
    def __init__(self,prior=12):
        self.n=0;self.total=0.;self.prior=prior
    def predict(self):return self.total/(self.n+self.prior)
    def learn(self,bps,clip=500):
        self.n+=1
        self.total+=clamp(bps,clip)
def score(views,p):
    def is_clock(t):
        return t% (4*HR)==0 and p["phase"]["start"]<=t<p["phase"]["end"]
    clocks=sorted({t for v in views.values() for t in v["price"] if is_clock(t)})
    buckets=defaultdict(Bucket);pending=[];seq=0
    rows=defaultdict(list);missing=defaultdict(int);offers=defaultdict(list)
    planned=defaultdict(int);eligible=defaultdict(int);matured=0
    for t in clocks+[p["phase"]["end"]+1]:
        while pending and pending[0][0]<=t:
            _,_,item=heapq.heappop(pending)
            s=item["symbol"];due=item["due"]
            entry=views[s]["price"].get(item["entryAt"])
            exit_price=views[s]["price"].get(due)
            group=(item["phase"],s,item["horizon"])
            if entry is None or exit_price is None:
                missing[group]+=1
                continue
            y=10000*log(exit_price/entry)
            buckets[item["bucket"]].learn(y,p["predictor"]["retClipAbsBps"])
            matured+=1
            if item["ready"]:
                rows[group].append((y,item["pred"],item["naive"],item["week"]))
        if t>=p["phase"]["end"]:break
        if t < p["phase"]["start"]+p["phase"]["firstModelWarmupWeeks"]*WEEK:
            continue
        phase,boundary=stage(t,p)
        day,slot=key(t)
        if day>=5:continue
        for s,v in views.items():
            if t not in v["price"]:continue
            for horizon in p["holdingHorizonsMinutes"]:
                due=t+MS+horizon*60000
                if due>=boundary:continue
                name=(s,horizon,day,slot)
                m=buckets[name]
                pred=m.predict()
                naive=None
                previous=v["price"].get(t-DAY)
                if previous is not None and previous>0:
                    naive=10000*log(v["price"][t]/previous)*horizon/1440
                ready=m.n>=p["predictor"]["minimumMaturedLabels"]
                seq+=1
                item=dict(symbol=s,phase=phase,horizon=horizon,due=due,
                    entryAt=t+MS,bucket=name,pred=pred,naive=naive,
                    ready=ready,week=(t-p["phase"]["developmentEnd"])//WEEK)
                planned[(phase,s,horizon)]+=1
                heapq.heappush(pending,(due,seq,item))
                if ready and phase!="development":
                    eligible[(phase,s,horizon)]+=1
                    offers[t].append(dict(symbol=s,horizon=horizon,
                        predBps=pred,knownAt=t,observed=m.n,
                        phase=phase,scaleBps=max(1,abs(pred))))
    groupMetrics=[];summary={}
    for phase in ("development","selection","exposed_audit"):
        pooled=[]
        for s in p["sourceSymbols"]:
            for h in p["holdingHorizonsMinutes"]:
                group=(phase,s,h)
                a=rows[group];pooled+=a
                paired=[q for q in a if q[2] is not None]
                mse=mean((y-pred)**2 for y,pred,_,_ in a) if a else None
                zero=mean(y*y for y,_,_,_ in a) if a else None
                baseline=mean((y-naive)**2 for y,_,naive,_ in paired) if paired else None
                prediction=mean((y-pred)**2 for y,pred,naive,_ in paired) if paired else None
                groupMetrics.append(dict(phase=phase,symbol=s,horizonMinutes=h,
                    planned=planned[group],ready=eligible[group],scored=len(a),
                    missing=missing[group],pairedMomentum=len(paired),
                    mse=mse,zeroMse=zero,
                    skillVsZero=(1-mse/zero if zero else None),
                    skillVsPriorMomentum=(1-prediction/baseline if baseline else None),
                    meanSignedGrossBps=(mean((1 if pred>0 else -1)*y for y,pred,_,_ in a) if a else None)))
        paired=[q for q in pooled if q[2] is not None]
        zero=mean(y*y for y,p,_,_ in pooled) if pooled else None
        mse=mean((y-p)**2 for y,p,_,_ in pooled) if pooled else None
        mom=mean((y-ref)**2 for y,_,ref,_ in paired) if paired else None
        ours=mean((y-p)**2 for y,p,_,_ in paired) if paired else None
        summary[phase]=dict(scored=len(pooled),withMomentum=len(paired),
            missing=sum(missing[(phase,s,h)] for s in p["sourceSymbols"] for h in p["holdingHorizonsMinutes"]),
            pooledMse=mse,zeroMse=zero,
            pooledSkillVsZero=(1-mse/zero if zero else None),
            pairedSkillVsMomentum=(1-ours/mom if mom else None),
            proposed=sum(planned[(phase,s,h)] for s in p["sourceSymbols"] for h in p["holdingHorizonsMinutes"]))
    return dict(rows=groupMetrics,pooled=summary,offers=offers,
        totalLabelsMatured=matured,decisionClocks=len(clocks),models=len(buckets))

def source():
    p=json.loads(P.read_text())
    require(p["id"]=="TWC1" and p["status"]=="REGISTERED_UNSCORED","PROTOCOL")
    require(not Path("docs/TWC1_AUTHENTIC_RESULT.json").exists(),"FROZEN_NO_REPLAY")
    bars={};costRows=[];audits=[]
    specs=[("bdp-source","mxm-bdp1-source-v1","research/portfolio_discovery_protocol.json"),
           ("aip-source","mxm-aip1-source-v1","research/auction_inventory_protocol.json")]
    for i,(folder,schema,origin) in enumerate(specs):
        blob,decoded,audit=recover(Path(folder),p["sourceRuns"][i],
             p["sourceSha256"][i],schema,origin)
        for s,x in blob["bars"].items():
            require(s not in bars,"DUPLICATE_ORIGINAL_SOURCE")
            bars[s]=x
        cost,coverage=extract_costs(blob,decoded)
        costRows.extend(cost)
        audits.append(dict(originalRun=p["sourceRuns"][i],audit=audit,
                           developmentCostSamples=len(cost),coverage=coverage))
    require(set(bars)==set(p["sourceSymbols"]) and len(costRows)==166,
            "AUTHENTIC_SOURCE_OR_COST_COVERAGE_CHANGED")
    views={s:market_view(x) for s,x in bars.items()}
    costs=cost_context(costRows)
    require(set(costs)==set(views),"COST_UNIVERSE_INCOMPLETE")
    return p,views,costs,audits,sum(map(len,bars.values()))

def main():
    p,views,cost,audits,n=source()
    prediction=score(views,p)
    from .twc1_portfolio import evaluate
    economics=evaluate(views,prediction["offers"],cost,p)
    result=dict(schema="TWC1_AUTHENTIC_EXPOSED_CALENDAR_PORTFOLIO_V1",
        authority=p["authority"],protocolSha256=hashlib.sha256(P.read_bytes()).hexdigest(),
        executionRunId=int(os.environ["GITHUB_RUN_ID"]),
        sourceRunIds=p["sourceRuns"],sourceAudit=audits,
        authenticatedOriginalBars=n,brokerDevelopmentCostContexts=166,
        allCalendarExposedGlobally=True,independentConfirmation=False,
        closedModelsCalled=0,closedStudiesRerun=False,brokerRequestsThisRun=0,
        orderSubmissions=0,cloudActivated=False,
        decisionClocks=prediction["decisionClocks"],
        models=prediction["models"],maturedLabels=prediction["totalLabelsMatured"],
        predictivePooled=prediction["pooled"],allGroups=prediction["rows"],
        conditionalSharedCapital=economics,
        historicalBrokerNetEur=None,lifetimeDrawdownCertified=False,
        qualified=False,hard21Certified=False)
    Path("twc1-public-only.json").write_text(json.dumps(result,
          sort_keys=True,separators=(",",":"),allow_nan=False)+"\n")
    print("TWC1_AUTHENTIC_EXPOSED_RESULT "+json.dumps(dict(
        run=result["executionRunId"],bars=n,
        originalCostContexts=166,phases=prediction["pooled"],
        portfolio=economics,qualified=False),sort_keys=True,default=str),flush=True)

if __name__=="__main__":main()

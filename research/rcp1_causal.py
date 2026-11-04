"""RCP1 causal event-state skill on authentic existing Pepperstone OHLCV.

Distinct from closed IPF1: three *structural* pressure state variables and
discounted Bayesian one-coefficient posteriors (zero prior), not its SGD
vectors, models, predictions or portfolio. Outcomes mature after future
next-M5 entry + horizon. Original source integrity/cost code is reused only.
"""
import hashlib,heapq,json,math,os
from bisect import bisect_right
from collections import defaultdict
from pathlib import Path
from statistics import mean

from .multiscale_conditional_research import recover,extract_costs
from .integrated_predictive_funded import market_view,window,cost_context
MS=300000
HR=3600000
WEEK=7*24*HR
FAMILIES=("RANGE_COMPRESSION_RELEASE","RELATIVE_DISPERSION_REPAIR","TAIL_VOLATILITY_UNWIND")
P=Path("research/rcp1_protocol.json")

def require(cond,reason):
    if not cond:raise ValueError("RCP1_"+reason)
def clip(v,hi=3.):
    return min(hi,max(-hi,float(v)))
def sigmoid(v):
    return 1/(1+math.exp(-clip(v,20)))
def stage(t,proto):
    c=proto["phase"]
    if t<c["developmentEnd"]:return "development",c["developmentEnd"]
    if t<c["selectionEnd"]:return "selection",c["selectionEnd"]
    if t<c["end"]:return "exposed_audit",c["end"]
    return None,None
def analytic_features(views,s,t):
    if t not in views[s]["price"]:return None
    own=views[s]
    a=window(own,t,4,3)
    b=window(own,t,24,15)
    c=window(own,t,120,60)
    if not a or not b or not c:return None
    base=max(0.5,c["sig"])
    peers=[]
    for idx in ("US500","NAS100","GER40"):
        if idx==s:continue
        view=views.get(idx)
        if not view:continue
        u=window(view,t,24,15)
        if u and u["sig"]>0:peers.append(clip(u["ret"]/max(1.,u["sig"]*math.sqrt(24))))
    if len(peers)<2:return None
    act=max(0.,math.log(max(.01,a["vol"])/max(.01,c["vol"])))
    contraction=max(0.,1.-a["sig"]/max(.1,c["sig"]))
    expansion=max(0.,a["sig"]/max(.1,c["sig"])-1.)
    hrs=own["hr"];left=bisect_right(hrs,t-4*HR);right=bisect_right(hrs,t)
    inside=[own["h"][clock] for clock in hrs[left:right]]
    if len(inside)<3:return None
    hi=max(x[1] for x in inside);lo=min(x[2] for x in inside)
    op=inside[0][0];cl=inside[-1][3]
    upper=max(0.,hi-max(op,cl))
    lower=max(0.,min(op,cl)-lo)
    wick=(lower-upper)/max(1.,hi-lo)
    own_norm=clip(b["ret"]/max(1.,b["sig"]*math.sqrt(24)))
    risk=mean(peers)
    factors={
      FAMILIES[0]:clip(2*a["loc"]*contraction*min(2.5,act)*3),
      FAMILIES[1]:clip(own_norm-risk),
      FAMILIES[2]:clip(wick*expansion*min(3.,act)*3)
    }
    # An exact 4h bar is a completed decision, no statistical factor uses the
    # next market bar (which is reserved exclusively for execution proxy).
    return dict(x=factors,sigma=base,prior24hBps=b["ret"],
       amplitudeBps=abs(a["ret"]),activityRatio=a["vol"]/max(.01,c["vol"]))

class Posterior:
    def __init__(self,prior=16.,decay=.995):
        self.xy=0.;self.xx=0.;self.n=0;self.prior=prior;self.decay=decay
    def predict(self,x):
        return self.xy/(self.prior+self.xx)*x
    def learn(self,x,y):
        self.xy=self.decay*self.xy+x*clip(y,3)
        self.xx=self.decay*self.xx+x*x
        self.n+=1

def score_market(views,proto):
    # Required for all 12 source instruments, not only favorable ones.
    symbols=list(views)
    pending=[];seq=0
    models=defaultdict(Posterior)
    scored=defaultdict(list);unknown=defaultdict(int)
    clock_forecasts=defaultdict(list)
    observed=defaultdict(int);decisions=0;modelCount=0
    hrs=sorted(set(t for v in views.values() for t in v["hr"] if
        t% (4*HR)==0 and proto["phase"]["start"]<=t<proto["phase"]["end"]))
    # Clock is the *end* of a full H4 bar. Only matured due prices may train.
    for t in hrs+[proto["phase"]["end"]+1]:
        while pending and pending[0][0] <= t:
            due,_,row=heapq.heappop(pending)
            s=row["symbol"]
            entry=views[s]["price"].get(row["entryAt"])
            exit_price=views[s]["price"].get(due)
            key=(row["phase"],s,row["horizon"])
            if entry is None or exit_price is None:
                unknown[key]+=1
                continue
            outcome=10000*math.log(exit_price/entry)
            normalized=clip(outcome/row["scale"])
            for fam in FAMILIES:
                m=models[(s,fam,row["horizon"])]
                # Score the predeclared prediction *before* updating label.
                scored[(row["phase"],s,row["horizon"],fam)].append((
                    outcome,row["pred"][fam],row["naive"],row["scale"]))
                m.learn(row["x"][fam],normalized)
            scored[(row["phase"],s,row["horizon"],"FUSION")].append((
                outcome,row["fusion"],row["naive"],row["scale"]))
        if t>=proto["phase"]["end"]:break
        if t<proto["phase"]["start"]+proto["phase"]["firstModelWarmupWeeks"]*WEEK:
            continue
        decisions+=1
        phase,boundary=stage(t,proto)
        for s in symbols:
            feat=analytic_features(views,s,t)
            if feat is None:continue
            for horizon in proto["holdingHorizonsMinutes"]:
                due=t+MS+horizon*60000
                if due>boundary:continue
                observed[(phase,s,horizon)]+=1
                x=feat["x"];scale=feat["sigma"]*math.sqrt(horizon/60)
                pred={fam:clip(models[(s,fam,horizon)].predict(x[fam]))*scale for fam in FAMILIES}
                fusion=sum(pred.values())/len(FAMILIES)
                naive=clip(feat["prior24hBps"]*0.25,3*scale)
                matured=min(models[(s,f,horizon)].n for f in FAMILIES)
                seq+=1
                item=dict(clock=t,entryAt=t+MS,due=due,symbol=s,horizon=horizon,
                    phase=phase,x=x,pred=pred,fusion=fusion,naive=naive,scale=scale)
                heapq.heappush(pending,(due,seq,item))
                # No artificial positive starting forecast or future label.
                if matured>=proto["model"]["minimumMaturedObservations"]:
                    clock_forecasts[t].append(dict(symbol=s,horizon=horizon,
                        familyBps=pred,fusionBps=fusion,scaleBps=scale,
                        knownAt=t,maturedExamples=matured,phase=phase,
                        baselineMomentumBps=naive))
    metrics=[]
    phases=("development","selection","exposed_audit")
    for phase in phases:
        for s in symbols:
            for h in proto["holdingHorizonsMinutes"]:
                for fam in FAMILIES+("FUSION",):
                    rows=scored[(phase,s,h,fam)]
                    if rows:
                        mse=mean((y-pred)**2 for y,pred,_,sig in rows)
                        naive_mse=mean((y-base)**2 for y,_,base,sig in rows)
                        zero=mean(y*y for y,*_ in rows)
                        brier=mean((sigmoid(2*pred/max(.5,sig))-(1 if y>0 else 0))**2
                                    for y,pred,_,sig in rows)
                        corr=mean((1 if pred>0 else -1)*y for y,pred,_,_ in rows)
                        absret=mean(abs(y) for y,*_ in rows)
                    else:
                        mse=naive_mse=zero=brier=corr=absret=None
                    metrics.append(dict(phase=phase,symbol=s,horizon=h,family=fam,
                        proposed=observed[(phase,s,h)],complete=len(rows),
                        unknown=unknown[(phase,s,h)],meanSquaredError=mse,
                        mseSkillVsZero=(1-mse/zero if zero else None),
                        mseSkillVsMomentum=(1-mse/naive_mse if naive_mse else None),
                        brier=brier,neutralBrier=.25,meanAlignedGrossBps=corr,
                        meanAbsoluteOutcomeBps=absret))
    return dict(metrics=metrics,clockForecasts=clock_forecasts,
                forecastClocks=len(clock_forecasts),decisionClocks=decisions,
                unknownOutcomes=sum(unknown.values()),
                planned=sum(observed.values()),modelCount=len(models))

def read_authentic():
    p=json.loads(P.read_text())
    require(p["id"]=="RCP1" and p["status"]=="REGISTERED_UNSCORED","EXACT_PROTOCOL")
    require(not Path("docs/RCP1_RESULT.json").exists(),"FROZEN_CANNOT_RERUN")
    specs=[("bdp-source","mxm-bdp1-source-v1","research/portfolio_discovery_protocol.json"),
           ("aip-source","mxm-aip1-source-v1","research/auction_inventory_protocol.json")]
    bars={};costs=[];sourceChecks=[]
    for i,(folder,schema,original_protocol) in enumerate(specs):
        blob,decoded,audit=recover(Path(folder),p["sourceRuns"][i],
            p["sourceSha256"][i],schema,original_protocol)
        for s,rows in blob["bars"].items():
            require(s not in bars,"SOURCE_DUPLICATED_IN_ARCHIVE");bars[s]=rows
        values,coverage=extract_costs(blob,decoded)
        costs.extend(values);sourceChecks.append(dict(run=p["sourceRuns"][i],audit=audit,
            costContexts=len(values),coverage=coverage))
        print("RCP1_AUTHENTIC_SOURCE "+str(p["sourceRuns"][i]),flush=True)
    require(len(bars)==12 and len(costs)==166,"EXPECTED_AUTHENTIC_ORIGINAL_CONTEXT")
    views={s:market_view(rows) for s,rows in bars.items()}
    c=cost_context(costs)
    require(set(c)==set(bars),"MINIMUM_FINANCE_NOT_KNOWN")
    return p,views,c,sourceChecks,sum(len(x) for x in bars.values())

def main():
    p,views,cost,sources,bars=read_authentic()
    result=score_market(views,p)
    from .rcp1_portfolio import evaluate
    funded=evaluate(views,result["clockForecasts"],cost,p)
    phaseRows=result["metrics"]
    summary=dict(schema="RCP1_EXPOSED_CAUSAL_NEXT_BAR_JOINT_PORTFOLIO_CONDITIONAL",
        protocolSha256=hashlib.sha256(P.read_bytes()).hexdigest(),
        executionRunId=int(os.environ["GITHUB_RUN_ID"]),originalM5Bars=bars,
        originalCostContexts=sum(x["costContexts"] for x in sources),
        authenticatedOriginalSources=sources,readOnly=True,
        noClosedModelScoring=True,closedStudiesUnchanged=True,newBrokerRequests=0,
        observations=dict(decisionClocks=result["decisionClocks"],
            forecastClocks=result["forecastClocks"],planned=result["planned"],
            missingOutcomes=result["unknownOutcomes"],onlineModelCount=result["modelCount"]),
        predictiveSkillAllDeclaredCells=phaseRows,
        conditionalCommonCapitalBooks=funded,actualBrokerFundedNetEur=None,
        actualFillHistoryCertified=False,independentConfirmation=False,
        hard21SystemCertified=False,noCloudActivation=True,ordersSubmitted=0,
        passesOwnerEconomicQualification=False)
    Path("rcp1-public-only.json").write_text(json.dumps(summary,sort_keys=True,
        separators=(",",":"),allow_nan=False)+"\n")
    fusion=[x for x in phaseRows if x["family"]=="FUSION"]
    report=dict(run=summary["executionRunId"],sourceBars=bars,
        sourceCostContexts=summary["originalCostContexts"],
        skillSelectionCellsPositiveVsZero=sum(x["mseSkillVsZero"] is not None and x["mseSkillVsZero"]>0
            for x in fusion if x["phase"]=="selection"),
        skillSelectionCellsPositiveVsMomentum=sum(x["mseSkillVsMomentum"] is not None and x["mseSkillVsMomentum"]>0
            for x in fusion if x["phase"]=="selection"),
        commonBooks={k:{z:v[z] for z in ("cashEur","netClosedEur","modeledRoundTrips",
           "maxSampledDrawdown","nativeCalls","nativeAllocations","unresolvedPositions",
           "hard21EligibleWeeksPassed") if z in v} for k,v in funded.items()},
        qualified=False)
    print("RCP1_AUTHENTIC_INTEGRATED "+json.dumps(report,sort_keys=True),flush=True)

if __name__=="__main__":main()

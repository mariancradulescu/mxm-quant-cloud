"""RDE1 ex-ante causal tail-risk study, NOT an allocator or a trading model.

No MVE1 feature/scorer is called. All study splits were frozen before source
readback. The only outputs here are calibrated forecasts, eligibility and
paired scores; money enters only the EXISTING native EUR300 ledger.
"""
from __future__ import annotations
from collections import defaultdict
from math import log, sqrt, isfinite
from statistics import mean, stdev, NormalDist
from bisect import bisect_right

M5=300000
HOUR=3600000
WEEK=7*24*HOUR
TAU=.90
BONF_Z=NormalDist().inv_cdf(1-.05/24)


def sign(x):
    return (x>0)-(x<0)


def validated(raw):
    """No silent sorting/dedup/interpolation of broker source."""
    out=sorted(raw,key=lambda a:int(a[1]))
    streak=[];prior=None
    for a in out:
        if (len(a)!=7 or int(a[1])-int(a[0])!=M5 or
            int(a[2])<=0 or int(a[5])<=0 or
            int(a[3])<max(int(a[2]),int(a[5])) or
            int(a[4])>min(int(a[2]),int(a[5])) or int(a[6])<0):
            raise ValueError("RDE1_M5_OHLCV_INVALID")
        if prior and int(a[1])<=int(prior[1]):
            raise ValueError("RDE1_DUPLICATE_M5")
        streak.append(streak[-1]+1 if prior and int(a[0])==int(prior[1]) else 1)
        prior=a
    return out,streak


def phase_of(t,scope):
    if t<scope["trainEnd"]:return "training"
    if t<scope["selectionEnd"]:return "selection"
    return "exposed_audit"


def phase_end(ph,scope):
    return {"training":scope["trainEnd"],"selection":scope["selectionEnd"],
            "exposed_audit":scope["end"]}[ph]


def causal_clocks(symbol,raw,scope):
    """Hourly forecasting on all intact 97-bar contexts, with no outcomes."""
    a,streak=validated(raw)
    event=[]
    for i in range(96,len(a)):
        t=int(a[i][1])
        if not(scope["calendarStart"]<=t<scope["end"]) or t%HOUR:
            continue
        if streak[i]<97:continue
        c=[float(x[5]) for x in a[i-96:i+1]]
        rr=[log(c[j]/c[j-1]) for j in range(1,97)]
        rv24=sqrt(mean(v*v for v in rr[-24:]))
        rv48=sqrt(mean(v*v for v in rr[-48:]))
        r48=log(c[-1]/c[-49]);r24=log(c[-1]/c[-25])
        directional=sign(r48)
        strong=abs(r48)>.75*rv48*sqrt(48)
        agreed=directional!=0 and sign(r24)==directional
        side=directional if strong and agreed else 0
        aligned=sum(sign(v)==directional for v in rr[-24:])/24 if directional else .5
        event.append(dict(s=symbol,t=t,index=i,phase=phase_of(t,scope),
            direction=side,rv24=rv24,rv48=rv48,
            volRatio=rv24/max(rv48,1e-12),
            persistence=int(aligned>=.60),
            scaleBps=10000*max(rv24,1e-12)*sqrt(24),
            entryClock=t+M5))
    return event,a,streak


def realized_labels(events,a,streak,scope):
    """Only after intents are frozen. Unknown forward path never drops intent."""
    out=[]
    for e in events:
        i=e["index"];end=i+25;limit=phase_end(e["phase"],scope)
        record=dict(e,known=False,longAdverse=None,shortAdverse=None,returnBps=None)
        if (end>=len(a) or streak[end]<26 or int(a[end][1])>=limit):
            out.append(record);continue
        entry=float(a[i+1][5]);close=float(a[end][5])
        path=a[i+2:end+1]
        low=min(float(b[4]) for b in path)
        high=max(float(b[3]) for b in path)
        if min(entry,close,low,high)<=0:
            out.append(record);continue
        record.update(known=True,
            longAdverse=10000*max(0.,log(entry/low)),
            shortAdverse=10000*max(0.,log(high/entry)),
            returnBps=10000*log(close/entry))
        out.append(record)
    return out


def quantile(x,tau=TAU):
    if not x:raise ValueError("RDE1_EMPTY_TRAIN_DISTRIBUTION")
    ordered=sorted(float(v) for v in x)
    return ordered[min(len(ordered)-1,max(0,int(len(ordered)*tau+1-1e-12)-1))]


def mixed_quantile(local,global_values,prior_weight=50):
    """Exact quantile of (local empirical CDF + 50*global empirical CDF)."""
    if not global_values:raise ValueError("RDE1_NO_TRAIN_DISTRIBUTION")
    points=[(float(v),1.) for v in local]
    points +=[(float(v),prior_weight/len(global_values)) for v in global_values]
    points.sort(key=lambda z:z[0])
    threshold=TAU*(len(local)+prior_weight)
    total=0.
    for v,w in points:
        total+=w
        if total+1e-10>=threshold:return v
    return points[-1][0]


def fit_training(rows):
    train=[r for r in rows if r["phase"]=="training" and r["known"]]
    if len(train)<100:
        raise ValueError("RDE1_INSUFFICIENT_TRAINING_WITH_MATURED_PATHS")
    # Global, train-only dimensionless volatility regime thresholds.
    t1=quantile([r["volRatio"] for r in train],1/3)
    t2=quantile([r["volRatio"] for r in train],2/3)
    model={"terciles":[t1,t2],"trainKnown":len(train),"simple":{},"groups":{}}
    for side in (1,-1):
        values=[(r["longAdverse"] if side>0 else r["shortAdverse"])/
                r["scaleBps"] for r in train]
        model["simple"][side]=quantile(values)
        for tercile in range(3):
            for persistent in (0,1):
                local=[(r["longAdverse"] if side>0 else r["shortAdverse"])/
                       r["scaleBps"] for r in train if
                       (int(r["volRatio"]>t1)+int(r["volRatio"]>t2))==tercile and
                       r["persistence"]==persistent]
                model["groups"][(side,tercile,persistent)]=mixed_quantile(local,values)
    return model


def forecast(r,fit,side):
    t1,t2=fit["terciles"]
    v=int(r["volRatio"]>t1)+int(r["volRatio"]>t2)
    return dict(simple=fit["simple"][side]*r["scaleBps"],
                conditional=fit["groups"][(side,v,r["persistence"])]*r["scaleBps"])


def pinball(y,q):
    d=y-q
    return (TAU if d>=0 else TAU-1)*d


def paired_weekly(rows,fit,scope,phase,side):
    # Overlapping 2h labels are never assumed independent M5 observations.
    weekly=defaultdict(lambda:defaultdict(list))
    sums={"simpleLoss":0.,"conditionalLoss":0.,"simpleExceed":0,
          "conditionalExceed":0,"known":0,"missing":0}
    start=scope["trainEnd"] if phase=="selection" else scope["selectionEnd"]
    for r in rows:
        if r["phase"]!=phase:continue
        if not r["known"]:
            sums["missing"]+=1;continue
        y=r["longAdverse"] if side>0 else r["shortAdverse"]
        q=forecast(r,fit,side)
        ls=pinball(y,q["simple"]);lc=pinball(y,q["conditional"])
        sums["simpleLoss"]+=ls;sums["conditionalLoss"]+=lc
        sums["simpleExceed"]+=int(y>q["simple"])
        sums["conditionalExceed"]+=int(y>q["conditional"])
        sums["known"]+=1
        week=(r["t"]-start)//WEEK
        if 0<=week<13:weekly[week][r["s"]].append(ls-lc)
    w=[]
    for k in range(13):
        assets=weekly[k]
        w.append(mean([mean(v) for v in assets.values()]) if assets else None)
    observed=[x for x in w if x is not None]
    lower=None
    if len(observed)>=10 and len(observed)>1:
        lower=mean(observed)-BONF_Z*stdev(observed)/sqrt(len(observed))
    n=sums["known"]
    return dict(phase=phase,side=side,n=n,unknown=sums["missing"],
        simplePinball=sums["simpleLoss"]/n if n else None,
        conditionalPinball=sums["conditionalLoss"]/n if n else None,
        simpleExceedance=sums["simpleExceed"]/n if n else None,
        conditionalExceedance=sums["conditionalExceed"]/n if n else None,
        pairedWeekDifferenceLowerBonferroni=lower,
        observedWeeks=len(observed),weeklyMeanDifferences=w,
        acceptedRiskInformation=bool(lower is not None and lower>0),
        independentConfirmation=False)


def mandatory_economic_gate(train_intents,symbol,side,scope,cost):
    """No alpha => no economic entry, even with beautiful tail forecasts."""
    if (not cost or cost.get("minimumNotionalEur",0)<=0 or
        cost.get("minimumMarginEur",1e99)>=300 or
        not isfinite(float(cost.get("adverseBps",float("nan")))) or
        not cost.get("fundingKnown")):
        return dict(admitted=False,reason="FINANCIAL_OR_CONTRACT_UNKNOWN")
    sample=[];week_n=set();last_end=-1
    for r in sorted(train_intents,key=lambda x:x["t"]):
        if r["s"]!=symbol or r["direction"]!=side or r["phase"]!="training":
            continue
        # First suppress overlapping intentions WITHOUT consulting realized outcomes.
        if r["entryClock"]<last_end:continue
        last_end=r["entryClock"]+24*M5
        if not r["known"]:continue
        value=(side*r["returnBps"]-cost["adverseBps"])*cost["minimumNotionalEur"]/10000
        week=(r["t"]-scope["calendarStart"])//WEEK
        if 0<=week<26:
            sample.append((week,value));week_n.add(week)
    if len(sample)<16 or len(week_n)<10:
        return dict(admitted=False,reason="TRAIN_SAMPLE_INSUFFICIENT",
                    nonoverlapTrades=len(sample),weeks=len(week_n))
    each=[sum(v for k,v in sample if k==j) for j in range(26)]
    lower=mean(each)-BONF_Z*stdev(each)/sqrt(len(each))
    return dict(admitted=lower>0,reason="TRAIN_ALPHA_LOWER_PASS" if lower>0 else "NO_TRAIN_ALPHA",
                nonoverlapTrades=len(sample),weeks=len(week_n),
                trainWeeklyAdverseNetLowerEur=lower,
                independentConfirmation=False)

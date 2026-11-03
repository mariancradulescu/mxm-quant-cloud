"""A distinct, prospectively frozen M15 EURUSD session-price anchor hypothesis.

Each historical signal uses ONLY completed bars of current 06:00 UTC session.
The labels of future 45-minute price paths are used only for chronological
training or subsequent selection reporting, never to choose current side.
"""
import math,statistics
from datetime import datetime,timezone
from .decode import need
from .tick_volume_net import eligible_weeks, DAY

Q=900000
MODEL="EURUSD_M15_SESSION_ANCHORED_TICK_BALANCE_V1"
SLOTS=(9,11,13,15,17)

def signals(b):
    a=sorted(b["bars"],key=lambda x:x["t"])
    lo=b["start"]+(b["end"]-b["start"])*6//10
    hi=b["start"]+(b["end"]-b["start"])*8//10
    need(len(a)>20000 and a[-1]["t"]+Q-a[0]["t"]>=365*DAY,
         "M15_365_DAY_OBSERVED_SOURCE_MISSING")
    samples=[];seen=set()
    for i in range(48,len(a)-3):
        t=a[i]["t"]
        need(t not in seen,"DUPLICATE_M15")
        seen.add(t)
        dt=datetime.fromtimestamp(t/1000,timezone.utc)
        if dt.weekday()>4 or dt.hour not in SLOTS or dt.minute!=0:continue
        if any(a[i+k]["t"]!=t+k*Q for k in range(4)):continue
        session_start=t-(dt.hour-6)*4*Q
        k=i-1;window=[]
        while k>=0 and a[k]["t"]>=session_start:
            window.append(a[k]);k-=1
        window.reverse()
        expected=(t-session_start)//Q
        if (len(window)!=expected or len(window)<12 or
            any(v["t"]!=session_start+j*Q for j,v in enumerate(window)) or
            any(v["v"]<=0 or v["l"]<=0 or v["h"]<v["l"] or v["c"]<v["l"] or v["c"]>v["h"] for v in window)):
            continue
        denominator=sum(v["v"] for v in window)
        need(denominator>0,"INVALID_TICK_WEIGHT")
        value=sum(v["v"]*(v["h"]+v["l"]+v["c"])/3 for v in window)/denominator
        rng=sum(v["h"]-v["l"] for v in window)/len(window)
        if rng<=0:continue
        x=(a[i-1]["c"]-value)/rng
        target=(a[i+2]["c"]-a[i-1]["c"])/a[i-1]["c"]
        need(math.isfinite(x) and math.isfinite(target),"NONFINITE_ANCHOR_FEATURE")
        samples.append({"signal":t,"exit":t+3*Q,"x":x,"y":target,
                        "price":a[i-1]["c"]/100000})
    train=[x for x in samples if x["exit"]<lo]
    selection=[x for x in samples if lo<=x["signal"] and x["exit"]<hi]
    weeks=eligible_weeks(lo,hi)
    need(len(train)>=450 and len(selection)>=130 and len(weeks)>=8,
         "M15_ANCHOR_TRAIN_OR_SELECTION_INSUFFICIENT")
    mx=statistics.mean(x["x"] for x in train)
    my=statistics.mean(x["y"] for x in train)
    denom=sum((x["x"]-mx)**2 for x in train)
    need(denom>1e-12,"M15_ANCHOR_ZERO_TRAIN_VARIABILITY")
    slope=sum((x["x"]-mx)*(x["y"]-my) for x in train)/denom
    slope*=len(train)/(len(train)+200)
    intercept=my-slope*mx
    tails=sorted(abs(x["y"]) for x in train)
    tail=tails[int((len(tails)-1)*0.995)]
    plan=[{"signal":x["signal"],"exit":x["exit"],
           "side":1 if intercept+slope*x["x"]>0 else -1,
           "forecast":intercept+slope*x["x"],"price":x["price"],
           "realizedBidCloseReturn":x["y"]}
          for x in selection if abs(intercept+slope*x["x"])>0]
    return {"trainingExamples":len(train),"selectionWindows":len(selection),
            "plan":plan,"trainingCutMs":lo,"selectionEndMs":hi,
            "fitIntercept":intercept,"fitSlope":slope,
            "train99p5AbsForwardReturn":tail,
            "eligibleMondayUtcMs":weeks}

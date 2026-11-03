"""Frozen independent economic mechanism: 06-09 UTC M15 wick rejection -> 09-15 UTC EURUSD.

Source is existing original Pepperstone sealed M15 bars+event quotes; this is
a NEW hypothesis, NOT a retune or resurrected previous exact configuration.
Selection dates have been used in earlier research and are NOT independent
confirmation. No new broker calls or trade orders are possible here.
"""
import statistics,math
from datetime import datetime,timezone
from .decode import need
from .tick_volume_net import eligible_weeks,DAY

Q=900000
MODEL="EURUSD_M15_EARLY_SESSION_WICK_REJECTION_TO_15UTC_V1"

def signals(b):
    bars=sorted(b["bars"],key=lambda x:x["t"])
    source={x["t"]:x for x in bars}
    need(len(source)==len(bars) and len(bars)>20000 and bars[-1]["t"]+Q-bars[0]["t"]>=365*DAY,
         "ORIGINAL_AUTHENTIC_M15_SOURCE_GEOMETRY")
    cut=b["start"]+(b["end"]-b["start"])*6//10
    stop=b["start"]+(b["end"]-b["start"])*8//10
    rows=[]
    for bar in bars:
        entry=bar["t"]
        d=datetime.fromtimestamp(entry/1000,timezone.utc)
        if d.weekday()>4 or d.hour!=9 or d.minute!=0:continue
        observed=[source.get(entry-j*Q) for j in range(12,0,-1)]
        future=[source.get(entry+j*Q) for j in range(24)]
        if any(x is None for x in observed+future):continue
        den=sum(x["h"]-x["l"] for x in observed)
        if den<=0 or any(x["l"]<=0 or x["h"]<max(x["o"],x["c"]) or min(x["o"],x["c"])<x["l"] for x in observed):continue
        # Wick rejection, NOT previous price displacement or volume weighting.
        # Positive value = excess LOWER wicks, negative = UPPER wicks.
        wick_skew=sum((min(x["o"],x["c"])-x["l"])-(x["h"]-max(x["o"],x["c"])) for x in observed)/den
        px=observed[-1]["c"]
        y=(future[-1]["c"]-px)/px
        need(math.isfinite(wick_skew) and math.isfinite(y),"WICK_NONFINITE_SOURCE")
        rows.append({"signal":entry,"exit":entry+24*Q,"x":wick_skew,"y":y,
                     "price":px/100000})
    train=[r for r in rows if r["exit"]<cut]
    select=[r for r in rows if cut<=r["signal"] and r["exit"]<stop]
    weeks=eligible_weeks(cut,stop)
    need(len(train)>=125 and len(select)>=35 and len(weeks)>=8,
         "WICK_CAUSAL_TRAIN_SELECTION_TOO_FEW")
    mx=statistics.mean(r["x"] for r in train);my=statistics.mean(r["y"] for r in train)
    var=sum((r["x"]-mx)**2 for r in train)
    need(var>1e-12,"WICK_TRAIN_NO_VARIANCE")
    slope=sum((r["x"]-mx)*(r["y"]-my) for r in train)/var
    slope*=len(train)/(len(train)+100)
    intercept=my-slope*mx
    y_abs=sorted(abs(r["y"]) for r in train)
    tail=y_abs[int((len(y_abs)-1)*0.995)]
    proposals=[{"signal":r["signal"],"exit":r["exit"],
                "side":1 if intercept+slope*r["x"]>0 else -1,
                "forecast":intercept+slope*r["x"],
                "price":r["price"],"realizedBidCloseReturn":r["y"]}
               for r in select if abs(intercept+slope*r["x"])>0]
    return {"trainingExamples":len(train),"selectionWindows":len(select),
            "plan":proposals,"trainingCutMs":cut,"selectionEndMs":stop,
            "fitIntercept":intercept,"fitSlope":slope,
            "train99p5AbsForwardReturn":tail,
            "eligibleMondayUtcMs":weeks}

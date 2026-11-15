"""MVE1: source-only completed-M5 event and continuous multivariate features.

No broker interface, order route, fixed time-of-day candidate selection, outcome
lookup, retrospective filter, or closed strategy prediction. All technical
transforms are expressible using native C# Bars and Math.
"""
from __future__ import annotations
from collections import Counter
from math import log, sqrt, sin, cos, pi
M5=300000
HOUR=3600000
SYMBOLS=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD",
         "US500","NAS100","GER40","UK100","AUS200","JPN225")
PEERS=("EURUSD","XAUUSD","US500","NAS100","GER40")
TAGS=("BREAKOUT_12","WICK_REJECTION","VOLATILITY_TRANSITION",
      "PULLBACK_REJOIN","COMPRESSION_BREAK","IMPULSE_CONTINUATION")
COLUMNS=("intercept","bodyByRange","upperWickByRange","lowerWickByRange",
         "r3Norm","r12Norm","r24Norm","r48Norm","signedEfficiency24",
         "vol6Over24","vol24Over48","prevRange12Over24",
         "breakoutDistanceNorm","rsi14Centered","ema12Minus26Norm",
         "logVolume6Over24","peer12Norm","peerObservedFraction",
         "timeSin","timeCos","bodyTimesR24","volRatioTimesR12",
         "breakoutTimesCompression","wickImbalanceTimesR24",
         "peerTimesImpulse","volumeTimesVol","eventBreakout",
         "eventRejection","eventVolTransition","eventPullback",
         "eventCompression","eventContinuation")
N_BASE=20
INTERACTION_IDX=tuple(range(20,26))
PEER_IDX=(16,17,24)
SIMPLE_IDX=(0,4,5,6,7)
FIXED_CLIP=5.


def sign(x):
    return (x>0)-(x<0)


def cap(x,n=FIXED_CLIP):
    return max(-n,min(n,x))


def ema_last(a,length):
    alpha=2/(length+1)
    x=a[0]
    for val in a[1:]:
        x=alpha*val+(1-alpha)*x
    return x


def strict_rows(raw):
    a=sorted(raw,key=lambda z:z[1])
    run=[];prior=None
    for i,r in enumerate(a):
        if (len(r)!=7 or int(r[1])-int(r[0])!=M5 or
            int(r[5])<=0 or int(r[4])<=0 or int(r[2])<=0 or
            int(r[3])<max(int(r[2]),int(r[5])) or
            int(r[4])>min(int(r[2]),int(r[5]))):
            raise ValueError("MVE1_ORIGINAL_OHLCV_INVALID")
        if prior is not None and r[1]<=prior[1]:
            raise ValueError("MVE1_ORIGINAL_DUPLICATE_M5")
        run.append(run[-1]+1 if prior and r[0]==prior[1] else 1)
        prior=r
    return a,run


def peer_past12(rows,run):
    """Only exact peer completion clocks, no forward fill or future price."""
    out={}
    for i in range(24,len(rows)):
        if run[i]<25:
            continue
        prices=[float(x[5]) for x in rows[i-24:i+1]]
        ret=[log(prices[j]/prices[j-1]) for j in range(1,25)]
        vol=sqrt(sum(x*x for x in ret)/24)
        out[int(rows[i][1])]=cap(log(prices[-1]/prices[-13])/
                                  max(vol*sqrt(12),1e-8))
    return out


def features_at(rows,run,i,peer_values):
    """49 exact completed M5 closes: all inputs at or before rows[i].end."""
    if i<48 or run[i]<49:
        return None
    a=rows[i-48:i+1]
    c=[float(x[5]) for x in a]
    ret=[log(c[j]/c[j-1]) for j in range(1,49)]
    def rms(x):
        return sqrt(sum(v*v for v in x)/len(x))
    rv6=rms(ret[-6:]);rv24=rms(ret[-24:]);rv48=rms(ret)
    old6=rms(ret[-12:-6]);old24=rms(ret[-30:-6])
    prevbar=a[-1];prange=max(1.,float(prevbar[3]-prevbar[4]))
    body=(prevbar[5]-prevbar[2])/prange
    upper=(prevbar[3]-max(prevbar[5],prevbar[2]))/prange
    lower=(min(prevbar[5],prevbar[2])-prevbar[4])/prange
    rr3=log(c[-1]/c[-4]);rr12=log(c[-1]/c[-13])
    rr24=log(c[-1]/c[-25]);rr48=log(c[-1]/c[0])
    denom=max(1e-8,rv24)
    r3=cap(rr3/(denom*sqrt(3)))
    r12=cap(rr12/(denom*sqrt(12)))
    r24=cap(rr24/(denom*sqrt(24)))
    r48=cap(rr48/(denom*sqrt(48)))
    high12=max(x[3] for x in a[-13:-1])
    low12=min(x[4] for x in a[-13:-1])
    rng12=max(x[3] for x in a[-13:-1])-min(x[4] for x in a[-13:-1])
    prev12=a[-25:-13]
    rng_prev12=max(x[3] for x in prev12)-min(x[4] for x in prev12)
    rng24=max(x[3] for x in a[-25:-1])-min(x[4] for x in a[-25:-1])
    raw_dist=(prevbar[5]-high12 if prevbar[5]>high12 else
              prevbar[5]-low12 if prevbar[5]<low12 else 0)
    signed_eff=(c[-1]-c[-25])/max(1e-8,sum(abs(c[j]-c[j-1])
                                           for j in range(25,49)))
    positives=sum(max(0,x) for x in ret[-14:])
    negatives=sum(max(0,-x) for x in ret[-14:])
    rsi=positives/(positives+negatives) if positives+negatives else .5
    em12=ema_last(c,12);em26=ema_last(c,26)
    vol6=sum(float(x[6]) for x in a[-6:])
    vol24=sum(float(x[6]) for x in a[-24:])
    activity=cap(log((vol6+1)/(vol24+1)*4))
    synced=[v for v in peer_values if v is not None]
    peer=cap(sum(synced)/len(synced)) if len(synced)>=2 else 0.
    peer_available=len(synced)/max(1,len(peer_values))
    utc=(int(prevbar[1])%86400000)/HOUR
    breakout=prevbar[5]>high12 or prevbar[5]<low12
    rejection=upper>max(abs(body),lower) or lower>max(abs(body),upper)
    rv_transition=sign(rv6-rv24)!=sign(old6-old24)
    pullback=rr24*rr3<0 and sign(body)==sign(rr24)
    compressed=rng12<rng_prev12
    continuation=sign(rr3)==sign(rr24)==sign(body) and sign(body)!=0
    tags=(breakout,rejection,rv_transition,pullback,
          compressed and breakout,continuation)
    if not any(tags):
        return None
    ratio6=cap(rv6/denom)
    ratio24=cap(rv24/max(rv48,1e-8))
    compression=cap(rng12/max(rng24,1.))
    breakout_dist=cap(raw_dist/max(c[-1]*denom,1.))
    ema_ratio=cap((em12-em26)/max(c[-1]*denom,1e-8))
    base=[1.,cap(body),cap(upper),cap(lower),r3,r12,r24,r48,
          cap(signed_eff),ratio6,ratio24,compression,breakout_dist,
          cap(2*rsi-1),ema_ratio,activity,peer,peer_available,
          sin(2*pi*utc/24),cos(2*pi*utc/24)]
    interaction=[
        cap(body*r24),cap((ratio6-1)*r12),
        cap(breakout_dist*(1-compression)),
        cap((lower-upper)*r24),cap(peer*r3),
        cap(activity*(ratio6-1))]
    feature=base+interaction+[float(x) for x in tags]
    assert len(feature)==len(COLUMNS)
    return {"features":tuple(feature),"tags":tuple(tags),
            "vol5":denom,"r12":rr12,"r24":rr24,"r48":rr48,
            "entryClock":int(prevbar[1])+M5,
            "regime":"EXPANSION" if ratio6>1 else "CONTRACTION"}


def build_events(bars,p):
    """Independent feature-first pass; labels never accessed here."""
    parsed={};runs={};peer_context={}
    for symbol in p["scope"]["universe"]:
        raw,consecutive=strict_rows(bars[symbol])
        parsed[symbol]=raw;runs[symbol]=consecutive
        if symbol in PEERS:
            peer_context[symbol]=peer_past12(raw,consecutive)
    event_rows=[];availability=Counter();source_bars={}
    for symbol in p["scope"]["universe"]:
        a=parsed[symbol];run=runs[symbol]
        source_bars[symbol]=len(a)
        peers=[peer_context[q] for q in PEERS if q!=symbol and q in peer_context]
        for i,row in enumerate(a):
            t=int(row[1])
            if not p["scope"]["calendarStart"]<=t<p["scope"]["end"]:
                continue
            availability["observedCompletedM5"]+=1
            if run[i]<49:
                availability["causal49M5Missing"]+=1
                continue
            peers_at=[q.get(t) for q in peers]
            v=features_at(a,run,i,peers_at)
            if v is None:
                availability["noFrozenEventDefinitionTriggered"]+=1
                continue
            availability["causalEventIntents"]+=1
            event_rows.append(dict(s=symbol,t=t,index=i,**v))
    event_rows.sort(key=lambda e:(e["t"],e["s"]))
    return event_rows,parsed,runs,dict(availability),source_bars


def label_after_original_intent(events,parsed,runs,p):
    """Forward outcomes are strictly separate from event/feature creation.

    Full next-horizon bid-like M5 source path needed for excursions/labels;
    missing future never changes event, tags or feature vector.
    """
    out={h:[] for h in p["targets"]["horizonsM5"]}
    for event in events:
        s=event["s"];a=parsed[s];run=runs[s];idx=event["index"];t=event["t"]
        phase=("training" if t<p["scope"]["trainEnd"] else
               "selection" if t<p["scope"]["selectionEnd"] else "exposed_audit")
        limit=(p["scope"]["trainEnd"] if phase=="training" else
               p["scope"]["selectionEnd"] if phase=="selection" else p["scope"]["end"])
        for h in out:
            rec=dict(event,phase=phase,h=h,known=False,target=None)
            ending=idx+h+1
            if (ending>=len(a) or run[ending]<h+2 or
                int(a[ending][1])>=limit):
                out[h].append(rec);continue
            entry=float(a[idx+1][5])
            end=float(a[ending][5])
            if min(entry,end)<=0:
                out[h].append(rec);continue
            forwards=a[idx+2:ending+1]
            high=max(x[3] for x in forwards)
            low=min(x[4] for x in forwards)
            if high<=0 or low<=0:
                out[h].append(rec);continue
            m5ret=[log(a[j][5]/a[j-1][5]) for j in range(idx+2,ending+1)]
            future_vol=sqrt(sum(x*x for x in m5ret)/len(m5ret))
            scale=max(1e-8,event["vol5"]*sqrt(h))
            target=(cap(log(end/entry)/scale,8),
                    cap(log(high/entry)/scale,8),
                    cap(log(low/entry)/scale,8),
                    float(future_vol>event["vol5"]))
            out[h].append({**rec,"known":True,
                           "target":target,
                           "returnBps":10000*log(end/entry),
                           "futureHighBps":10000*log(high/entry),
                           "futureLowBps":10000*log(low/entry),
                           "targetScaleBps":10000*scale})
    return out

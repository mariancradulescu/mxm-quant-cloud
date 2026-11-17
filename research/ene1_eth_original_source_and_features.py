"""ENE1 original source geometry and ETHOHLCV multiscale predictors.

NEW economic-study source readback; CXL1 is used as encrypted original
protobuf SOURCE ONLY. Never import/run a closed CXL1 trading policy.
No M1 is reconstructed from M5; missing original quote remains UNKNOWN.
"""
from __future__ import annotations
import base64,hashlib,json,math,os
from collections import Counter
from datetime import date,datetime,timezone
from decimal import Decimal as D
from pathlib import Path
from statistics import median
from .cxl1_original_native_eur_readback import (
    read_archive,reconstruct,wire,quote_one,no_swap,
    SOURCE50,RECEIPT50,SOURCE275,RECEIPT275,PILOT_RUN)
from .cxl1_original_feasibility import (
    calendar,M5,DAY,DECISION_DELAY,EXIT_DELAY)
from .cxl1_original_275_source import earlier
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .decode import decode_bars,need

FROZEN=Path("research/ENE1_FROZEN_AUTHENTIC_ETH_NET_REGIME_20261117.md")
SOURCE275_RUN=43947388854
SCALE=D(100000)
MONDAY=int(datetime(2026,8,17,tzinfo=timezone.utc).timestamp()*1000)
WEEK=7*DAY
SLIPS={"central":D(".5"),"adverse":D("2")}
BASE_COLS=(0,2,5,10,11)
FULL_COLS=tuple(range(14))
TRAIN_WEEKS=6;CAL_WEEKS=3;EVAL_WEEKS=4
PRICE_SCALE=100000.

def sha(bs):return hashlib.sha256(bs).hexdigest()
def bounded(x):return max(-4.,min(4.,float(x)))
def rms(a):return math.sqrt(sum(x*x for x in a)/len(a))
def logret(a,b):return math.log(b/a)
def decimal(x):return D(str(x))

def source_original():
    secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(secret.strip()),"ENE1_SECRET_REQUIRED_IN_PROTECTED_CONTEXT")
    old,receipt0,h0=read_archive(SOURCE275,RECEIPT275,secret,SOURCE275_RUN,
       "MXM_CXL1_ORIGINAL_275_EARLIER_CLOSED_BAR_AND_QUOTE_SOURCE_V1",
       "MXM_CXL1_ORIGINAL_275_SOURCE_ONLY_V1",2757,275)
    last,receipt1,h1=read_archive(SOURCE50,RECEIPT50,secret,PILOT_RUN,
       "MXM_CXL1_ORIGINAL_FIRST_ONLY_PILOT_RAW_PROTOBUF_V1",
       "MXM_CXL1_ORIGINAL_PRESOURCE_PILOT_FEASIBILITY_V1",507,50)
    a,contract0,margin0,trader0,counts0=reconstruct(old,earlier())
    b,contract1,margin1,trader1,counts1=reconstruct(last,
         [(d,t) for d,t in calendar() if d>=date(2026,11,2)])
    need(len(a)==275 and len(b)==50,"ENE1_SOURCE_325_ROW_CENSUS")
    c=contract0["ETHUSD"];d=contract1["ETHUSD"]
    need(c.SerializeToString()==d.SerializeToString(),
         "ENE1_CONTRACT_DIFFERENCE_BETWEEN_SOURCE_SPLITS")
    need(margin0==margin1 and min(margin0)>0 and max(margin0)<=D(210),
         "ENE1_CURRENT_ORIGINAL_MARGIN_NOT_CERTIFIED")
    units=D(c.minVolume)/100;step=D(c.stepVolume)/100
    need(units>0 and step>0 and units<=c.maxVolume/100 and
         units==D(str(c.minVolume))/100,
         "ENE1_MIN_VOLUME_STEP_CONTRACT")
    books=[]
    for source,original_rows,tag in ((old,a,"EARLIER275"),(last,b,"PILOT50")):
        need(len(original_rows)==len(source["rows"]),"ENE1_WRONG_ORIGINAL_SOURCE")
        for j,row in enumerate(original_rows):
            t=int(row["t"]);raw=source["raw"][7+10*j+1]
            req,ans=wire(raw)
            need(type(req) is m.ProtoOAGetTrendbarsReq and
                 req.period==e.M5 and req.fromTimestamp==t-DAY-M5 and
                 req.toTimestamp==t and
                 row["day"]==datetime.fromtimestamp(t/1000,timezone.utc).date().isoformat(),
                 "ENE1_CRYPTO_ORIGINAL_M5_REQUEST_TIME")
            bar=None
            if type(ans) is m.ProtoOAGetTrendbarsRes and ans.HasField("hasMore") and not ans.hasMore:
                decoded=decode_bars(ans.trendbar,t-DAY-M5,t,5)
                observed={int(z[1]):z for z in decoded}
                times=[t-DAY+i*M5 for i in range(289)]
                if all(u in observed for u in times):
                    bar=[observed[u] for u in times]
                    need(all(z[1]-z[0]==M5 and z[4]>0 and
                             z[4]<=min(z[2],z[5])<=max(z[2],z[5])<=z[3] and
                             z[6]>=0 for z in bar),
                             "ENE1_SOURCE_M5_BAR_INVARIANT")
            note=row["pre"]["ETHUSD"]
            need((bar is None)==(note is None),"ENE1_AUTHENTIC_ETH_SOURCE_FEATURE_BINDING")
            if bar is not None:
                close15=[x[5] for x in bar]
                # Compare original CXL1 source reader's ETH 15m feature
                # SOURCE FEATURE ONLY, never its closed strategy/result.
                from .cxl1_original_feasibility import crypto_features
                check=crypto_features(close15)
                need(check is not None and all(abs(float(x)-float(y))<1e-10
                      for x,y in zip(check,note)),"ENE1_ETH_M15_ORIGINAL_REBUILD")
            books.append(dict(t=t,day=row["day"],source=tag,
                originalM5=bar,marks=row["marks"]))
    expected=[t for _,t in calendar()]
    need([x["t"] for x in books]==expected,"ENE1_FIXED_325_CLOCK_ORDER")
    sourceReceipt=dict(originalEarlierRun=SOURCE275_RUN,originalPilotRun=PILOT_RUN,
        originalCipherSha256=[h0["cipherSha256"],h1["cipherSha256"]],
        originalPlaintextSha256=[h0["plainSha256"],h1["plainSha256"]],
        originalEncryptedAccountAndProtobufVerified=True,
        currentOriginalMinimumUnits=str(units),currentStepUnits=str(step),
        originalMaximumMarginEur=str(max(margin0)),
        sourceOnlyReadbackNoCxlPolicyExecuted=True,newBrokerRequests=0)
    return books,c,max(margin0),trader0,sourceReceipt

def features_from_original_m5(bars,t):
    if bars is None:return None,"AUTHENTIC_289_BAR_M5_REQUIRED"
    if len(bars)!=289 or bars[-1][1]!=t or bars[0][1]!=t-DAY or any(
        a[1]+M5!=b[1] for a,b in zip(bars,bars[1:])):
        return None,"AUTHENTIC_M5_NOT_CONTIGUOUS"
    b=[[float(z)/PRICE_SCALE for z in row[2:6]]+[int(row[6])] for row in bars]
    close=[x[3] for x in b]
    returns=[logret(a,c) for a,c in zip(close,close[1:])]
    sigma=max(.0001,rms(returns))
    trend=lambda k:bounded(sum(returns[-k:])/(sigma*math.sqrt(k)))
    recent12=returns[-12:];prior48=returns[-60:-12]
    acceleration=bounded(rms(recent12)/max(.0001,rms(prior48))-1)
    recentBars=b[-6:]
    top=sum(x[1]-max(x[0],x[3]) for x in recentBars)
    bottom=sum(min(x[0],x[3])-x[2] for x in recentBars)
    wid=sum(x[1]-x[2] for x in recentBars)
    wick=bounded((top-bottom)/max(1e-9,wid))
    bodies=[x[3]-x[0] for x in b[-12:]]
    efficiency=bounded(sum(bodies)/max(1e-9,sum(abs(x) for x in bodies)))
    r12=sum(z[1]-z[2] for z in b[-12:])/12
    ref48=median([z[1]-z[2] for z in b[-60:-12]])
    compression=bounded(r12/max(1e-9,ref48)-1)
    v12=sum(z[4] for z in b[-12:])
    v48=sum(z[4] for z in b[-60:-12])
    activity=bounded(v12/(v48/48*12)-1) if v48>0 else 0.
    hour=(t%(24*3600000))/3600000
    f=[trend(1),trend(3),trend(6),trend(12),trend(48),
       acceleration,wick,efficiency,compression,activity,
       math.sin(2*math.pi*hour/24),math.cos(2*math.pi*hour/24)]
    f.extend([bounded(wick*acceleration),bounded(f[1]*f[4])])
    need(len(f)==14 and all(math.isfinite(v) for v in f),
         "ENE1_FIXED_14_FEATURES_INVALID")
    # Exact authentic 3/6/12/48 completed M5 bars prove M15/M30/H1/H4
    # features. They do NOT prove a historical original ETH M1 stream.
    return f,None

def quote_event(row,contract,margin,trader):
    t=row["t"];a=t+DECISION_DELAY;z=a+EXIT_DELAY
    no_swap(contract,trader,a,z)
    try:
        if any(row["marks"][k][s] is None for k in ("entry","exit")
               for s in ("ETHUSD","EURUSD")):
            return dict(entry=None,exit=None,reason="ORIGINAL_BIDASK_OR_EURUSD_UNKNOWN")
        q0=quote_one(row["marks"]["entry"],a,contract,margin)
        qz=quote_one(row["marks"]["exit"],z,contract,margin)
        return dict(entry=q0,exit=qz,reason=None)
    except Exception as exc:
        # Never turn an invalid future quote/cost into a profitable label.
        return dict(entry=None,exit=None,reason="CONVERSION_ORIGINAL_CONTRACT_UNPRICED")

def payoff(row,side,scenario,units):
    if row["entry"] is None or row["exit"] is None:return None
    ent=row["entry"];end=row["exit"]
    eb,ea=decimal(ent["Bid"]),decimal(ent["Ask"])
    zb,za=decimal(end["Bid"]),decimal(end["Ask"])
    start=(eb+ea)/2;finish=(zb+za)/2
    slip=SLIPS[scenario]
    x=start*slip/D(20000);y=finish*slip/D(20000)
    opening=ea+x if side>0 else eb-x
    closing=zb-y if side>0 else za+y
    usd=D(side)*units*(closing-opening)
    fx=decimal(end["EurCredit"] if usd>=0 else end["EurDebit"])
    fee=(decimal(ent["ExitFeePerUnit"])+decimal(end["ExitFeePerUnit"]))*units
    net=usd*fx-fee
    return float(net)

def make_source_population():
    books,c,m,trader,src=source_original()
    counts=Counter()
    rows=[]
    for row in books:
        t=row["t"];week=(t-MONDAY)//WEEK
        feat,why=features_from_original_m5(row["originalM5"],t)
        quoted=quote_event(row,c,m,trader)
        status=why or "FEATURE_COMPLETE"
        if feat is None:counts["feature_unknown"]+=1
        else:counts["feature_complete"]+=1
        price={}
        for scenario in ("central","adverse"):
            for side in (1,-1):
                price[scenario,side]=payoff(quoted,side,scenario,D(c.minVolume)/100)
        for side in (1,-1):
            if price["adverse",side] is not None:counts["adverse_label_known"]+=1
            else:counts["adverse_label_unknown"]+=1
        if quoted["entry"] is not None:counts["entry_quote_known"]+=1
        if quoted["exit"] is not None:counts["exit_quote_known"]+=1
        rows.append(dict(t=t,week=week,day=row["day"],features=feat,
            sourceState=status,quoteSourceState=quoted["reason"],quoted=quoted,labels=price))
    need(len(rows)==325 and all(0<=z["week"]<13 for z in rows),
         "ENE1_EXACT_CALENDAR_325")
    return rows,c,m,src,dict(counts)

"""MRF1: new authentic M1 price-path and multiscale regime discovery.
NEVER generates M1 from M5; never runs closed CXL1 economic scorer, HXP1 or PVE3.
Original HXC1 raw request/response verified; CXL1 raw source reused ONLY for
genuine original EURUSD 30m entry/exit BIDASK model, not for prior policies.
"""
from __future__ import annotations
import json,math,os,base64,subprocess,tempfile
from collections import Counter,defaultdict
from datetime import datetime,date,timedelta,timezone
from decimal import Decimal as D
from pathlib import Path
from hashlib import sha256
from bisect import bisect_right
import numpy as np

from .custody import unseal_new
from .hxc1_historical_readback import validate as verify_hxc_original
from .cxl1_original_native_eur_readback import (
    read_archive,reconstruct,dec,q10,SOURCE50,RECEIPT50,SOURCE275,
    RECEIPT275,PILOT_RUN)
from .cxl1_original_275_source import earlier
from .cxl1_original_feasibility import calendar,DECISION_DELAY,EXIT_DELAY
from .rne1_source_financial_preflight import fee_usd

P=Path("research/MRF1_FROZEN_AUTHENTIC_M1_MULTIRESOLUTION_PROTOCOL_20261117.md")
HXC_RUN=43817213663; CXL_275_RUN=43947388854
SYMS=("EURUSD","XAUUSD","US500","NAS100")
M=60000; H=3600000;W=7*24*H
START=int(datetime(2026,10,19,tzinfo=timezone.utc).timestamp()*1000)
END=int(datetime(2026,11,16,tzinfo=timezone.utc).timestamp()*1000)
SCENARIOS={"central":D(".5"),"adverse":D("2")}
HORIZONS=(5,30,120)
# All global policies MUST retain every predeclared symbol and horizon.
EPS=1e-12

def need(v,why):
    if not v:raise ValueError("MRF1_"+why)
def clamp(v):return float(max(-4.,min(4.,float(v))))
def mean(v):return float(np.mean(v)) if len(v) else 0.
def rms(v):return float(np.sqrt(np.mean(np.asarray(v,float)**2)))
def sign(x):return 1 if x>0 else -1 if x<0 else 0

def strict_aggregate(bars,source_minutes,target_minutes):
    """Convert genuine fine OHLCV ONLY into a coarser authentic-derived series."""
    need(target_minutes%source_minutes==0,"ONLY_COARSER_AUTHENTIC_AGGREGATION")
    width=target_minutes//source_minutes;step=target_minutes*M
    groups=defaultdict(list)
    for r in bars:
        groups[((r[1]-1)//step+1)*step].append(r)
    out=[]
    for end,rows in sorted(groups.items()):
        x=sorted(rows,key=lambda z:z[0])
        if (len(x)!=width or x[0][0]!=end-step or x[-1][1]!=end or
            any(a[1]!=b[0] for a,b in zip(x,x[1:]))):continue
        out.append([end-step,end,x[0][2],max(y[3] for y in x),
                    min(y[4] for y in x),x[-1][5],sum(y[6] for y in x)])
    return out

def validate_original_sources():
    secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(secret.strip()),"CUSTODY_SECRET_REQUIRED")
    envelope=Path("hxc1-source/source.envelope.json").read_bytes()
    receipt=json.loads(Path("hxc1-source/receipt.public.json").read_text())
    need(sha256(envelope).hexdigest()==receipt["ciphertextSha256"],
         "HXC1_ORIGINAL_CIPHERTEXT_HASH")
    original=json.loads(unseal_new(envelope,secret,str(HXC_RUN)))
    proved=verify_hxc_original(original,receipt,str(HXC_RUN))
    need(proved["status"]=="HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT" and
         proved["rawRequestsRebuilt"]==1444,
         "HXC1_SOURCE_RAW_OR_ACCOUNT_AUTHENTICITY")
    # Original independent CXL1 broker account/quote source, strictly source
    # reconstruction. NEVER call CXL1.calculate, make_facts, side or closed model.
    old275,_,h275=read_archive(SOURCE275,RECEIPT275,secret,CXL_275_RUN,
        "MXM_CXL1_ORIGINAL_275_EARLIER_CLOSED_BAR_AND_QUOTE_SOURCE_V1",
        "MXM_CXL1_ORIGINAL_275_SOURCE_ONLY_V1",2757,275)
    old50,_,h50=read_archive(SOURCE50,RECEIPT50,secret,PILOT_RUN,
        "MXM_CXL1_ORIGINAL_FIRST_ONLY_PILOT_RAW_PROTOBUF_V1",
        "MXM_CXL1_ORIGINAL_PRESOURCE_PILOT_FEASIBILITY_V1",507,50)
    preceding,contracts0,_,trader0,_=reconstruct(old275,earlier())
    latest,contracts1,_,trader1,_=reconstruct(old50,
        [(d,t) for d,t in calendar() if d>=date(2026,11,2)])
    need(contracts0["EURUSD"].SerializeToString()==
         contracts1["EURUSD"].SerializeToString(),
         "ORIGINAL_EURUSD_CONTRACT_CHANGED")
    c=contracts0["EURUSD"]
    terms=json.loads(Path("docs/CMA1_AUTHENTIC_CONTRACT_TERMS_20261108.json").read_text())
    own=terms["instruments"]["EURUSD"]
    need(terms["originalPepperstoneEurAccountVerified"] is True and
         terms["originalSourceReadbackVerified"] is True and
         terms["termsDate"]=="2026-11-04" and
         dec(own["currentMinMarginEur"])==D("33.33") and
         c.minVolume//100==1000 and
         dec(terms["sharedCurrentContract"]["commissionPerLotPerSideUsdFromNativeCurrentModel"])==D(3),
         "ORIGINAL_CURRENT_BROKER_TERMS_UNSUPPORTED")
    genuine={}
    for row in preceding+latest:
        t=row["t"]
        if START<=t<END and
           datetime.fromtimestamp(t/1000,timezone.utc).hour in (8,10,12,14):
            genuine[t]=row["marks"]
    need(len(genuine)==80,"ORIGINAL_PREDECLARED_EURUSD_80_CLOCKS")
    return original["bars"],genuine,c,dict(
        hxcRunId=HXC_RUN,hxcCiphertextSha256=sha256(envelope).hexdigest(),
        hxcSourceProtocolSha256=proved["protocolSha256"],
        hxcRawBrokerRequestsProven=1444,hxcOriginalSourceCounts=proved["sourceCounts"],
        cxl275RunId=CXL_275_RUN,cxlPilotRunId=PILOT_RUN,
        cxlOriginalCiphertextSha256=[h275["cipherSha256"],h50["cipherSha256"]],
        cxlOriginalPlaintextSha256=[h275["plainSha256"],h50["plainSha256"]],
        currentTariffHistoricalContinuityCertified=False,
        sourceAccountBoundAndRawProtobufRebuilt=True,
        newBrokerRequests=0,oldClosedStrategiesExecuted=0)

def prepare(bars):
    result={};proof={}
    for s in SYMS:
        raw={}
        for tf in ("M1","M15","H1"):
            data=bars.get(s+"/"+tf)
            need(data and len(data)>100,"ORIGINAL_INSTRUMENT_RESOLUTION_MISSING")
            raw[tf]=[[int(a[0]),int(a[1]),*(float(x)/100000 for x in a[2:6]),int(a[6])] for a in data]
        derived={"M5":strict_aggregate(raw["M1"],1,5),
            "M30":strict_aggregate(raw["M15"],15,30),
            "H4":strict_aggregate(raw["H1"],60,240),
            "D1":strict_aggregate(raw["H1"],60,1440)}
        streams={**raw,**derived}
        result[s]={key:dict(rows=rr,ends=[v[1] for v in rr],
            byend={v[1]:v for v in rr},bystart={v[0]:v for v in rr})
                   for key,rr in streams.items()}
        proof[s]={key:len(rr) for key,rr in streams.items()}
    return result,proof

def exact_prefix(stream,t,n,span):
    """Strict same-resolution n completed bars; no assumed session continuity."""
    return [stream["byend"].get(t-(n-1-i)*span) for i in range(n)] if all(
        (t-j*span in stream["byend"] and
         stream["byend"][t-j*span][0]==t-(j+1)*span)
        for j in range(n)) else None

def most_recent(stream,t,n,span):
    ends=stream["ends"];i=bisect_right(ends,t)
    if i<n:return None
    end=ends[i-1]
    if t-end>span:return None
    return exact_prefix(stream,end,n,span)

def frame(symbol,streams,t):
    obj=streams[symbol];m1=exact_prefix(obj["M1"],t,61,M)
    m5=exact_prefix(obj["M5"],t,7,5*M)
    if m1 is None or m5 is None:return None,"M1_OR_M5_REQUIRED_CONTIGUITY_UNKNOWN"
    raw=np.asarray([math.log(m1[i][5]/m1[i-1][5]) for i in range(1,61)],float)
    sig=max(.0001,rms(raw))
    recent=raw[-5:];prior=raw[-60:-5]
    pathEff=sum(recent)/max(EPS,sum(abs(v) for v in recent))
    accel=rms(recent)/max(.0001,rms(prior))-1
    flips=sum(sign(recent[i])!=sign(recent[i-1]) for i in range(1,5))/4
    old=raw[-55:-5]
    oldFlip=sum(sign(old[i])!=sign(old[i-1]) for i in range(1,len(old)))/max(1,len(old)-1)
    act=sum(v[6] for v in m1[-5:])/(sum(v[6] for v in m1[:-5])/56*5)-1 if sum(v[6] for v in m1[:-5])>0 else 0.
    mr=m5[-1][3]-m5[-1][4]
    m5body=(m5[-1][5]-m5[-1][2])/max(EPS,mr)
    m5move=math.log(m5[-1][5]/m5[-2][5])/max(.0001,sig*math.sqrt(5))
    m5trend=math.log(m5[-1][5]/m5[0][5])/max(.0001,sig*math.sqrt(30))
    h1=most_recent(obj["H1"],t,8,H)
    h1trend=0.;h1comp=0.
    if h1 is not None:
        h1trend=math.log(h1[-1][5]/h1[0][5])/max(.0001,sig*math.sqrt(420))
        h1comp=(h1[-1][3]-h1[-1][4])/max(EPS,mean([v[3]-v[4] for v in h1[:-1]]))-1
    opt=[]
    rawOptional={}
    for key,n,span in (("M15",2,15*M),("M30",2,30*M),
                        ("H4",2,4*H),("D1",2,DAY)):
        x=most_recent(obj[key],t,n,span)
        rawOptional[key]=x is not None
        val=math.log(x[-1][5]/x[-2][5])/max(.0001,sig*math.sqrt(span/M)) if x is not None else 0
        opt.extend((clamp(val),float(x is not None)))
    hour=(t%(24*H))/H
    # core length 23: M1 4, M5 3, H1 3 (including validity),
    # optional 8, time 2, one-hot 4, interactions 2 -> 26.
    x=[clamp(pathEff),clamp(accel),clamp(flips-oldFlip),clamp(act),
       clamp(m5body),clamp(m5move),clamp(m5trend),
       clamp(h1trend),clamp(h1comp),float(h1 is not None)]
    x.extend(opt)
    x.extend([math.sin(2*math.pi*hour/24),math.cos(2*math.pi*hour/24)])
    x.extend([float(symbol==s) for s in SYMS])
    x.extend([clamp(pathEff*h1trend),clamp(accel*(opt[4] if rawOptional["H4"] else 0))])
    need(len(x)==26 and all(math.isfinite(v) for v in x),"FIXED_FEATURE_FRAME_INVALID")
    return dict(t=t,s=symbol,week=(t-START)//W,features=x,sig=sig,
                tfAvailable=dict(M1=True,M5=True,M15=rawOptional["M15"],
                    M30=rawOptional["M30"],H1=h1 is not None,
                    H4=rawOptional["H4"],D1=rawOptional["D1"])),None

def source_price_label(row,stream,minutes):
    t=row["t"];byopen=stream["M1"]["bystart"]
    future=[byopen.get(t+i*M) for i in range(minutes)]
    if any(v is None or v[0]!=t+i*M or v[1]!=t+(i+1)*M
           for i,v in enumerate(future)):
        return None
    start=future[0][2];end=future[-1][5]
    if start<=0 or end<=0:return None
    sig=max(.0001,row["sig"]*math.sqrt(minutes))
    return dict(y=math.log(end/start)/sig,priceReturn=math.log(end/start),
                at=t,exitAt=t+minutes*M)

def calendar_rows(streams):
    rows=[];counts=Counter()
    for d in range(28):
        day=datetime.fromtimestamp((START+d*24*H)/1000,timezone.utc)
        if day.weekday()>=5:continue
        for k in range(17):
            t=START+d*24*H+8*H+k*30*M
            for s in SYMS:
                counts["scheduled"]+=1
                f,why=frame(s,streams,t)
                if f is None:
                    counts[why]+=1;continue
                f["labels"]={minutes:source_price_label(f,streams[s],minutes)
                             for minutes in HORIZONS}
                for minutes in HORIZONS:
                    counts[str(minutes)+"_labelKnown" if f["labels"][minutes] is not None else
                        str(minutes)+"_labelUnknown"]+=1
                rows.append(f)
    need(counts["scheduled"]==1360,"SCHEDULED_POPULATION_1360")
    return rows,dict(counts)

def fit_ridge(X,y,symbols,columns):
    a=np.column_stack((np.ones(len(X)),X[:,columns]))
    weights=np.asarray([1/max(1,sum(symbols==s)) for s in symbols],float)
    weights*=len(X)/len(set(symbols))
    gram=a.T@(a*weights[:,None])
    gram[1:,1:]+=64*np.eye(len(columns))
    return np.linalg.solve(gram,a.T@(weights*y))
BASE_COLS=[4,5,6,7,8,9,18,19,20,21,22,23]
FULL_COLS=list(range(26))

def to_euro_quote(market,at,commission,volume,margin):
    if market is None or any(pair is None or len(pair)!=2 for pair in (market,)):
        return None
    pair=market
    bidRaw,askRaw=pair[0],pair[1]
    need(bidRaw[0]<=at and askRaw[0]<=at and
         bidRaw[0]>=at-20000 and askRaw[0]>=at-20000,
         "ORIGINAL_EURUSD_QUOTE_TIMING")
    bid=dec(bidRaw[1])/D(100000);ask=dec(askRaw[1])/D(100000)
    need(bid>0 and ask>=bid,"ORIGINAL_EURUSD_CROSSED_QUOTE")
    # EURUSD base currency EUR: original bid/ask gives genuine USD/EUR
    # credit/debit conversion, not a made-up mid exchange rate.
    credit=1/ask;debit=1/bid
    oneSideFee=fee_usd(commission,volume,(bid+ask)/2)
    feePerUnit=q10(oneSideFee*debit/volume)
    return dict(Symbol="EURUSD",At=at,Bid=str(bid),Ask=str(ask),
        EurCredit=str(q10(credit)),EurDebit=str(q10(debit)),
        ExitFeePerUnit=str(feePerUnit),ExitFeeFloor="0",
        MarginPerUnit=str(q10(margin/volume)))

def original_finance_points(quote_source,contract):
    expected={START+d*24*H+h*H+30*M for d in range(28)
              if datetime.fromtimestamp((START+d*24*H)/1000,timezone.utc).weekday()<5
              for h in (8,10,12,14)}
    need(len(expected)==80 and set(quote_source)==expected,
         "MRF1_SOURCE_PROVENANCE_80_CLOCKS")
    out={}
    for t in sorted(expected):
        marks=quote_source[t]
        entry=t+DECISION_DELAY;exit=t+EXIT_DELAY+DECISION_DELAY
        a=to_euro_quote(marks["entry"]["EURUSD"],entry,contract,D(1000),D("33.33")) if marks["entry"]["EURUSD"] is not None else None
        z=to_euro_quote(marks["exit"]["EURUSD"],exit,contract,D(1000),D("33.33")) if marks["exit"]["EURUSD"] is not None else None
        out[t]=dict(entry=a,exit=z,originalEntryAt=entry,originalExitAt=exit)
    return out

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

def fit_and_evaluate(rows):
    import scipy  # only to ensure no local custom mathematical engine dependence? (not needed)
    del scipy
    X=np.asarray([row["features"] for row in rows],float)
    syms=np.asarray([row["s"] for row in rows])
    weeks=np.asarray([row["week"] for row in rows])
    due={h:np.asarray([row["labels"][h]["exitAt"] if row["labels"][h] is not None else 0
                       for row in rows]) for h in HORIZONS}
    stats=[];predictions={};parity=[];modelDigest=sha256();models=[];population=Counter()
    for week in (2,3):  # only original evaluation weeks, fixed
        boundary=START+week*W
        for minutes in HORIZONS:
            label=np.asarray([row["labels"][minutes]["y"]
                    if row["labels"][minutes] is not None else 0.
                    for row in rows],float)
            known=np.asarray([row["labels"][minutes] is not None for row in rows])
            train=known&(weeks<week-1)&(due[minutes]<boundary-W-120*M)
            cal=known&(weeks==week-1)&(due[minutes]<boundary-120*M)
            idx=np.flatnonzero(weeks==week)
            need(train.sum()>=60 and cal.sum()>=60 and len(idx)>50,
                 "TRAINING_CALIBRATION_EVAL_MINIMUM_H"+str(minutes)+"_W"+str(week))
            for variant,cols in (("FULL",FULL_COLS),("BASE",BASE_COLS)):
                beta=fit_ridge(X[train],label[train],syms[train],cols)
                cal_pred=np.column_stack((np.ones(cal.sum()),X[cal][:,cols]))@beta
                quantiles=np.quantile(label[cal]-cal_pred,(np.arange(16)+.5)/16)
                pred=np.column_stack((np.ones(len(idx)),X[idx][:,cols]))@beta
                good=known[idx];y=label[idx][good]
                actual=pred[good]
                probs=np.mean(actual[:,None]+quantiles[None,:]>0,axis=1)
                stat=dict(week=week+1,horizonMinutes=minutes,variant=variant,
                    featureComplete=len(idx),labelKnown=int(good.sum()),
                    labelUnknown=int((~good).sum()),trainingMatured=int(train.sum()),
                    calibrationMatured=int(cal.sum()),
                    normalizedPriceMse=float(np.mean((actual-y)**2)),
                    zeroMovementMse=float(np.mean(y*y)),
                    normalizedPriceMae=float(np.mean(np.abs(actual-y))),
                    brierDirectional=float(np.mean((probs-(y>0))**2)),
                    meanPositiveForecastProbability=float(np.mean(probs)),
                    observedPositiveMoveFraction=float(np.mean(y>0)),
                    calibratedThrough=int(max(due[minutes][cal])),
                    predictionSignAccuracy=float(np.mean((actual>0)==(y>0))))
                stats.append(stat)
                models.append(dict(week=week+1,horizonMinutes=minutes,
                    variant=variant,columns=cols,coefficients=beta.tolist(),
                    residualQuantiles=quantiles.tolist(),
                    calibrationMaturedThrough=stat["calibratedThrough"]))
                for j,i in enumerate(idx):
                    key=(int(rows[i]["t"]),rows[i]["s"],minutes,variant)
                    predictions[key]=dict(mean=float(pred[j]),
                        quantile=[float(v) for v in quantiles],due=int(rows[i]["t"]+minutes*M),
                        calibrationThrough=stat["calibratedThrough"])
                    modelDigest.update(json.dumps(dict(key=key,mean=float(pred[j])),
                        sort_keys=True,separators=(",",":")).encode())
                    if len(parity)<24:
                        parity.append(dict(features=rows[i]["features"],
                            columns=cols,coefficients=beta.tolist(),
                            expected=float(pred[j])))
                    population[(variant,minutes,"predictions")]+=1
                    if rows[i]["labels"][minutes] is not None:
                        population[(variant,minutes,"priced")]+=1
            print("MRF1_CHRONOLOGICAL_WEEK_HORIZON",week+1,minutes,flush=True)
    paired=[]
    for week in (3,4):
        for minutes in HORIZONS:
            a=next(x for x in stats if x["week"]==week and x["horizonMinutes"]==minutes and x["variant"]=="FULL")
            b=next(x for x in stats if x["week"]==week and x["horizonMinutes"]==minutes and x["variant"]=="BASE")
            need(a["labelKnown"]==b["labelKnown"] and
                 a["featureComplete"]==b["featureComplete"],"PAIR_UNMATCHED")
            paired.append(dict(week=week,horizonMinutes=minutes,
                fullMinusBaseMseBenefit=b["normalizedPriceMse"]-a["normalizedPriceMse"],
                fullMinusZeroMseBenefit=a["zeroMovementMse"]-a["normalizedPriceMse"],
                labelKnown=a["labelKnown"],priceMse=a["normalizedPriceMse"],
                baselineMse=b["normalizedPriceMse"],zeroMovementMse=a["zeroMovementMse"]))
    return dict(metrics=stats,models=models,
                predictionHashSha256=modelDigest.hexdigest(),
                nativeModelParityInputs=parity,paired=paired,
                scoredByVariantAndHorizon={str(k):v for k,v in population.items()},
                multipleComparisonsSix=True,
                inferentialConfidence="UNKNOWN_TWO_EXPOSED_EVALUATION_WEEKS_NOT_INDEPENDENT"),predictions

def commission_one_leg(contract,units,mid,eur_debit):
    value=fee_usd(contract,units,mid)
    need(value>=0,"EURUSD_COMMISSION_NEGATIVE")
    return value*eur_debit

def actual_original_eur_payoff(entry,exit,side,units,scenario):
    e={k:dec(entry[k]) for k in ("Bid","Ask","EurCredit","EurDebit","ExitFeePerUnit")}
    z={k:dec(exit[k]) for k in ("Bid","Ask","EurCredit","EurDebit","ExitFeePerUnit")}
    slip=SCENARIOS[scenario]
    emid=(e["Ask"]+e["Bid"])/2
    zmid=(z["Ask"]+z["Bid"])/2
    s0=emid*slip/D(20000)
    s1=zmid*slip/D(20000)
    opening=e["Ask"]+s0 if side>0 else e["Bid"]-s0
    closing=z["Bid"]-s1 if side>0 else z["Ask"]+s1
    usd=D(side)*units*(closing-opening)
    gross=D(side)*units*(zmid-emid)*(z["EurCredit"]+z["EurDebit"])/2
    transfer=usd*(z["EurCredit"] if usd>=0 else z["EurDebit"])
    fees=(e["ExitFeePerUnit"]+z["ExitFeePerUnit"])*units
    return dict(netEur=float(transfer-fees),grossMidpointEur=float(gross),
                frictionEur=float(gross-transfer+fees),commissionEur=float(fees))

def calibrated_quote_cost_prior(source,t):
    # Only fully observed prior ORIGINAL entry/exit quotes mature before T.
    # Future historical quotes exist in archive but are forbidden as prior.
    spreads=[]
    for when,x in source.items():
        if when+EXIT_DELAY>=t-120*M:continue
        if x["entry"] is None or x["exit"] is None:continue
        for key in ("entry","exit"):
            z=x[key];spreads.append(dec(z["Ask"])-dec(z["Bid"]))
    return None if len(spreads)<20 else float(np.median(np.asarray(spreads,float)))

def money_offer(row,forecast,quote,spreadPrior,policy,contract,t,scenario):
    entry=quote["entry"]
    if entry is None:return None
    if forecast["calibrationThrough"]>=t-120*M:
        raise ValueError("MRF1_FINANCIAL_FORECAST_EMBARGO")
    units=D(1000);mid=(dec(entry["Ask"])+dec(entry["Bid"]))/2
    eurRate=dec(entry["EurDebit"])
    sigma=D(str(max(.0001,row["sig"]*math.sqrt(30))))
    moveScale=units*mid*sigma*eurRate
    entryHalfSpread=(dec(entry["Ask"])-dec(entry["Bid"]))/2
    # Exit spread is estimated only from earlier original source; NEVER
    # supplied by the current future 'exit' mark in the prediction.
    priorExitHalfSpread=dec(spreadPrior)/2
    slip=SCENARIOS[scenario]
    slipPerSide=mid*slip/D(20000)
    estimatedFees=dec(entry["ExitFeePerUnit"])*units*2
    modeledCost=(entryHalfSpread+priorExitHalfSpread+2*slipPerSide)*units*eurRate+estimatedFees
    q=np.asarray(forecast["quantile"],float)
    actual=[]
    risks=[];scores=[];means=[]
    for side in (1,-1):
        scenarios=[float(D(side)*moveScale*D(str(forecast["mean"]+res))-modeledCost)
                   for res in q]
        scenarios=sorted(scenarios) # conservative comonotonic joint loss
        worst=max(0.,-mean(scenarios[:4]))
        base=float(D(side)*moveScale*D(str(forecast["mean"]))-modeledCost)
        score=base-.5*worst
        actual.append(scenarios);risks.append(max(.01,3*worst));scores.append(score)
        means.append(base)
    return dict(At=t+DECISION_DELAY+1,ExitAt=t+DECISION_DELAY+EXIT_DELAY,
        Symbol="EURUSD",Variant=policy,CalibratedThrough=forecast["calibrationThrough"],
        MinUnits="1000",MinMarginEur="33.33",
        MeanAdverseEur=means,RiskEur=risks,ActionScore=scores,
        ScenarioNetEur=actual)

def financial_input(rows,predictions,quote_source,scenario):
    by_t={(r["t"],r["s"]):r for r in rows}
    offers=[];quotes=[];diag=Counter();observed=[]
    for t,source in sorted(quote_source.items()):
        week=(t-START)//W
        if week<2:continue
        diag["evaluationScheduled"]+=1
        row=by_t.get((t,"EURUSD"))
        if row is None:
            diag["predecisionFeatureUnknown"]+=1;continue
        if source["entry"] is None or source["exit"] is None:
            diag["genuineQuotePairMissing"]+=1
        else:
            diag["genuineQuotePairKnown"]+=1
            for action in (1,-1):
                for scen in SCENARIOS:
                    d=actual_original_eur_payoff(source["entry"],source["exit"],
                                                action,D(1000),scen)
                    observed.append(dict(week=week+1,scenario=scen,side=action,
                                         knownModelUnfundedCounterfactual=d))
        prior=calibrated_quote_cost_prior(quote_source,t)
        if prior is None:
            diag["sourceBasedPriorSpreadInsufficient"]+=1;continue
        if source["entry"] is None:
            continue
        # The real future exit quote is not read or passed to the offer builder.
        for variant in ("FULL","BASE"):
            forecast=predictions.get((t,"EURUSD",30,variant))
            if forecast is None:
                diag["forecastUnknown_"+variant]+=1;continue
            signal=money_offer(row,forecast,source,prior,variant,None,t,scenario)
            if signal is None:continue
            offers.append(signal)
            diag["positive_"+variant]+=int(max(signal["ActionScore"])>0)
        # Original entry and exit marks are used in chronological native
        # ledger replay ONLY; never as a future input to a decision at T.
        if source["entry"] is not None:
            quotes.append(source["entry"])
        if source["exit"] is not None:
            quotes.append(source["exit"])
    need(diag["evaluationScheduled"]==40,"EURUSD_EVALUATION_40_CLOCKS")
    # Two distinct 40-clock policy books share one identical quote event tape.
    unique={(q["At"],q["Symbol"]):q for q in quotes}
    return dict(Start=START+2*W,End=END,Scenario=scenario,
        Quotes=sorted(unique.values(),key=lambda z:z["At"]),
        Offers=offers),dict(diag),observed

def main():
    need(P.exists() and "FROZEN" in P.read_text(),"EXACT_PRESOURCE_PROTOCOL_MISSING")
    original,quotesource,contract,sourceMeta=validate_original_sources()
    streams,sourceTfCounts=prepare(original)
    rows,census=calendar_rows(streams)
    report,forecasts=fit_and_evaluate(rows)
    populated=dict(schema="MXM_MRF1_NEW_ORIGINAL_M1_INFORMATION_7TF_THREE_HORIZON_V1",
        sourceAuthenticity=sourceMeta,originalSourceTfCounts=sourceTfCounts,
        sourceCalendar=dict(scheduled=1360,featureKnown=len(rows),
            missingReasons=census),
        frozenProtocolSha256=sha256(P.read_bytes()).hexdigest(),
        implementationSha256=sha256(Path(__file__).read_bytes()).hexdigest(),
        originalRunId=os.environ.get("GITHUB_RUN_ID"),
        predictive=report,
        economicDomain="ORIGINAL_EURUSD_BIDASK_PLUS_CURRENT_ORIGINAL_BROKER_TARIFF_CONDITIONAL_MODELED_FILL",
        originalCxl1PoliciesOrScorersCalled=False,
        otherClosedModelsCalled=False,newBrokerRequests=0,ordersSubmitted=0,
        cloudActivated=False,qualified=False,independentConfirmation=False,
        continuousFloatingDrawdownCertified=False,historicalTariffContinuityCertified=False)
    Path("mrf1-original-predictive.json").write_text(json.dumps(
        populated,sort_keys=True,indent=2,allow_nan=False)+"\n")
    dotnet=os.environ.get("MRF1_DOTNET","dotnet")
    dll="src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
    with tempfile.TemporaryDirectory(prefix="mrf1-private-") as td:
        a=Path(td)/"in.json";z=Path(td)/"out.json"
        a.write_text(json.dumps(report["nativeModelParityInputs"],allow_nan=False))
        test=subprocess.run([dotnet,dll,str(a),str(z),"--mrf1-parity"],
                            capture_output=True,text=True,timeout=180)
        need(test.returncode==0 and z.exists(),"CSHARP_PREDICTIVE_PARITY_FAILURE")
        populated["nativePredictorParity"]=json.loads(z.read_text())
        for scenario in SCENARIOS:
            facts,census,originalCounterfactuals=financial_input(rows,forecasts,quotesource,scenario)
            a.write_text(json.dumps(facts,allow_nan=False,separators=(",",":")))
            # Seal original native inputs in protected workflow memory; the
            # financial source quotes are never copied into public JSON.
            populated["nativeInput"+scenario+"Sha256"]=sha256(a.read_bytes()).hexdigest()
            response=subprocess.run([dotnet,dll,str(a),str(z),"--native-mrf1"],
                                    capture_output=True,text=True,timeout=1800)
            if response.returncode!=0 or not z.exists():
                populated["native_"+scenario]=dict(status="UNKNOWN_NATIVE_FAILURE",
                        stderr=response.stderr[-300:],returnCode=response.returncode)
                Path("mrf1-original-public.json").write_text(json.dumps(populated,
                    sort_keys=True,indent=2,allow_nan=False)+"\n")
                raise RuntimeError("MRF1_NATIVE_"+scenario+"_FAILED")
            populated["native_"+scenario]=json.loads(z.read_text())
            populated["financialCensus_"+scenario]=census
            populated["unfundedQuoteSideDescriptive_"+scenario]=dict(
                completeCounterfactualSideLabels=len(originalCounterfactuals),
                longSumNetEur=sum(q["knownModelUnfundedCounterfactual"]["netEur"]
                    for q in originalCounterfactuals if q["scenario"]==scenario and q["side"]==1),
                shortSumNetEur=sum(q["knownModelUnfundedCounterfactual"]["netEur"]
                    for q in originalCounterfactuals if q["scenario"]==scenario and q["side"]==-1),
                disclaimer="NOT_SIMULTANEOUS_FINANCED_BOOK_OR_BROKER_FILLS")
            Path("mrf1-original-native-"+scenario+".json").write_text(z.read_text())
    Path("mrf1-original-public.json").write_text(json.dumps(populated,
        sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("MRF1_AUTHENTIC_NEW_MULTIRES_PRICE_COMPLETE",json.dumps(dict(
        originalM1={k:v["M1"] for k,v in sourceTfCounts.items()},
        known=len(rows),paired=report["paired"])),flush=True)
    for scenario in SCENARIOS:
        for name in ("FULL","BASE","CASH"):
            x=populated["native_"+scenario][name]
            print("MRF1_NATIVE_EUR300",scenario,name,
                  "NET",x["Scorecard"]["NetEur"],
                  "TRIPS",x["Scorecard"]["CompletedRoundTrips"],
                  "HARD21",x["Scorecard"]["Hard21AllEligibleWeeks"],flush=True)

if __name__=="__main__":main()

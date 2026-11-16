"""EWL1 original-custody, endpoint-by-endpoint conditional outcome distributions.

No closed strategy replay. Each forecast at original completed-H1 endpoint T sees
only features <= T and analog labels matured at least one full hour before T.
HXC1 ciphertext is decrypted and independently verified only in protected
GitHub custody. Published JSON contains aggregate support/economic proxies only.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import hashlib
import heapq
import json
import math
import os
from pathlib import Path
from statistics import mean, median, stdev

from .custody import unseal_new
from .decode import need
from .hxc1_historical_readback import validate as hxc1_validate

PROTOCOL=Path("research/ewl1_endpoint_protocol.json")
SOURCE=Path("ewl1-source")
OUTPUT=Path("ewl1-original-endpoint-learning-public.json")
CONTRACTS=Path("docs/CMA1_AUTHENTIC_CONTRACT_TERMS_20261108.json")
HOUR=3600000
DAY=24*HOUR
WEEK=7*DAY
SCALE=100000.0


def timestamp(value):
    need(isinstance(value,str) and value.endswith("Z"),"EWL1_UTC_TIME")
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp()*1000)


def frozen():
    raw=PROTOCOL.read_bytes()
    p=json.loads(raw)
    need(p["schema"]=="MXM_EWL1_CAUSAL_ENDPOINT_DISTRIBUTION_LEARNING_FROZEN_V1"
         and p["status"]=="PRE_ORIGINAL_SCORE_FROZEN"
         and p["universe"]==["EURUSD","GBPUSD","AUDUSD","USDJPY","USDCAD",
                             "XAUUSD","US500","NAS100","GER40","UK100","AUS200","JPN225"]
         and p["economicalSymbols"]==["EURUSD","GBPUSD","AUDUSD","USDJPY"]
         and p["endpoint"]["labelHorizonHours"]==4
         and p["model"]["rollingDays"]==91
         and p["model"]["maxAnalogs"]==64
         and p["model"]["minSamples"]==64,
         "EWL1_PRE_REGISTERED_SCOPE")
    c=p["timeline"]
    bounds=[timestamp(c[k]) for k in ("startUtc","trainEndUtc",
                                      "selectionEndUtc","exposedEndUtc")]
    need([bounds[i+1]-bounds[i] for i in range(3)]==
         [26*WEEK,13*WEEK,13*WEEK], "EWL1_CHRONOLOGY")
    return p,hashlib.sha256(raw).hexdigest(),bounds


def authenticated_source(p):
    source=p["source"]
    run=str(source["workflowRunId"])
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"EWL1_PRIVATE_CUSTODY_MISSING")
    envelope=(SOURCE/"source.envelope.json").read_bytes()
    receipt=json.loads((SOURCE/"receipt.public.json").read_text())
    need(receipt.get("sourceRunId")==run
         and receipt.get("protocolSha256")==source["originalProtocolSha256"]
         and hashlib.sha256(envelope).hexdigest()==receipt.get("ciphertextSha256"),
         "EWL1_SOURCE_HASH_OR_RUN")
    tape=json.loads(unseal_new(envelope,private,run))
    verified=hxc1_validate(tape,receipt,run)
    need(tape["schema"]==source["sourceSchema"]
         and verified["rawRequestsRebuilt"]==1444
         and verified["status"]=="HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT",
         "EWL1_BROKER_ORIGINAL_READBACK")
    return tape,receipt,verified


def fee_terms(p):
    fees=json.loads(CONTRACTS.read_text())
    t=fees["sharedCurrentContract"]
    need(fees["originalPepperstoneEurAccountVerified"]
         and fees["originalSourceReadbackVerified"]
         and fees["termsDate"]=="2026-11-04"
         and t["minUnits"]==1000 and t["lotSizeUnits"]==100000
         and float(t["commissionPerLotPerSideUsdFromNativeCurrentModel"])==3.0
         and p["economics"]["commissionUsdPer1000RoundTrip"]==0.06,
         "EWL1_CURRENT_TARIFF_EVIDENCE")
    for s in p["economicalSymbols"]:
        need(s in fees["instruments"] and
             fees["instruments"][s]["minimumUnits"]==1000,
             "EWL1_ORIGINAL_FX_CONTRACT")
    return 0.06


def original_h1(tape,p):
    result={}
    for symbol in p["universe"]:
        rows=tape["bars"].get(symbol+"/H1")
        need(rows is not None and len(rows)>500,"EWL1_SOURCE_MISSING_SYMBOL")
        values=sorted(rows,key=lambda x:x[1])
        need(all(len(r)==7 and r[1]-r[0]==HOUR
                 and r[4]>0 and r[4]<=min(r[2],r[5])
                 and max(r[2],r[5])<=r[3] and r[6]>=0
                 and (i==0 or r[1]>values[i-1][1])
                 for i,r in enumerate(values)),
             "EWL1_ORIGINAL_H1_GEOMETRY")
        result[symbol]=values
    return result


def clip(x):
    return max(-5.0,min(5.0,x))


def feature(rows,i):
    """Completed-H1 state only; observed gaps are never turned into H1 bars."""
    if i<40:return None
    w=rows[i-40:i+1]
    # Four immediately preceding H1 returns must be contiguous, even for an
    # instrument that has session gaps elsewhere in the 41-observation window.
    if any(w[j][0]!=w[j-1][1] for j in range(37,41)):
        return None
    pairs=[math.log(w[j][5]/w[j-1][5])
           for j in range(1,41) if w[j][0]==w[j-1][1]]
    if len(pairs)<24 or len(pairs)<8:return None
    sig=math.sqrt(mean(x*x for x in pairs[-24:]))
    short=math.sqrt(mean(x*x for x in pairs[-8:]))
    if sig<=1e-10:return None
    c=w[-1][5]
    impulse=math.log(c/w[-5][5])/(2*sig)
    elapsed=(w[-1][1]-w[-13][1])/HOUR
    if elapsed<12:return None
    trend=math.log(c/w[-13][5])/(sig*math.sqrt(elapsed))
    volratio=math.log(max(short,1e-10)/sig)
    hi=max(x[3] for x in w[-8:])
    lo=min(x[4] for x in w[-8:])
    channel=(2*(c-lo)/(hi-lo)-1) if hi>lo else 0
    base=(clip(impulse),clip(trend),clip(volratio),clip(channel))
    return {"base":base,"sigma":sig,"clock":w[-1][1],
            "currentCloseRaw":c}


def mature_outcome(records,i):
    """Outcome is calculated independently but never exposed until expiry."""
    r=records[i]
    t=r["t"]
    idx=r["_index"]
    bars=r["_bars"]
    nxt=bars[idx+1:idx+5]
    if len(nxt)!=4 or any(x[0]!=t+j*HOUR for j,x in enumerate(nxt)):
        return None
    opening=nxt[0][2]
    closing=nxt[-1][5]
    if opening<=0 or closing<=0:return None
    normalized=math.log(closing/opening)/(r["sigma"]*2)
    low=min(x[4] for x in nxt)
    high=max(x[3] for x in nxt)
    # These are label-side-specific H1-price excursions, not executable
    # quotes, not evidence for actual stop fills or continuous portfolio DD.
    long_mae=max(0,math.log(opening/low))/(r["sigma"]*2)
    short_mae=max(0,math.log(high/opening))/(r["sigma"]*2)
    return (normalized,opening,closing,long_mae,short_mae)


def prepare(tape,p):
    bars=original_h1(tape,p)
    records={}
    anchored={}
    for symbol in p["universe"]:
        out=[]
        for i,row in enumerate(bars[symbol]):
            f=feature(bars[symbol],i)
            if f is None:
                continue
            event={"symbol":symbol,"t":row[1],"_index":i,"_bars":bars[symbol],
                   "base":f["base"],"sigma":f["sigma"],
                   "currentCloseRaw":f["currentCloseRaw"]}
            out.append(event)
            anchored[(symbol,row[1])]=event
        records[symbol]=out
    # Peer impulse is assembled from other markets' H1 observations ending
    # at EXACT SAME UTC T, never from the latest "nearby" future bar.
    fxanchor=("EURUSD","GBPUSD","AUDUSD")
    for symbol in p["universe"]:
        for r in records[symbol]:
            peers=[anchored[(peer,r["t"])]["base"][0]
                   for peer in fxanchor if peer!=symbol
                   and (peer,r["t"]) in anchored]
            missing=0 if len(peers)>=2 else 1
            pressure=clip(median(peers)) if not missing else 0.0
            r["feature"]=r["base"]+(pressure,float(missing))
            r["peerMissing"]=bool(missing)
            r["_outcome"]=mature_outcome(records[symbol],r["_index"]) if False else None
    # For each original completed H1 decision record, future label is
    # assembled from the same symbol source. It is NOT made available to
    # the learner until (decision + horizon + one-hour embargo) <= T.
    for symbol in p["universe"]:
        for r in records[symbol]:
            i=r["_index"]
            bs=r["_bars"]
            future=bs[i+1:i+5]
            if len(future)!=4 or any(x[0]!=r["t"]+j*HOUR
                                    for j,x in enumerate(future)):
                r["_outcome"]=None
                continue
            entry=future[0][2]
            close=future[-1][5]
            if entry<=0 or close<=0:
                r["_outcome"]=None
                continue
            y=math.log(close/entry)/(r["sigma"]*2)
            low=min(x[4] for x in future)
            high=max(x[3] for x in future)
            mae_l=max(0,math.log(entry/low))/(r["sigma"]*2)
            mae_s=max(0,math.log(high/entry))/(r["sigma"]*2)
            r["_outcome"]=(y,entry,close,mae_l,mae_s)
    return records,anchored,bars


def feature_distance(a,b,with_peer):
    weights=(1,0.75,0.75,0.5,0.5,1) if with_peer else (1,0.75,0.75,0.5)
    return sum(weights[j]*(a[j]-b[j])**2 for j in range(len(weights)))


def quantile(values,weights,prob):
    ordered=sorted(zip(values,weights),key=lambda x:x[0])
    threshold=sum(weights)*prob
    total=0.0
    for x,w in ordered:
        total+=w
        if total>=threshold:return x
    return ordered[-1][0]


def analog_prediction(pool,f,unconditional,with_peer,t):
    chosen=heapq.nsmallest(
        64,pool,key=lambda past:feature_distance(f,past["feature"],with_peer))
    weighted=[]
    for obs in chosen:
        d=feature_distance(f,obs["feature"],with_peer)
        days=max(0,(t-obs["t"])/DAY)
        weight=math.exp(-math.log(2)*days/28)/(1+d)
        weighted.append(weight)
    scale=64/sum(weighted)
    w=[x*scale for x in weighted]
    y=[x["_outcome"][0] for x in chosen]
    avg=sum(a*b for a,b in zip(w,y))/sum(w)
    # Fixed empirical-Bayes prior is only the past-available 13-week mean.
    pred=(64*avg+32*unconditional)/(64+32)
    var=max(1e-10,sum(a*(b-avg)**2 for a,b in zip(w,y))/sum(w))
    eff=sum(w)**2/sum(x*x for x in w)
    se=(64/(64+32))*math.sqrt(var/max(1,eff))
    up=(1+sum(a*(b>0) for a,b in zip(w,y)))/(2+sum(w))
    return {"mean":pred,"se":se,"up":up,
            "q10":quantile(y,w,0.1),"q90":quantile(y,w,0.9),
            "riskLongQ90":quantile([x["_outcome"][3] for x in chosen],w,0.9),
            "riskShortQ90":quantile([x["_outcome"][4] for x in chosen],w,0.9),
            "effectiveSupport":eff}


def phase_at(t,finish,b):
    for name,left,right in (("TRAIN",b[0],b[1]),
                            ("SELECTION",b[1],b[2]),
                            ("EXPOSED",b[2],b[3])):
        if left<=t<right:
            if finish>=right:return "LABEL_CROSSES_PHASE"
            return name
    return None


def economic_pair(symbol,side,entry,close,eurusd_exit,usd_jpy_exit,commission):
    # This is a H1 source-price proxy, with 2026-11-04 current broker
    # commission sensitivity applied EX POST, NOT available as of old T.
    eu=eurusd_exit/SCALE
    need(eu>0,"EWL1_BAD_EURUSD_CONVERSION")
    gain_usd=side*1000*(close-entry)/SCALE
    if symbol=="USDJPY":
        need(usd_jpy_exit>0,"EWL1_BAD_JPY_CONVERSION")
        gain_usd/=usd_jpy_exit/SCALE
    gross=gain_usd/eu
    net=(gain_usd-(commission if side else 0))/eu
    need(math.isfinite(gross) and math.isfinite(net),
         "EWL1_NONFINITE_EURO_PROXY")
    return gross,net


def hypothetical_admission(symbol,r,pred,anchored,commission):
    if pred["mean"]==0:
        return False,0,None
    side=1 if pred["mean"]>0 else -1
    prob=pred["up"] if side==1 else 1-pred["up"]
    if prob<0.60:return False,side,None
    eur=anchored.get(("EURUSD",r["t"]))
    jpy=anchored.get(("USDJPY",r["t"]))
    if eur is None or (symbol=="USDJPY" and jpy is None):
        return False,side,None
    eu=eur["currentCloseRaw"]/SCALE
    fx=(jpy["currentCloseRaw"]/SCALE) if symbol=="USDJPY" else 1.0
    current=r["currentCloseRaw"]/SCALE
    # Predict EUR net from AS-OF current completed close, not next opening.
    estimated_move=current*math.expm1(pred["mean"]*r["sigma"]*2)
    estimated_abs=abs(1000*estimated_move/fx/eu)
    uncertainty=1000*current*pred["se"]*r["sigma"]*2/fx/eu
    commission_eur=commission/eu
    adverse=pred["riskLongQ90"] if side==1 else pred["riskShortQ90"]
    estimated_adverse=1000*current*math.expm1(adverse*r["sigma"]*2)/fx/eu
    valid=estimated_abs-2*uncertainty>commission_eur and estimated_adverse<=3
    return valid,side,{"projectedGrossEur":estimated_abs,
                        "projectedSeEur":uncertainty,
                        "costFloorEur":commission_eur,
                        "projectedAdverse90Eur":estimated_adverse}


def week_summary(items,bounds,phase,metric,benchmark=None):
    start={"TRAIN":0,"SELECTION":26,"EXPOSED":39}[phase]
    span={"TRAIN":26,"SELECTION":13,"EXPOSED":13}[phase]
    sums=[[] for _ in range(span)]
    for x in items:
        k=x["week"]-start
        need(0<=k<span,"EWL1_WEEK_PHASE")
        sums[k].append(x[metric]-(x[benchmark] if benchmark else 0))
    per=[mean(x) if x else 0.0 for x in sums]
    avg=mean(per)
    tcrit=2.5 if span==13 else 2.060
    lower=avg-tcrit*stdev(per)/math.sqrt(span)
    return {"meanWeeklyDifference":round(avg,7),
            "lowerPairedWeekly95":round(lower,7),
            "weeksWithScoredEndpoints":sum(bool(x) for x in sums),
            "phaseWeeks":span}


def summarize(items):
    if not items:return {"n":0,"mseFull":None,"mseOwn":None,
                         "mseUnconditional":None,"mseMomentum":None,
                         "mseZero":None,"brierFull":None,
                         "brierUnconditional":None,"conditionalIntervalCoverage":None}
    return {"n":len(items),
            "mseFull":round(mean(x["seFull"] for x in items),7),
            "mseOwn":round(mean(x["seOwn"] for x in items),7),
            "mseUnconditional":round(mean(x["seBase"] for x in items),7),
            "mseMomentum":round(mean(x["seMomentum"] for x in items),7),
            "mseZero":round(mean(x["seZero"] for x in items),7),
            "brierFull":round(mean(x["brierFull"] for x in items),7),
            "brierUnconditional":round(mean(x["brierBase"] for x in items),7),
            "conditionalIntervalCoverage":round(mean(x["inside"] for x in items),6),
            "meanEffectiveNeighborSupport":round(mean(x["effectiveSupport"] for x in items),3)}


def evaluate(tape,p,bounds,commission):
    records,anchored,sourcebars=prepare(tape,p)
    support={phase:Counter() for phase in ("TRAIN","SELECTION","EXPOSED")}
    quality={phase:[] for phase in support}
    by_market=defaultdict(list)
    shadow=defaultdict(list)
    for symbol in p["universe"]:
        chain=records[symbol]
        pool=deque()
        ptr=0
        for idx,r in enumerate(chain):
            t=r["t"]
            phase=phase_at(t,t+4*HOUR,bounds)
            if phase is None:continue
            if phase=="LABEL_CROSSES_PHASE":
                continue
            counters=support[phase]
            counters["featureEligibleEndpoint"]+=1
            if r["peerMissing"]:counters["crossMarketPeerUnavailable"]+=1
            # Release formerly UNKNOWN future only when the original
            # label's four H1 bars have finished plus one whole H1 embargo.
            while ptr<idx and chain[ptr]["t"]+5*HOUR<=t:
                previous=chain[ptr]
                if previous["_outcome"] is not None:
                    pool.append(previous)
                ptr+=1
            while pool and pool[0]["t"]<t-91*DAY:
                pool.popleft()
            if t<bounds[0]+13*WEEK or len(pool)<64:
                counters["warmupOrInsufficientMatureLabels"]+=1
                continue
            counters["causalForecastIssued"]+=1
            nums=[x["_outcome"][0] for x in pool]
            uncond=mean(nums)
            base_p=(1+sum(y>0 for y in nums))/(2+len(nums))
            # Exactly the same eligible clock and matured analog history for
            # FULL versus own-only; no outcomes determine endpoint admission.
            full=analog_prediction(pool,r["feature"],uncond,True,t)
            own=analog_prediction(pool,r["feature"],uncond,False,t)
            if symbol in p["economicalSymbols"]:
                hypothetical,side,financial=hypothetical_admission(
                    symbol,r,full,anchored,commission)
                if hypothetical:
                    counters["modelShadowPreDecisionIntents"]+=1
            else:
                hypothetical=False
                side=0
            outcome=r["_outcome"]
            if outcome is None:
                counters["forward4hOutcomeUnknown"]+=1
                if hypothetical:counters["shadowForwardOutcomeUnknown"]+=1
                continue
            y,opening,closing,maeL,maeS=outcome
            counters["maturedEndpointOutcomesScored"]+=1
            mforecast=.25*r["base"][0]
            sign=1 if y>0 else 0
            sq=lambda mu:(y-mu)*(y-mu)
            row={"week":int((t-bounds[0])//WEEK),
                 "seFull":sq(full["mean"]),
                 "seOwn":sq(own["mean"]),
                 "seBase":sq(uncond),"seMomentum":sq(mforecast),
                 "seZero":sq(0),
                 "brierFull":(full["up"]-sign)**2,
                 "brierBase":(base_p-sign)**2,
                 "inside":int(full["q10"]<=y<=full["q90"]),
                 "effectiveSupport":full["effectiveSupport"]}
            quality[phase].append(row)
            by_market[(phase,symbol)].append(row)
            if hypothetical:
                e=anchored.get(("EURUSD",t+4*HOUR))
                j=anchored.get(("USDJPY",t+4*HOUR))
                if e is None or (symbol=="USDJPY" and j is None):
                    counters["shadowEconomicConversionMissing"]+=1
                    continue
                eg,net=economic_pair(symbol,side,opening,closing,
                                  e["currentCloseRaw"],
                                  j["currentCloseRaw"] if j else 1,
                                  commission)
                momentum=1 if r["base"][0]>0 else -1 if r["base"][0]<0 else 0
                mg,mc=economic_pair(symbol,momentum,opening,closing,
                                    e["currentCloseRaw"],
                                    j["currentCloseRaw"] if j else 1,
                                    commission)
                _,longcost=economic_pair(symbol,1,opening,closing,
                                        e["currentCloseRaw"],
                                        j["currentCloseRaw"] if j else 1,
                                        commission)
                shadow[phase].append({"week":row["week"],"symbol":symbol,
                                      "grossEur":eg,"commissionOnlyEur":net,
                                      "momentumCommissionEur":mc,
                                      "longCommissionEur":longcost,
                                      "side":side,"adverseH1Bps":(
                                          maeL if side==1 else maeS)*r["sigma"]*2*10000})
    phases={}
    selected_ready=False
    for name,first,n in (("TRAIN",0,26),("SELECTION",26,13),("EXPOSED",39,13)):
        rows=quality[name]
        shadows=shadow[name]
        phase={
            "population":dict(support[name]),
            "forecastQualityAll12":summarize(rows),
            "bySymbol":{s:summarize(by_market[(name,s)]) for s in p["universe"]},
            "pairedWeeklyFullMSEvsUnconditional":
                week_summary(rows,bounds,name,"seBase","seFull"),
            "pairedWeeklyFullMSEvsOwnOnly":
                week_summary(rows,bounds,name,"seOwn","seFull"),
            "pairedWeeklyFullMSEvsMomentum":
                week_summary(rows,bounds,name,"seMomentum","seFull"),
            "fourFxShadowNotFundedRoundTrips":{
                "predecisionIntents":sum(1 for x in shadows),
                "knownOutcomeCount":len(shadows),
                "grossEurPriceOnly":round(sum(x["grossEur"] for x in shadows),6),
                "commissionOnlyEurCurrentTariff":round(sum(x["commissionOnlyEur"] for x in shadows),6),
                "matchedMomentumCommissionOnlyEur":round(sum(x["momentumCommissionEur"] for x in shadows),6),
                "matchedAlwaysLongCommissionOnlyEur":round(sum(x["longCommissionEur"] for x in shadows),6),
                "meanObservedH1AdverseBps":round(mean(x["adverseH1Bps"] for x in shadows),6)
                          if shadows else None,
                "weeksWithAtLeast21ShadowIntents":sum(
                    sum(x["week"]==k for x in shadows)>=21
                    for k in range(first,first+n))
            }
        }
        phases[name]=phase
    sel=phases["SELECTION"]
    q=sel["forecastQualityAll12"]
    # Fixed multi-comparator conditional quality admission, no training or
    # parameter adjustment from selection or exposed score outcomes.
    predictive=(q["n"]>0 and
                sel["pairedWeeklyFullMSEvsUnconditional"]["lowerPairedWeekly95"]>0
                and sel["pairedWeeklyFullMSEvsOwnOnly"]["lowerPairedWeekly95"]>0
                and sel["pairedWeeklyFullMSEvsMomentum"]["lowerPairedWeekly95"]>0)
    return phases,predictive,{s:len(sourcebars[s]) for s in p["universe"]}


def run():
    p,protocol_sha,bounds=frozen()
    source,receipt,verified=authenticated_source(p)
    commission=fee_terms(p)
    phases,predictive,sourcecounts=evaluate(source,p,bounds,commission)
    result={
        "schema":"MXM_EWL1_AUTHENTIC_ENDPOINT_PREQUENTIAL_DISTRIBUTION_V1",
        "protocolSha256":protocol_sha,
        "originalHxc1RunId":int(receipt["sourceRunId"]),
        "originalHxc1ProtocolSha256":receipt["protocolSha256"],
        "originalBrokerProtobufRequestsIndependentlyVerified":verified["rawRequestsRebuilt"],
        "originalH1SourceBars":sourcecounts,
        "sourceEvidenceClass":"AUTHENTIC_PEPPERSTONE_COMPLETED_H1_PRICE_ONLY_NOT_EXECUTION",
        "endpointDecision":"historical completed H1 T; pre-T features; pool only label matured T-1h or earlier",
        "featureWarmup":"41 observed completed H1 candles, >=24 true adjacent within-session H1 returns, own 4H valid",
        "modelWarmup":"13 calendar weeks and >=64 matured same-symbol analog labels, rolling 91d, half-life28d",
        "labelWarmup":"next4 contiguous H1 outcomes with 1 completed H1 embargo; no forward availability conditioning",
        "chronologicalPhases":phases,
        "selectionIncrementalPredictiveGate":predictive,
        "allResultsGloballyExposedNotIndependent":True,
        "economicLimitations":{
           "currentCommissionOriginalBrokerUsdFor1000":commission,
           "currentTariffSourceDate":"2026-11-04",
           "currentTariffWouldBeFutureInformationAtOlderEndpoints":True,
           "fourFxFinancialOutcomeIsHistoricalPriceProxyCurrentCommissionSensitivityOnly":True,
           "fullHistoricalBrokerExecutionNetEur":None,
           "sharedNativeCsharp300EurFundedNet":None,
           "floatingDrawdown30Certified":False,"hard21SystemicCertified":False,
           "independentConfirmation":False,
           "historicalBidAskFullSpread":False,
           "historicalSwapSlippageFXExecution":False
        },
        "noClosedStudyRerun":True,
        "ordersSubmitted":0,"cloudActivation":False,
        "verdict":"PREDICTIVE_ONLY_IF_FIXED_GATE_PASSED_NO_FULL_NET_OR_INDEPENDENCE"
    }
    OUTPUT.write_text(json.dumps(result,sort_keys=True,indent=2,
                                 allow_nan=False)+"\n")
    print("EWL1_AUTHENTIC_ENDPOINT_WALKFORWARD_EVALUATED_NO_FULL_NET_CLAIM",flush=True)


if __name__=="__main__":
    try:
        run()
    except Exception:
        print("EWL1_AUTHENTIC_ENDPOINT_EVALUATION_FAILED_DETAIL_WITHHELD",flush=True)
        raise SystemExit(1)

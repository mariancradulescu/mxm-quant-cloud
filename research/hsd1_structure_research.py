"""HSD1: frozen systematic, causal, multimechanism historical OHLCV research.

Research exclusively on separately verified original HXC1 sealed broker history.
Twelve symbols, six market-structure mechanisms, four native closed-bar
regimes and two original H1 horizons. Four original-contract-priced FX markets
admit EUR commission-only proxy; others retain honest directional proxy only.

Original HXC1 sealed source is never published. No orders, no RDE1, no replay
of SPDE1, MVE1 or HXP1 and no strategy tuning after source scoring.
"""
from __future__ import annotations
import collections
import hashlib
import json
import math
import os
from pathlib import Path
from datetime import datetime
from statistics import mean, median, stdev

from .custody import unseal_new
from .hxc1_historical_readback import validate as validate_hxc1
from .decode import need

SOURCE = Path("hsd1-original-source")
PROTOCOL = Path("research/hsd1_structure_protocol.json")
OUTPUT = Path("hsd1-public-predictive-economic-proxy.json")
CMA1 = Path("docs/CMA1_AUTHENTIC_CONTRACT_TERMS_20261108.json")
HOUR = 3_600_000
WEEK = 168 * HOUR
SCALE = 100000.0


def ms(utc):
    need(utc.endswith("Z"), "HSD1_BOUND_NOT_UTC")
    return int(datetime.fromisoformat(utc.replace("Z","+00:00")).timestamp()*1000)


def frozen_plan():
    data=PROTOCOL.read_bytes()
    p=json.loads(data)
    need(p["schema"]=="MXM_HSD1_FROZEN_SYSTEMATIC_HISTORICAL_STRUCTURE_SELECTION_V1"
         and p["status"]=="PRE_SCORE_FROZEN_UNSCORED"
         and len(p["universe"])==12
         and p["financeEligible"]==["EURUSD","GBPUSD","AUDUSD","USDJPY"]
         and len(p["mechanisms"])==6 and p["horizonsH"]==[1,4]
         and p["selection"]["comparisonCount"]==48,
         "HSD1_FROZEN_POLICY_MISMATCH")
    chrono=p["chronologicalSplit"]
    bounds=[ms(chrono[k]) for k in ("startUtc","trainEndUtc",
                                    "selectionEndUtc","exposedEndUtc")]
    need([bounds[i+1]-bounds[i] for i in range(3)]==
         [26*WEEK,13*WEEK,13*WEEK], "HSD1_PHASE_GEOMETRY")
    return p,hashlib.sha256(data).hexdigest(),bounds


def authentic_history(p):
    source=p["originalHxc1"]
    run=str(source["runId"])
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"HSD1_PROTECTED_KEY_MISSING")
    raw=(SOURCE/"source.envelope.json").read_bytes()
    receipt=json.loads((SOURCE/"receipt.public.json").read_text())
    need(receipt["sourceRunId"]==run and
         receipt["protocolSha256"]==source["sourceProtocolSha256"] and
         hashlib.sha256(raw).hexdigest()==receipt["ciphertextSha256"],
         "HSD1_SOURCE_FROZEN_IDENTITY")
    bundle=json.loads(unseal_new(raw,private,run))
    verified=validate_hxc1(bundle,receipt,run)
    need(bundle["schema"]==source["sourceSchema"] and
         verified["rawRequestsRebuilt"]==1444,
         "HSD1_ORIGINAL_SOURCE_VALIDATION_FAILED")
    return bundle,receipt,verified


def cost_terms(p):
    contract=json.loads(CMA1.read_text())
    t=contract["sharedCurrentContract"]
    need(contract["originalSourceReadbackVerified"] and
         contract["originalPepperstoneEurAccountVerified"] and
         contract["termsDate"]==p["finance"]["commissionTermsAsOf"] and
         t["minUnits"]==1000 and t["lotSizeUnits"]==100000 and
         float(t["commissionPerLotPerSideUsdFromNativeCurrentModel"])==3.0,
         "HSD1_FINANCIAL_TERMS_UNVERIFIED")
    for symbol in p["financeEligible"]:
        need(symbol in contract["instruments"] and
             contract["instruments"][symbol]["minimumUnits"]==1000,
             "HSD1_CONTRACT_NOT_FINANCE_ELIGIBLE")
    return 0.06


def source_rows(bundle,p):
    result={}
    for symbol in p["universe"]:
        data=bundle["bars"].get(symbol+"/H1")
        need(isinstance(data,list) and len(data)>500,
             "HSD1_MISSING_ORIGINAL_H1")
        arr=sorted(data,key=lambda x:x[1])
        need(all(len(r)==7 and r[1]-r[0]==HOUR and r[4]>0
                 and r[4]<=min(r[2],r[5])<=max(r[2],r[5])<=r[3]
                 and r[6]>=0 and (i==0 or r[1]>arr[i-1][1])
                 for i,r in enumerate(arr)),
             "HSD1_SOURCE_BAR_GEOMETRY")
        result[symbol]=arr
    return result


def causal_events(bars,at,p):
    """Uses current finished H1 and previous 48 OBSERVED bars; no next bar."""
    if at<48:return [],None
    hist=bars[at-48:at+1]
    r=hist[-1]
    prev=hist[:-1]
    ranges=[v[3]-v[4] for v in hist]
    closes=[v[5] for v in hist]
    valid=[math.log(closes[i]/closes[i-1])
           for i in range(1,len(hist))
           if hist[i][0]==hist[i-1][1]]
    if len(valid)<24:
        return [],None
    sigma=math.sqrt(mean(x*x for x in valid[-24:]))
    if sigma<=1e-10:return [],None
    current_range=max(1,ranges[-1])
    body=r[5]-r[2]
    prev24hi=max(x[3] for x in prev[-24:])
    prev24lo=min(x[4] for x in prev[-24:])
    prev8hi=max(x[3] for x in prev[-8:])
    prev8lo=min(x[4] for x in prev[-8:])
    volHigh=mean(ranges[-8:])>1.3*mean(ranges[-32:])
    past12=math.log(closes[-1]/closes[-13])
    trendHigh=abs(past12)>1.25*math.sqrt(12)*sigma
    regime=int(volHigh)*2+int(trendHigh)
    events=[]
    def add(name,side):
        if side in (-1,1):
            events.append((name,side,regime))
    # 1. Breakout with decisive candle body.
    if abs(body)>=.35*current_range:
        if r[5]>prev24hi and body>0:add("CHANNEL_BREAKOUT_BODY",1)
        elif r[5]<prev24lo and body<0:add("CHANNEL_BREAKOUT_BODY",-1)
    # 2. Rejected previous price extreme, measured after fully closed wick.
    upper=r[3]-max(r[2],r[5])
    lower=min(r[2],r[5])-r[4]
    if r[3]>prev24hi and r[5]<prev24hi and upper>=.5*current_range:
        add("FAILED_EXTREME_WICK",-1)
    elif r[4]<prev24lo and r[5]>prev24lo and lower>=.5*current_range:
        add("FAILED_EXTREME_WICK",1)
    # 3. In a past 12-bar trend, countertrend candle still above/below past median.
    if abs(past12)>math.sqrt(12)*sigma:
        median_close=median(closes[-25:-1])
        if past12>0 and body<0 and r[5]>median_close:
            add("TREND_DIP_REJOIN",1)
        elif past12<0 and body>0 and r[5]<median_close:
            add("TREND_DIP_REJOIN",-1)
    # 4. Huge late candle with stretched body: mean-reversion forecast.
    if current_range>2*median(ranges[-25:-1]) and abs(body)>.55*current_range:
        add("VOLUMELESS_VOL_SHOCK_REVERSAL",-1 if body>0 else 1)
    # 5. Low-range consolidation breaks in a decisive direction.
    if mean(ranges[-9:-1])<.7*mean(ranges[-33:-1]) and abs(body)>.35*current_range:
        if r[5]>prev8hi and body>0:add("COMPRESSION_ESCAPE",1)
        elif r[5]<prev8lo and body<0:add("COMPRESSION_ESCAPE",-1)
    # 6. Three consecutively oriented completed closed bars with size.
    if (closes[-1]>closes[-2]>closes[-3]>closes[-4] and
        math.log(closes[-1]/closes[-4])>1.5*math.sqrt(3)*sigma):
        add("THREE_BAR_IMPULSE",1)
    elif (closes[-1]<closes[-2]<closes[-3]<closes[-4] and
          math.log(closes[-4]/closes[-1])>1.5*math.sqrt(3)*sigma):
        add("THREE_BAR_IMPULSE",-1)
    momentum=1 if closes[-1]>closes[-5] else (-1 if closes[-1]<closes[-5] else 0)
    return events,momentum


def price_route_eur(symbol,side,entry,exit,conversion,units,commission_usd):
    """Conservatively labeled optimistic current-commission EUR price proxy.

    This is NOT broker executable NET; entry/exit are H1 open/close, conversion
    is original EURUSD H1 close, not an executable FX route or spread.
    """
    eurusd=conversion["EURUSD"]/SCALE
    need(eurusd>0 and entry>0 and exit>0,"HSD1_EUR_CONVERSION_INVALID")
    quote_delta=side*units*(exit-entry)/SCALE
    if symbol=="USDJPY":
        usd=quote_delta/(exit/SCALE)
    else:
        usd=quote_delta
    gross=usd/eurusd
    cost=commission_usd/eurusd if side!=0 else 0
    need(math.isfinite(gross) and math.isfinite(cost),"HSD1_FINITE_ECONOMY")
    return gross,gross-cost


def split_decision(t,exit_at,bounds):
    (start,train,selection,exposed)=bounds
    for name,lo,hi,w in (("TRAIN",start,train,0),
                         ("SELECTION",train,selection,26),
                         ("EXPOSED",selection,exposed,39)):
        if lo<=t<hi:
            return (name,(t-start)//WEEK) if exit_at<hi else ("CROSS_PHASE",None)
    return (None,None)


def collect_events(series,p,bounds,commission):
    indices={symbol:{r[1]:r for r in rows} for symbol,rows in series.items()}
    candidates=[]
    counts=collections.Counter()
    for symbol,rows in series.items():
        eligible=symbol in p["financeEligible"]
        for idx in range(48,len(rows)):
            t=rows[idx][1]
            events,momentum=causal_events(rows,idx,p)
            if momentum is None:
                counts["missingCausalFeatures"]+=1
                continue
            counts["completedCausalClocks"]+=1
            if not events:
                counts["abstainedNoStructuralEvent"]+=1
                continue
            for name,side,regime in events:
                for h in p["horizonsH"]:
                    phase,week=split_decision(t,t+h*HOUR,bounds)
                    if phase is None:continue
                    if phase=="CROSS_PHASE":
                        counts["maturedPastPhaseBoundary"]+=1
                        continue
                    counts["preOutcomeStructuralEvents"]+=1
                    # Labels never feed back into ex-ante event generation.
                    future=[indices[symbol].get(t+j*HOUR) for j in range(1,h+1)]
                    if any(v is None or v[0]!=t+(j-1)*HOUR
                           for j,v in enumerate(future,1)):
                        counts["unknownForwardMarketBars"]+=1
                        continue
                    entry=future[0][2]
                    close=future[-1][5]
                    if entry<=0 or close<=0:
                        counts["invalidFutureProxy"]+=1
                        continue
                    price_bps=side*10000*math.log(close/entry)
                    data={"phase":phase,"week":int(week),"symbol":symbol,
                          "family":name,"regime":regime,"h":h,"at":t,
                          "side":side,"momentum":momentum,
                          "bps":price_bps,
                          "correct":int(side*(close-entry)>0),
                          "eurgross":None,"eurcommission":None,
                          "eurmomentum":None,"eurlong":None}
                    if eligible:
                        conv=indices["EURUSD"].get(t+h*HOUR)
                        if conv is None or conv[0]!=t+(h-1)*HOUR:
                            counts["unknownEurConversion"]+=1
                            # Preserve honest direction-only candidate and never
                            # treat it as an economic EUR label.
                        else:
                            conversions={"EURUSD":conv[5]}
                            gross,floor=price_route_eur(symbol,side,entry,close,
                                                          conversions,1000,commission)
                            _,momentum_floor=price_route_eur(
                                symbol,momentum,entry,close,conversions,1000,
                                commission if momentum else 0)
                            _,long_floor=price_route_eur(
                                symbol,1,entry,close,conversions,1000,commission)
                            data.update(eurgross=gross,eurcommission=floor,
                                        eurmomentum=momentum_floor,eurlong=long_floor)
                    candidates.append(data)
    return candidates,counts


def simple_summary(rows,key="bps"):
    values=[r[key] for r in rows if r[key] is not None]
    return {"n":len(values),"sum":round(sum(values),5),
            "mean":round(mean(values),6) if values else None,
            "correctFraction":round(mean(r["correct"] for r in rows),5)
            if rows else None}


def weekly_gate(rows,phase_start,weeks,value="eurcommission",other=None,critical=2.179):
    arr=[0.0]*weeks
    nonzero=set()
    for r in rows:
        idx=r["week"]-phase_start
        need(0<=idx<weeks,"HSD1_PHASE_INDEX_INVALID")
        v=r[value]-(r[other] if other else 0)
        arr[idx]+=v
        nonzero.add(idx)
    avg=mean(arr)
    lower=avg-critical*stdev(arr)/math.sqrt(weeks)
    return {"sumEur":round(sum(arr),6),"meanWeeklyEur":round(avg,6),
            "lowerWeeklyEur":round(lower,6),
            "weeksWithEvents":len(nonzero)}


def candidate_train_gate(rows,p):
    conf=p["selection"]
    if len(rows)<conf["minTrainCandidates"]:return False
    if len({r["week"] for r in rows})<conf["minTrainWeeks"]:return False
    a=[r for r in rows if r["week"]<13]
    b=[r for r in rows if r["week"]>=13]
    if not a or not b:return False
    if sum(r["eurcommission"] for r in a)<=0 or sum(r["eurcommission"] for r in b)<=0:
        return False
    z=conf["uncertaintyZ"]
    f=weekly_gate(rows,0,26,critical=z)
    d=weekly_gate(rows,0,26,other="eurmomentum",critical=z)
    return f["lowerWeeklyEur"]>0 and d["lowerWeeklyEur"]>0


def score_all(candidates,p):
    mechanism_rows=[]
    classed={}
    for family in p["mechanisms"]:
        for regime in range(4):
            for h in p["horizonsH"]:
                key=(family,regime,h)
                rows=[r for r in candidates if r["symbol"] in p["financeEligible"]
                      and (r["family"],r["regime"],r["h"])==key
                      and r["eurcommission"] is not None]
                per={phase:[r for r in rows if r["phase"]==phase]
                     for phase in ("TRAIN","SELECTION","EXPOSED")}
                training=per["TRAIN"]
                gate=candidate_train_gate(training,p)
                classification={
                    "family":family,"regime":regime,"horizonHours":h,
                    "trainQualified":gate,
                    "train":simple_summary(training,"eurcommission"),
                    "selection":simple_summary(per["SELECTION"],"eurcommission"),
                    "exposedDescriptive":simple_summary(per["EXPOSED"],"eurcommission"),
                    "trainMatchedMomentum":weekly_gate(training,0,26,
                        other="eurmomentum",critical=3.30),
                    "selectionMatchedMomentum":weekly_gate(per["SELECTION"],26,13,
                        other="eurmomentum"),
                    "trainCash":weekly_gate(training,0,26,critical=3.30),
                    "selectionCash":weekly_gate(per["SELECTION"],26,13)
                }
                mechanism_rows.append(classification)
                classed[key]=classification
    return mechanism_rows,classed


def qualified_shadow(candidates,trained,p):
    eligible=set(p["financeEligible"])
    grouped=collections.defaultdict(list)
    for r in candidates:
        if r["symbol"] not in eligible or r["eurcommission"] is None:
            continue
        k=(r["family"],r["regime"],r["h"])
        x=trained[k]
        if x["trainQualified"]:
            grouped[(r["phase"],r["symbol"],r["at"],r["h"])].append(r)
    # One ex-ante selected family for each market/time/horizon. No funder,
    # overlap/available-margin or full historical execution-price claim.
    selected=collections.defaultdict(list)
    for (phase,sym,at,h),rows in grouped.items():
        # Training-only ranking. If equal, canonical family lexical order.
        chosen=sorted(rows,key=lambda r:(
            -trained[(r["family"],r["regime"],r["h"])]["trainCash"]["lowerWeeklyEur"],
            r["family"]))[0]
        selected[phase].append(chosen)
    out={}
    for phase,week,count in (("TRAIN",0,26),("SELECTION",26,13),("EXPOSED",39,13)):
        rows=selected[phase]
        out[phase]={
            "signalsNotFundedRoundTrips":len(rows),
            "commissionOnlyEur":round(sum(r["eurcommission"] for r in rows),6),
            "grossPriceEur":round(sum(r["eurgross"] for r in rows),6),
            "matchedMomentumCommissionOnlyEur":round(sum(r["eurmomentum"] for r in rows),6),
            "cash":weekly_gate(rows,week,count),
            "incrementVsMomentum":weekly_gate(rows,week,count,other="eurmomentum"),
            "eligibleSymbols":sorted(set(r["symbol"] for r in rows)),
            "maxWeeklySignalCount":max((sum(r["week"]==w for r in rows)
                                        for w in range(week,week+count)),default=0),
            "weeksWith21OrMoreSignals":sum(sum(r["week"]==w for r in rows)>=21
                                     for w in range(week,week+count)),
        }
    return out


def research():
    p,protocol_sha,bounds=frozen_plan()
    source,receipt,verified=authentic_history(p)
    commission=cost_terms(p)
    series=source_rows(source,p)
    rows,support=collect_events(series,p,bounds,commission)
    all_family=[]
    for fam in p["mechanisms"]:
        for h in p["horizonsH"]:
            per=[]
            for phase in ("TRAIN","SELECTION","EXPOSED"):
                group=[r for r in rows if r["family"]==fam
                       and r["h"]==h and r["phase"]==phase]
                economic=[r for r in group if r["eurcommission"] is not None]
                per.append({
                    "phase":phase,
                    "all12RawPriceBps":simple_summary(group),
                    "fourFxCommissionOnlyEur":simple_summary(economic,"eurcommission"),
                    "grossModelEur":round(sum(r["eurgross"] for r in economic),6),
                    "matchedMomentumCommissionOnlyEur":round(
                       sum(r["eurmomentum"] for r in economic),6),
                    "labelledInstrumentCount":len(set(r["symbol"] for r in group)),
                    "unknownEconomicLabelCount":sum(
                        r["symbol"] in p["financeEligible"] and
                        r["eurcommission"] is None for r in group)
                })
            all_family.append({"family":fam,"horizonHours":h,"phases":per})
    regimes,trained=score_all(rows,p)
    selected=qualified_shadow(rows,trained,p)
    sel=selected["SELECTION"]
    admitted=(sel["signalsNotFundedRoundTrips"]>0 and
              sel["cash"]["lowerWeeklyEur"]>0 and
              sel["incrementVsMomentum"]["lowerWeeklyEur"]>0)
    data={
        "schema":"MXM_HSD1_ORIGINAL_HISTORY_SYSTEMATIC_STRUCTURE_PRICE_PROXY_V1",
        "study":"HSD1",
        "originalHxc1Run":int(receipt["sourceRunId"]),
        "originalHxc1ProtocolSha256":receipt["protocolSha256"],
        "sourceRawProtobufVerified":verified["rawRequestsRebuilt"],
        "studyProtocolSha256":protocol_sha,
        "originalH1BarCounts":{symbol:len(series[symbol]) for symbol in p["universe"]},
        "scope":{"symbols":p["universe"],"economicsAllowed":p["financeEligible"],
                 "families":p["mechanisms"],"regimes":4,"horizons":p["horizonsH"],
                 "globallyExposed":True,"independentConfirmation":False},
        "population":dict(support),
        "allCandidateFamilyHorizonOutcomes":all_family,
        "all48FamilyRegimeHorizonEconomicCells":regimes,
        "trainQualifiedCellCount":sum(x["trainQualified"] for x in regimes),
        "selectionAdmissionShadow":selected,
        "selectionAdmittedByFrozenEconomicProxyGate":admitted,
        "ineligibleForFullNetReason":"Historical execution BID/ASK, slippage, funding and FX executable prices not available in HXC1",
        "economicAccounting":{
            "minimumFxVolumeUnits":1000,"currentTermsDate":"2026-11-04",
            "commissionRoundTripUSD":commission,
            "EUR":"original H1 exit close FX conversion PRICE PROXY",
            "grossAndCommissionOnlyModeled":True,
            "historicalBrokerExecutableNETEUR":None,
            "nativeCsharp300EurFundedNETEUR":None,
            "floatingDrawdownCertified":False,
            "hard21Certified":False,
            "independentConfirmation":False,
            "ordersSubmitted":0,"cloudActivation":False
        },
        "status":"SYSTEMATIC_ORIGINAL_HISTORICAL_PREDICTION_NOT_FULL_BROKER_NET",
        "noRetuneNoClosedStudyRerun":True
    }
    OUTPUT.write_text(json.dumps(data,sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("HSD1_AUTHENTIC_H1_SYSTEMATIC_STRUCTURE_EVALUATION_DONE_FULL_NET_NOT_CLAIMED",flush=True)


if __name__=="__main__":
    try:
        research()
    except Exception:
        print("HSD1_PROTECTED_HISTORICAL_RESEARCH_FAILED_DETAIL_WITHHELD",flush=True)
        raise SystemExit(1)

"""HXP1: prospective-frozen delayed common-dollar-shock price prediction.

Historical research on original HXC1 source ONLY. Never accesses broker,
trading APIs, a live market, RDE1, or re-executes older exact strategies.
Public output aggregates performance only; price tape remains protected.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
from statistics import mean, median, stdev

from .custody import unseal_new
from .decode import need
from .hxc1_historical_readback import validate as verify_original_hxc1

PROTOCOL = Path("research/hxp1_fx_peer_delay_protocol.json")
PRICE_FACTOR = 100000.0
HOUR = 3600000
WEEK = 7 * 24 * HOUR
CMA1 = Path("docs/CMA1_AUTHENTIC_CONTRACT_TERMS_20261108.json")
SOURCE_DIR = Path("hxc1-source")
OUTPUT = Path("hxp1-original-predictive-public.json")


def utc(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def invariant_policy(p):
    need(p.get("schema") == "MXM_HXP1_HISTORICAL_FX_PEER_SHOCK_DELAY_PREDICTIVE_V1"
         and p.get("status") == "PRE_EVALUATION_FROZEN"
         and p["universe"] == ["EURUSD", "GBPUSD", "AUDUSD"], "HXP1_PROTOCOL_SCOPE")
    c=p["chronology"]
    start, train, select, end=(utc(c[k]) for k in
        ("startUtc","trainEndUtc","selectionEndUtc","exposedEndUtc"))
    need(train-start==26*WEEK and select-train==13*WEEK
         and end-select==13*WEEK, "HXP1_PHASE_GEOMETRY")
    need(p["causality"]["entry"].startswith("next original H1 OPEN")
         and p["finance"]["minimumUnits"]==1000
         and p["finance"]["commissionUsdPerLotPerSide"]==3.0,
         "HXP1_ECONOMIC_FROZEN_INVARIANTS")
    return start,train,select,end


def check_source(p):
    source=p["originalAuthenticatedSource"]
    original_run=str(source["workflowRunId"])
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"HXP1_NO_PROTECTED_KEY")
    ciphertext=(SOURCE_DIR/"source.envelope.json").read_bytes()
    receipt=json.loads((SOURCE_DIR/"receipt.public.json").read_text())
    need(hashlib.sha256(ciphertext).hexdigest()==receipt["ciphertextSha256"],
         "HXP1_SOURCE_CIPHERTEXT")
    need(receipt["protocolSha256"]==source["originalProtocolSha256"]
         and receipt["sourceRunId"]==original_run, "HXP1_SOURCE_FROZEN")
    bundle=json.loads(unseal_new(ciphertext,private,original_run))
    verified=verify_original_hxc1(bundle,receipt,original_run)
    need(verified["status"]=="HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT",
         "HXP1_SOURCE_READBACK")
    return bundle,receipt,verified


def fee_context(p):
    source=json.loads(CMA1.read_text())
    f=p["finance"]
    c=source["sharedCurrentContract"]
    need(source["originalPepperstoneEurAccountVerified"] is True
         and source["originalSourceReadbackVerified"] is True
         and source["termsDate"]=="2026-11-04"
         and c["minUnits"]==f["minimumUnits"]
         and c["lotSizeUnits"]==f["lotSize"]
         and float(c["commissionPerLotPerSideUsdFromNativeCurrentModel"])==
             f["commissionUsdPerLotPerSide"],
         "HXP1_CURRENT_FEE_CONTEXT_MISMATCH")
    for s in p["universe"]:
        need(float(source["instruments"][s]["currentMinMarginEur"])==
             f["symbolMinimumMarginEur"][s], "HXP1_SYMBOL_MARGIN_TERMS")
    return (f["minimumUnits"]/f["lotSize"] *
            2*f["commissionUsdPerLotPerSide"])


def phase_at(t, exit_time, bounds):
    start, train, selection, exposed = bounds
    for name,lo,hi,n in (("TRAIN",start,train,26),
                         ("SELECTION",train,selection,13),
                         ("EXPOSED_DESCRIPTIVE",selection,exposed,13)):
        if lo<=t<hi:
            return name if exit_time<hi else "UNKNOWN_MATURITY"
    return None


def prepare_series(bundle,p):
    out={}
    for name in p["universe"]:
        rows=bundle["bars"].get(name+"/H1")
        need(rows and len(rows)>=500,"HXP1_NO_AUTHENTIC_H1")
        seen=set()
        index={}
        for row in rows:
            start,end,op,high,low,close,volume=row
            need(end-start==HOUR and end not in seen and
                 low>0 and low<=min(op,close)<=max(op,close)<=high and volume>=0,
                 "HXP1_CORRUPT_OR_DUPLICATE_BAR")
            index[end]=(start,op,close)
            seen.add(end)
        out[name]=index
    return out


def series_feature(index,t):
    # Entire 24-return window must contain consecutive COMPLETED H1 bars.
    prices=[]
    for h in range(25):
        row=index.get(t-h*HOUR)
        if row is None or row[0]!=t-(h+1)*HOUR:
            return None
        prices.append(row[2])
    prices=list(reversed(prices))
    ret=[math.log(prices[i+1]/prices[i]) for i in range(24)]
    sig=math.sqrt(sum(x*x for x in ret)/24)
    if sig<=1e-9:
        return None
    return (math.log(prices[-1]/prices[-3]), ret[-1], sig)


def peer_feature(index,t):
    keys=[t-2*HOUR,t-HOUR,t]
    rows=[index.get(u) for u in keys]
    if any(v is None or v[0]!=key-HOUR for v,key in zip(rows,keys)):
        return None
    return math.log(rows[-1][2]/rows[0][2])


def next_outcome(series,t):
    nextbar=series.get(t+HOUR)
    exitbar=series.get(t+2*HOUR)
    if (nextbar is None or exitbar is None or
        nextbar[0]!=t or exitbar[0]!=t+HOUR):
        return None
    return (nextbar[1],exitbar[2])


def signed_payoff_eur(side,open_raw,close_raw,eurusd_exit_raw,units,commission_usd):
    need(eurusd_exit_raw>0,"HXP1_FX_CONVERSION_INVALID")
    euro_per_usd=PRICE_FACTOR/eurusd_exit_raw
    gross=side*units*(close_raw-open_raw)/PRICE_FACTOR*euro_per_usd
    return gross, gross-commission_usd*euro_per_usd


def observations(p,bundle,bounds,commission):
    universe=p["universe"]
    streams=prepare_series(bundle,p)
    by_phase=defaultdict(list)
    support=defaultdict(lambda: defaultdict(int))
    # Historical observations are formed BEFORE inspecting their future path.
    # Own and peer features are all from t or earlier.
    for target in universe:
        target_series=streams[target]
        peers=[k for k in universe if k!=target]
        for t in sorted(target_series):
            phase=phase_at(t,t+2*HOUR,bounds)
            if phase is None:
                continue
            if phase=="UNKNOWN_MATURITY":
                support["BOUNDARY"]["unknownMaturity"]+=1
                continue
            f=series_feature(target_series,t)
            px=[peer_feature(streams[s],t) for s in peers]
            if f is None or any(v is None for v in px):
                support[phase]["missingCausalFeature"]+=1
                continue
            r2,r1,sig=f
            if px[0]*px[1] <= 0.0:
                support[phase]["peerDisagreement"]+=1
                continue
            peer=(px[0]+px[1])/2.0  # median for two aligned peers
            direction=1 if peer>0 else -1
            support[phase]["causalClocks"]+=1
            if not (abs(peer)>1.5*math.sqrt(2)*sig and
                    abs(r2)<0.5*abs(peer) and
                    direction*r1>=-0.5*sig):
                support[phase]["abstainedExAnte"]+=1
                continue
            support[phase]["preDecisionSignals"]+=1
            market=next_outcome(target_series,t)
            eur=streams["EURUSD"].get(t+2*HOUR)
            if market is None or eur is None or eur[0]!=t+HOUR:
                support[phase]["unknownForwardOutcome"]+=1
                continue
            opening,closing=market
            need(opening>0 and closing>0, "HXP1_INVALID_FORWARD_PRICES")
            eg,ec=signed_payoff_eur(direction,opening,closing,eur[2],1000,commission)
            benchmark_side=(1 if r2>0 else -1 if r2<0 else 0)
            mg,mc=signed_payoff_eur(benchmark_side,opening,closing,eur[2],1000,
                                    commission if benchmark_side!=0 else 0)
            lg,lc=signed_payoff_eur(1,opening,closing,eur[2],1000,commission)
            need(math.isfinite(ec) and math.isfinite(mc) and math.isfinite(lc),
                 "HXP1_NONFINITE_FINANCIAL_RESULT")
            week=int((t-bounds[0])//WEEK)
            by_phase[phase].append({
                "week":week,"symbol":target,
                "correct":(closing-opening)*direction>0,
                "eventGrossEur":eg,"eventCommissionFloorEur":ec,
                "matchedMomentumGrossEur":mg,"matchedMomentumCommissionFloorEur":mc,
                "longCommissionFloorEur":lc,
                "grossReturnBps":direction*10000*math.log(closing/opening),
                "durationH":2})
    return by_phase,support


def bound_weekly(rows,start_week,count,metric,other=None):
    sums=[0.0]*count
    for row in rows:
        index=row["week"]-start_week
        need(0<=index<count, "HXP1_PHASE_ROW_MISMATCH")
        sums[index]+=row[metric]-(row[other] if other else 0.0)
    avg=mean(sums)
    threshold={13:2.179,26:2.060}[count]
    lower=avg-threshold*(stdev(sums)/math.sqrt(count))
    return {"weeklyMeanEur":round(avg,6),"weeklyLower95Eur":round(lower,6),
            "weeksWithSignals":sum(bool(x) for x in
              [sum(row["week"]==start_week+i for row in rows) for i in range(count)]),
            "weeklyTotalsEur":[round(v,5) for v in sums]}


def summary(rows):
    if not rows:
        return {"n":0,"grossEur":0.0,"commissionOnlyEur":0.0,
                "correctSignFraction":None}
    values=[row["eventCommissionFloorEur"] for row in rows]
    returns=[row["grossReturnBps"] for row in rows]
    q=sorted(values)
    return {
        "n":len(rows),
        "grossEur":round(sum(row["eventGrossEur"] for row in rows),6),
        "commissionOnlyEur":round(sum(values),6),
        "matchedMomentumCommissionOnlyEur":round(sum(row["matchedMomentumCommissionFloorEur"] for row in rows),6),
        "alwaysLongCommissionOnlyEur":round(sum(row["longCommissionFloorEur"] for row in rows),6),
        "meanCommissionOnlyEurPerSignal":round(mean(values),6),
        "meanGrossBpsPerSignal":round(mean(returns),6),
        "correctSignFraction":round(mean(1 if row["correct"] else 0 for row in rows),6),
        "minimumCommissionOnlyEur":round(q[0],6),
        "medianCommissionOnlyEur":round(median(values),6),
        "maximumCommissionOnlyEur":round(q[-1],6),
    }


def run():
    protocol_bytes=PROTOCOL.read_bytes()
    p=json.loads(protocol_bytes)
    bounds=invariant_policy(p)
    bundle,source_receipt,verified=check_source(p)
    commission=fee_context(p)
    phases,support=observations(p,bundle,bounds,commission)
    phase_order=(("TRAIN",0,26),("SELECTION",26,13),
                 ("EXPOSED_DESCRIPTIVE",39,13))
    results={}
    for name,week,count in phase_order:
        rows=phases[name]
        results[name]={
            "population":dict(support[name]),
            "allThreeInstruments":summary(rows),
            "perInstrument":{symbol:summary([r for r in rows if r["symbol"]==symbol])
                              for symbol in p["universe"]},
            "weeklyCashComparator":bound_weekly(rows,week,count,"eventCommissionFloorEur"),
            "weeklyMatchedMomentumIncrement":bound_weekly(
                rows,week,count,"eventCommissionFloorEur",
                "matchedMomentumCommissionFloorEur")
        }
    train=results["TRAIN"]
    train_gate=(train["weeklyCashComparator"]["weeksWithSignals"]>=8 and
                train["weeklyCashComparator"]["weeklyLower95Eur"]>0 and
                train["weeklyMatchedMomentumIncrement"]["weeklyLower95Eur"]>0)
    selection=results["SELECTION"]
    select_gate=(train_gate and
                 selection["weeklyCashComparator"]["weeklyLower95Eur"]>0 and
                 selection["weeklyMatchedMomentumIncrement"]["weeklyLower95Eur"]>0)
    receipt={
        "schema":"MXM_HXP1_AUTHENTIC_HISTORICAL_PREDICTIVE_ECONOMIC_PROXY_V1",
        "study":"HXP1",
        "sourceRun":p["originalAuthenticatedSource"]["workflowRunId"],
        "sourceProtocolSha256":source_receipt["protocolSha256"],
        "studyProtocolSha256":hashlib.sha256(protocol_bytes).hexdigest(),
        "originalBrokerRawTrendbarRequestsVerified":verified["rawRequestsRebuilt"],
        "originalAuthenticatedH1Bars":{k:len(v) for k,v in bundle["bars"].items() if k.endswith("/H1")},
        "hypothesis":"FROZEN_FX_USD_QUOTE_DELAYED_PEER_CATCHUP",
        "trainFrozenPolicyAdmitted":train_gate,
        "selectionCommissionFloorGate":select_gate,
        "selectionPolicyIfExecuted":"SHADOW_ONLY_EVEN_IF_GATE_TRUE",
        "phases":results,
        "financeEvidence":{
            "commissionPerMinimumRoundTripUsd":commission,
            "commissionTermsAsOf":"2026-11-04",
            "currentTermNotHistoricalCertainty":True,
            "missingHistoricalBidAskSpreadSlippageSwapFxConversionExecution":True,
            "fullBrokerNetEur":None,
            "fundedNative300EurNet":None,
            "drawdownFloatingProven":False,
            "hard21Proven":False,
            "independentConfirmation":False
        },
        "status":"PRICE_ONLY_PREDICTIVE_ASSESSMENT_FULL_NET_UNPROVEN",
        "brokerOrders":0,"cloudActivated":False,
        "neverQualifiedByExposedAudit":True
    }
    OUTPUT.write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("HXP1_AUTHENTIC_PRICE_PREDICTION_COMPLETE_ECONOMICS_COST_FLOOR_ONLY",flush=True)


if __name__=="__main__":
    try:
        run()
    except Exception:
        print("HXP1_ORIGINAL_HISTORICAL_EVALUATION_FAILED_DETAIL_WITHHELD",flush=True)
        raise SystemExit(1)

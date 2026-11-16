"""WPS1 original-readback PRE-OUTCOME causal support gate ONLY.

This module NEVER imports BWR1 first_signal/financial/monetary nor reads
post-10:45 returns into a WPS1 feature or evaluates any future label.
"""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, time, timedelta
from decimal import Decimal as D
from hashlib import sha256
from pathlib import Path
from statistics import median
from zoneinfo import ZoneInfo
import base64
import json
import math
import os

from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .custody import unseal_new
from .decode import decode_bars, need
from .guard import require_read_only_request
from .rne1_source_financial_preflight import fee_usd,Unpriced

SOURCE=Path("wps1-source/bwr1-original-encrypted-source.v2.enc")
PROTOCOL=Path("research/WPS1_EIA_PETROLEUM_SUPPORT_PRESOURCE_20261116.md")
OUT=Path("wps1-original-event-support-cost-preflight-public.json")
RUN="43576022822"
CIPHER="a019aaf2131173832630863d83bfa2127fb3a3d8ed6a6c22002fc42dc2b280e7"
PLAIN="df5f7f39e24921112bf89adde9aa47dccbee00f14d2b843a97860b2eb693e042"
NY=ZoneInfo("America/New_York")
START=date(2025,11,3)
OFF={date(2026,1,21),date(2026,2,18),date(2026,5,27),
     date(2026,9,9),date(2026,10,14)}
M5=300000
TARGETS=("SpotBrent","SpotCrude")
MIN_MARGIN_CEILING_EUR=210
SPREAD_BPS=D("3.552736")
ASSUMED_SLIPPAGE_BPS=D("2.0")
COST_HURDLE_BPS=SPREAD_BPS+ASSUMED_SLIPPAGE_BPS


def stamp(day,hh,mm):
    return int(datetime.combine(day,time(hh,mm),NY).timestamp()*1000)


def releases():
    day=date(2026,1,7)
    events=[]
    while day<=date(2026,10,28):
        if day not in OFF:
            events.append(day)
        day+=timedelta(days=7)
    need(len(events)==38,"WPS1_FIXED_RELEASE_COUNT")
    return events


def decode_original_source():
    need(PROTOCOL.exists() and "PRE-OUTCOME SOURCE" in PROTOCOL.read_text(),
         "WPS1_PRESOURCE_MISSING")
    cipher=SOURCE.read_bytes()
    need(sha256(cipher).hexdigest()==CIPHER,"WPS1_CIPHER_CHANGED")
    secret=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(secret.strip()),"WPS1_CUSTODY_KEY_NOT_AUTHORIZED")
    plain=unseal_new(cipher,secret,RUN)
    need(sha256(plain).hexdigest()==PLAIN,"WPS1_PLAINTEXT_MISMATCH")
    a=json.loads(plain)
    need(a.get("schema")=="MXM_BWR1_ORIGINAL_BRENT_WTI_CFD_SOURCE_PRIVATE"
         and a.get("run")==RUN and a.get("originalPepperstoneEurAccountBound") is True
         and a.get("postEntryEconomicScoringNotStarted") is True
         and a.get("readonlyCallsAfterAuthentication")==979
         and len(a.get("originalBrokerProtobuf",[]))==979
         and len(a.get("decodedOriginalBarsAndQuotes",{}))==260,
         "WPS1_ORIGINAL_SOURCE_SCHEMA_OR_COUNT")
    raw=a["originalBrokerProtobuf"]
    _,trader=parse(raw[0])
    _,assetres=parse(raw[1])
    _,roster=parse(raw[2])
    account=trader.ctidTraderAccountId
    fp=sha256(("ctrader-account:"+str(account)).encode("ascii")).hexdigest()
    need(sha256(fp.encode("ascii")).hexdigest()==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
         and trader.trader.HasField("brokerName")
         and "pepperstone" in trader.trader.brokerName.casefold(),
         "WPS1_ACCOUNT_FINGERPRINT")
    currency={x.assetId:x.name for x in assetres.asset}
    need(currency.get(trader.trader.depositAssetId)=="EUR"
         and assetres.ctidTraderAccountId==account
         and roster.ctidTraderAccountId==account,
         "WPS1_EUR_ACCOUNT")
    sym={x.symbolName:x.symbolId for x in roster.symbol if x.enabled}
    need(all(s in sym for s in TARGETS+("EURUSD",)),
         "WPS1_ORIGINAL_ROSTER")
    terms={}
    observed_raw_bars={}
    for row in raw:
        req,res=parse(row)
        need(req.ctidTraderAccountId==account
             and res.ctidTraderAccountId==account,
             "WPS1_WIRE_ACCOUNT_UNBOUND")
        if isinstance(req,m.ProtoOASymbolByIdReq):
            for c in res.symbol:
                if c.symbolId in [sym[s] for s in TARGETS]:
                    need(c.symbolId not in terms,"WPS1_DUPLICATE_CONTRACT")
                    terms[c.symbolId]=c
        if isinstance(req,m.ProtoOAGetTrendbarsReq):
            need(req.period==e.M5 and req.symbolId in
                 [sym[s] for s in TARGETS], "WPS1_BAR_REQUEST_SYMBOL")
            day=datetime.fromtimestamp(req.fromTimestamp/1000,NY).date()
            need(req.fromTimestamp==stamp(day,8,25)
                 and req.toTimestamp==stamp(day,11,40),
                 "WPS1_BAR_SOURCE_CLOCK")
            name=next(k for k in TARGETS if sym[k]==req.symbolId)
            need((day.isoformat(),name) not in observed_raw_bars,
                 "WPS1_DUPLICATE_BAR_REQUEST")
            if isinstance(res,m.ProtoOAErrorRes):
                need(res.errorCode=="NO_QUOTES",
                     "WPS1_ORIGINAL_BAR_SERVER_REJECTION")
                observed_raw_bars[day.isoformat(),name]={}
            else:
                need(isinstance(res,m.ProtoOAGetTrendbarsRes)
                     and res.period==e.M5,"WPS1_BAR_RESPONSE")
                if res.hasMore:
                    observed_raw_bars[day.isoformat(),name]={}
                else:
                    low,high=req.fromTimestamp,req.toTimestamp
                    zz=decode_bars(res.trendbar,low-2*M5,high+2*M5,5)
                    observed_raw_bars[day.isoformat(),name]={
                        str(x[1]):x[5] for x in zz}
    need(len(observed_raw_bars)==520
         and all(sym[s] in terms for s in TARGETS),
         "WPS1_MISSING_ORIGINAL_BAR_OR_CONTRACT")
    series=a["decodedOriginalBarsAndQuotes"]
    for w in range(52):
        for d in range(5):
            day=START+timedelta(weeks=w,days=d)
            key=day.isoformat()
            need(key in series and series[key]["week"]==w,
                 "WPS1_SOURCE_DAY_MISSING")
            for s in TARGETS:
                need(series[key]["bars"][s]==observed_raw_bars[(key,s)],
                     "WPS1_ORIGINAL_BAR_NOT_REBUILT")
    current=a["currentContractSnapshot"]["SpotBrent"]
    contract=terms[sym["SpotBrent"]]
    need(current["minimumWireVolume"]==contract.minVolume
         and contract.minVolume>0 and contract.minVolume%100==0
         and current["currentMarginBuyEur"] is not None
         and current["currentMarginSellEur"] is not None,
         "WPS1_MINIMUM_CONTRACT_MARGIN_UNKNOWN")
    margins=max(current["currentMarginBuyEur"],
                current["currentMarginSellEur"])
    try:
        fees=(fee_usd(contract,D(contract.minVolume)/100,D("80"))+
              fee_usd(contract,D(contract.minVolume)/100,D("80")))
        fees_known_zero=fees==0
    except (Unpriced,ValueError):
        fees_known_zero=False
    return series,float(margins),bool(fees_known_zero)


def parse(row):
    q=getattr(m,row["requestType"])()
    q.ParseFromString(base64.b64decode(row["request"],validate=True))
    require_read_only_request(q)
    k=getattr(m,row["responseType"])()
    k.ParseFromString(base64.b64decode(row["response"],validate=True))
    need(q.IsInitialized() and k.IsInitialized(),
         "WPS1_ORIGINAL_PROTOBUF_UNINITIALIZED")
    return q,k


def presignal_feature(bars,day):
    """Reads ONLY ten M5 completed closes ending by 10:45 NY."""
    needs=[stamp(day,10,0)+i*M5 for i in range(10)]
    paths={}
    for symbol in TARGETS:
        own=bars[symbol]
        path=[int(own.get(str(t),0)) for t in needs]
        if any(x<=0 for x in path):
            return {"state":"MISSING_PREDECISION_SOURCE"}
        paths[symbol]=path
    w=math.log(paths["SpotCrude"][9]/paths["SpotCrude"][6])*10000
    b=math.log(paths["SpotBrent"][9]/paths["SpotBrent"][6])*10000
    if not all(math.isfinite(x) for x in [w,b]):
        return {"state":"INVALID_PREDECISION"}
    lead=(w*b>0 and abs(w)>abs(b))
    residual=abs(w)-abs(b) if lead else 0
    return {"state":"WTI_LEADS" if lead else "OTHER",
            "side":(1 if w>0 else -1) if lead else 0,
            "halfResidualOverHurdle":bool(
                lead and D(str(residual))/2>COST_HURDLE_BPS),
            "halfResidualBps":residual/2 if lead else 0,
            "initialWtiMoveBps":abs(w)}


def evaluate(series,margin_eur,fee_zero):
    wps_dates=releases()
    halves=[wps_dates[:19],wps_dates[19:]]
    c=Counter()
    release_feat=[]
    placebo_feat=[]
    for day in wps_dates:
        controls=[(day,"RELEASE"),(day-timedelta(days=1),"PLACEBO")]
        for date_,arm in controls:
            feature=presignal_feature(series[date_.isoformat()]["bars"],date_)
            c[arm+"_"+feature["state"]]+=1
            if arm=="RELEASE":release_feat.append(feature)
            else:placebo_feat.append(feature)
    need(len(release_feat)==len(placebo_feat)==38,
         "WPS1_CENSUS_SCHEDULE")
    leading=[x for x in release_feat if x["state"]=="WTI_LEADS"]
    quality=len(leading)
    good_cost=[x for x in leading if x["halfResidualOverHurdle"]]
    half=[release_feat[:19],release_feat[19:]]
    leader_counts=[sum(x["state"]=="WTI_LEADS" for x in h) for h in half]
    cost_counts=[sum(x["halfResidualOverHurdle"] for x in h) for h in half]
    valid_w=sum(x["state"]!="MISSING_PREDECISION_SOURCE" for x in release_feat)
    valid_t=sum(x["state"]!="MISSING_PREDECISION_SOURCE" for x in placebo_feat)
    source_support=valid_w>=34 and valid_t>=34
    state_support=(quality>=10 and c["RELEASE_OTHER"]>=10
                   and sum(x["side"]==1 for x in leading)>=4
                   and sum(x["side"]==-1 for x in leading)>=4
                   and all(x>=4 for x in leader_counts))
    capital_cost=(0<margin_eur<MIN_MARGIN_CEILING_EUR
                  and fee_zero and len(good_cost)>=8
                  and all(x>=3 for x in cost_counts))
    passed=source_support and state_support and capital_cost
    return {"schema":"MXM_WPS1_ORIGINAL_PREOUTCOME_EIA_PETROLEUM_SOURCE_SUPPORT_V1",
       "status":"PASS_SUPPORT_ONLY_NO_PREDICTION" if passed else
           "WPS1_PREFLIGHT_STOP_NO_FUTURE_SCORING",
       "preregisteredProtocolSha256":sha256(PROTOCOL.read_bytes()).hexdigest(),
       "originalBwr1SourceRunId":int(RUN),
       "originalBwr1CiphertextSha256":CIPHER,
       "originalBwr1PlaintextSha256":PLAIN,
       "originalRawReadonlyProtobufCallsRebuilt":979,
       "genuineSourceDailyBarsVerified":520,
       "sourceBrokerOrders":0,"newBrokerRequests":0,"cloudActivated":False,
       "predecisionOnly":True,"wprFutureReturnLabelsInspected":False,
       "globallyExposedDevelopment":True,
       "scheduledEiaRegularEvents":38,"scheduledTuesdayPlacebo":38,
       "registeredShiftedReleaseWednesdays":5,
       "predecisionSourceStates":dict(c),
       "wtiLeadingBothSigns":{"long":sum(x["side"]==1 for x in leading),
                              "short":sum(x["side"]==-1 for x in leading)},
       "releaseLeadingFirst19Second19":leader_counts,
       "halfResidualCostPassFirst19Second19":cost_counts,
       "priorObservedBrentSpreadBpsNotUpperBound":float(SPREAD_BPS),
       "assumedAdverseAdditionalSlippageBps":float(ASSUMED_SLIPPAGE_BPS),
       "necessaryCostHurdleExcludingHistoricalUnknownsBps":float(COST_HURDLE_BPS),
       "currentMinimumBrentMarginEur":round(margin_eur,5),
       "currentContractCommissionExplicitlyZero":fee_zero,
       "sourceGate":source_support,
       "twoObservableStatesAndSidesGate":state_support,
       "capitalCostPotentialGate":capital_cost,
       "requiresFutureOriginalBidAskFxForNetEur":True,
       "fundedNetEur":None,"brokerRealizedNetEur":None,
       "historicalExecutableNetCertified":False,
       "independentConfirmation":False,
       "disclosure":"All WPS1 features are <=10:45 NY. No WPS1 future Brent prices, return labels or decisions scored. Initial cost scale is a necessary historical-terms-uncertain heuristic, not alpha or NET. Original BWR1 study untouched."}


def main():
    source,margin,fee_zero=decode_original_source()
    result=evaluate(source,margin,fee_zero)
    OUT.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("WPS1_PREOUTCOME_AUTHENTIC_SOURCE_SUPPORT",
          result["status"],
          json.dumps({"states":result["predecisionSourceStates"],
                      "costSupport":result["halfResidualCostPassFirst19Second19"],
                      "margin":result["currentMinimumBrentMarginEur"]}),flush=True)


if __name__=="__main__":
    main()

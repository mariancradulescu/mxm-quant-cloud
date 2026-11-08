"""CMA2: authenticated read-only paired BID/ASK and current contract cost preflight.

Separate, ex-ante quote-cost observation; no prediction, fills, EUR NET, or
model selection. Reuses owner_readonly_auth.authenticate, stdlib transport, custody v2,
guard allowlist, and immutable protocol. All raw protobuf stays encrypted.
"""
from __future__ import annotations
import base64
import hashlib
import json
import os
import sys
from decimal import Decimal as D
from pathlib import Path
from .owner_readonly_auth import authenticate
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .custody import seal_new,unseal_new
from .custody_new import checked_public
from .decode import decode_side
from .full_inventory_pipeline import _raw_record

P=Path("research/cma2_protocol.json")
SCHEMA="mxm-cma2-real-quote-source-v1"
def need(ok,code):
    if not ok:raise ValueError(code)
def sha(data):return hashlib.sha256(data).hexdigest()
def protocol():return json.loads(P.read_text())

def asof_spread(bid_events,ask_events,clock,age_ms,skew_ms,complete=True):
    """No lookahead: only last events at/before original clock."""
    if not complete:return {"status":"PAGINATION_TRUNCATED","spreadBps":None}
    bids=[(int(t),int(px)) for t,px in bid_events if t<=clock]
    asks=[(int(t),int(px)) for t,px in ask_events if t<=clock]
    if not bids or not asks:return {"status":"QUOTE_SIDE_MISSING","spreadBps":None}
    bt,bp=max(bids,key=lambda x:x[0]);at,ap=max(asks,key=lambda x:x[0])
    if clock-bt>age_ms or clock-at>age_ms or abs(bt-at)>skew_ms:
        return {"status":"STALE_OR_ASYNCHRONOUS","spreadBps":None}
    if bp<=0 or ap<=bp:return {"status":"CROSSED_OR_INVALID","spreadBps":None}
    value=D(20000)*(D(ap)-D(bp))/(D(ap)+D(bp))
    return {"status":"CAUSAL_PAIRED_SPREAD_OBSERVED",
            "spreadBps":str(value.quantize(D("0.000001"))),
            "ageBidMs":int(clock-bt),"ageAskMs":int(clock-at)}

def _unpack(raw):
    allowed={"ProtoOATraderReq","ProtoOAAssetListReq","ProtoOASymbolsListReq",
             "ProtoOASymbolByIdReq","ProtoOAExpectedMarginReq","ProtoOAGetTickDataReq"}
    pairs=[]
    for item in raw:
        need(set(item)=={"requestType","requestProtobuf","type","protobuf"},"CMA2_RAW_SHAPE")
        need(item["requestType"] in allowed and item["type"].endswith("Res"),
             "CMA2_WIRE_TYPE")
        q=getattr(m,item["requestType"])();r=getattr(m,item["type"])()
        q.ParseFromString(base64.b64decode(item["requestProtobuf"],validate=True))
        r.ParseFromString(base64.b64decode(item["protobuf"],validate=True))
        require_read_only_request(q)
        need(q.IsInitialized() and r.IsInitialized(),"CMA2_RAW_INITIALIZED")
        pairs.append((q,r))
    return pairs

def reconstruct(raw,p):
    """Independent raw protobuf source & causal quote-cost reconstruction."""
    need(p["id"]=="CMA2" and p["researchOnly"] is True and
         p["universe"]==["NatGas","JPYX","USDX","AMD.US"] and
         len(p["universe"])==len(set(p["universe"])) and
         len(p["observationUtcMillis"])==3,"CMA2_PROTOCOL")
    pairs=_unpack(raw)
    need(len(pairs)==3+8*len(p["universe"]) and
         len(pairs)<=p["maxSourceRequests"],"CMA2_REQUEST_COUNT")
    tq,tr=pairs[0];aq,ar=pairs[1];lq,lr=pairs[2]
    need(type(tq) is m.ProtoOATraderReq and type(tr) is m.ProtoOATraderRes and
         type(aq) is m.ProtoOAAssetListReq and type(ar) is m.ProtoOAAssetListRes and
         type(lq) is m.ProtoOASymbolsListReq and
         type(lr) is m.ProtoOASymbolsListRes,"CMA2_FIRST_THREE")
    account=int(tr.ctidTraderAccountId)
    need(account>0 and all(int(x.ctidTraderAccountId)==account
         for x in (tq,aq,ar,lq,lr)),"CMA2_ACCOUNT")
    fp=sha(f"ctrader-account:{account}".encode("ascii"))
    need(sha(fp.encode("ascii"))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT,
         "CMA2_HISTORIC_ACCOUNT")
    assets={a.assetId:a.name for a in ar.asset}
    need(tr.trader.HasField("brokerName") and
         "pepperstone" in tr.trader.brokerName.lower() and
         assets.get(tr.trader.depositAssetId)=="EUR","CMA2_BROKER_EUR")
    need(lq.HasField("includeArchivedSymbols") and
         lq.includeArchivedSymbols is False,"CMA2_ARCHIVED")
    listing={s.symbolName:s for s in lr.symbol if s.enabled}
    need(all(s in listing for s in p["universe"]),"CMA2_UNIVERSE_REBOUND")
    cursor=3;out=[]
    for name in p["universe"]:
        sid=int(listing[name].symbolId)
        dq,dr=pairs[cursor];cursor+=1
        mq,mr=pairs[cursor];cursor+=1
        need(type(dq) is m.ProtoOASymbolByIdReq and
             type(dr) is m.ProtoOASymbolByIdRes and
             list(dq.symbolId)==[sid] and len(dr.symbol)==1 and
             dr.symbol[0].symbolId==sid,"CMA2_CONTRACT_BINDING")
        c=dr.symbol[0]
        need(c.HasField("minVolume") and c.minVolume>0 and
             c.HasField("stepVolume") and c.stepVolume>0 and
             c.HasField("maxVolume") and c.maxVolume>=c.minVolume and
             int(c.tradingMode)==0,"CMA2_CONTRACT_UNAVAILABLE")
        need(type(mq) is m.ProtoOAExpectedMarginReq and
             type(mr) is m.ProtoOAExpectedMarginRes and
             mq.symbolId==sid and list(mq.volume)==[c.minVolume] and
             mr.HasField("moneyDigits") and len(mr.margin)==1 and
             mr.margin[0].volume==c.minVolume,"CMA2_MARGIN_BINDING")
        need(0<=mr.moneyDigits<=12 and
             mr.margin[0].buyMargin>=0 and mr.margin[0].sellMargin>=0,
             "CMA2_MARGIN_NUMERIC")
        minmargin=max(D(mr.margin[0].buyMargin),
                      D(mr.margin[0].sellMargin))/(D(10)**mr.moneyDigits)
        row={
            "symbol":name,"minimumUnits":str(D(c.minVolume)/100),
            "minimumMarginEurCurrent":str(minmargin),
            "marginBelowInitial200Eur":minmargin<D(200),
            "commissionRateWirePresent":c.HasField("preciseTradingCommissionRate"),
            "minCommissionWirePresent":c.HasField("preciseMinCommission"),
            "swapLongWirePresent":c.HasField("swapLong"),
            "swapShortWirePresent":c.HasField("swapShort"),
            "swapPeriodWirePresent":c.HasField("swapPeriod"),
            "pnlConversionFeeWirePresent":c.HasField("pnlConversionFeeRate"),
            "commissionTypeExplicit":int(c.commissionType) if c.HasField("commissionType") else None,
            "minCommissionTypeExplicit":int(c.minCommissionType) if c.HasField("minCommissionType") else None,
            "minCommissionAssetExplicit":c.minCommissionAsset if c.HasField("minCommissionAsset") else None,
            "preciseCommissionRateWire":c.preciseTradingCommissionRate if c.HasField("preciseTradingCommissionRate") else None,
            "preciseMinimumCommissionWire":c.preciseMinCommission if c.HasField("preciseMinCommission") else None,
            "pnlConversionFeeRateBpsExplicit":c.pnlConversionFeeRate if c.HasField("pnlConversionFeeRate") else None,
            "lotSizeUnits":str(D(c.lotSize)/100) if c.HasField("lotSize") else None,
            "swapCalculationTypeExplicit":int(c.swapCalculationType) if c.HasField("swapCalculationType") else None,
            "swapLongExplicit":c.swapLong if c.HasField("swapLong") else None,
            "swapShortExplicit":c.swapShort if c.HasField("swapShort") else None,
            "swapChargeTimeUtcMinutesExplicit":c.swapTime if c.HasField("swapTime") else None,
            "swapPeriodHoursExplicit":c.swapPeriod if c.HasField("swapPeriod") else None,
            "swapTripleWeekdayExplicit":int(c.swapRollover3Days) if c.HasField("swapRollover3Days") else None,
            "swapAtWeekendsExplicit":c.chargeSwapAtWeekends if c.HasField("chargeSwapAtWeekends") else None,
            "currentScheduleTimeZone":c.scheduleTimeZone if c.HasField("scheduleTimeZone") else None,
            "currentTradingIntervalCount":len(c.schedule),
            "quotes":[]
        }
        for clock in p["observationUtcMillis"]:
            sides={};complete=True
            for side in (e.BID,e.ASK):
                q,r=pairs[cursor];cursor+=1
                need(type(q) is m.ProtoOAGetTickDataReq and
                     type(r) is m.ProtoOAGetTickDataRes and
                     q.symbolId==sid and q.type==side and
                     q.fromTimestamp==clock-p["tickWindowBeforeClockMs"] and
                     q.toTimestamp==clock and r.HasField("hasMore"),
                     "CMA2_TICK_BINDING")
                if r.hasMore:
                    complete=False;sides[side]=[]
                else:
                    sides[side]=decode_side(r.tickData,
                        clock-p["tickWindowBeforeClockMs"],clock)
            quote=asof_spread(sides[e.BID],sides[e.ASK],clock,
                p["maximumQuoteAgeAtClockMs"],p["maximumBidAskTimeSkewMs"],
                complete=complete)
            row["quotes"].append({"clockUtcMs":clock,**quote})
        out.append(row)
    need(cursor==len(pairs),"CMA2_RAW_TRAILING")
    observed=sum(sum(q["status"]=="CAUSAL_PAIRED_SPREAD_OBSERVED"
                     for q in r["quotes"]) for r in out)
    return {"schema":"mxm-cma2-public-cost-observation-v1",
      "sourceClass":"AUTHENTIC_HISTORICAL_BID_ASK_PLUS_CURRENT_CONTRACT_TERMS",
      "readOnly":True,"originalAccountBindingRechecked":True,
      "sourceRequestCount":len(pairs),"testedSymbols":len(out),
      "symbolClockObservations":len(out)*len(p["observationUtcMillis"]),
      "freshPairedQuoteObservations":observed,
      "rows":out,"filledExecutions":0,"ordersSubmitted":0,"cloudActivated":False,
      "allInHistoricalCostsCertified":False,"financedNetEur":None,
      "feeValueInEur":None,"brokerFillProven":False,"costScoringAllowed":False,
      "hard21Proven":False,"independentConfirmation":False,
      "economicQualification":False}

def collect():
    """Existing cTrader SCOPE_VIEW OAuth, no new secrets or outbound targets."""
    p=protocol();run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-source-recipient"),run)
    t=StdlibCTraderTransport();raw=[]
    try:
        aid=authenticate(t)
        def req(q,expected):
            need(len(raw)<p["maxSourceRequests"],"CMA2_BROKER_BUDGET")
            require_read_only_request(q)
            r=t.request(q)
            need(type(r) is expected and r.IsInitialized() and
                 r.ctidTraderAccountId==q.ctidTraderAccountId==aid,
                 "CMA2_SOURCE_RESPONSE_BINDING")
            raw.append(_raw_record(q,r))
            return r
        req(m.ProtoOATraderReq(ctidTraderAccountId=aid),m.ProtoOATraderRes)
        req(m.ProtoOAAssetListReq(ctidTraderAccountId=aid),m.ProtoOAAssetListRes)
        listed=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=aid,
                  includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        byname={s.symbolName:s for s in listed.symbol if s.enabled}
        need(all(x in byname for x in p["universe"]),"CMA2_MISSING_ACTIVE_SYMBOL")
        for name in p["universe"]:
            sid=byname[name].symbolId
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=aid,
                       symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==sid,
                 "CMA2_DETAIL_ID")
            c=detail.symbol[0]
            need(c.HasField("minVolume") and c.minVolume>0,"CMA2_MIN_VOLUME")
            req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=aid,
                symbolId=sid,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
            for clock in p["observationUtcMillis"]:
                for side in (e.BID,e.ASK):
                    req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=aid,
                        symbolId=sid,type=side,
                        fromTimestamp=clock-p["tickWindowBeforeClockMs"],
                        toTimestamp=clock),m.ProtoOAGetTickDataRes)
        result=reconstruct(raw,p)
        sealed=seal_new(json.dumps({
          "schema":SCHEMA,"readOnly":True,"runId":run,
          "protocolSha256":sha(P.read_bytes()),
          "raw":raw,"auditResultSha256":sha(
              json.dumps(result,sort_keys=True).encode("utf-8"))},
          sort_keys=True).encode("utf-8"),recipient,run)
        output=Path("sealed-output");output.mkdir(exist_ok=True)
        (output/"source.envelope.json").write_bytes(sealed)
        (output/"receipt.public.json").write_text(json.dumps({
          "schema":SCHEMA,"runId":run,"complete":True,
          "ciphertextSha256":sha(sealed),
          "protocolSha256":sha(P.read_bytes()),"ordersSubmitted":0},
          sort_keys=True)+"\n")
        print("CMA2_COMPLETE_SOURCE_SEALED_NO_ECONOMIC_CERTIFICATION",flush=True)
    finally:
        t.close()

def readback():
    p=protocol();run=os.environ["GITHUB_RUN_ID"]
    cipher=Path("sealed-output/source.envelope.json").read_bytes()
    receipt=json.loads(Path("sealed-output/receipt.public.json").read_text())
    need(receipt["complete"] and receipt["runId"]==run and
         receipt["ciphertextSha256"]==sha(cipher) and
         receipt["protocolSha256"]==sha(P.read_bytes()),"CMA2_SEAL_BINDING")
    bundle=json.loads(unseal_new(cipher,
        os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),run))
    need(bundle["schema"]==SCHEMA and bundle["runId"]==run and
         bundle["readOnly"] is True and
         bundle["protocolSha256"]==sha(P.read_bytes()),"CMA2_PROTOCOL_BINDING")
    out=reconstruct(bundle["raw"],p)
    need(sha(json.dumps(out,sort_keys=True).encode("utf-8"))==
         bundle["auditResultSha256"],"CMA2_RAW_AUDIT_MISMATCH")
    out.update(sourceRunId=int(run),sourceCiphertextSha256=sha(cipher),
               protocolSha256=sha(P.read_bytes()),
               authenticatedReadback=True,
               exactProtocolNoRetuning=True)
    Path("cma2.public.json").write_text(json.dumps(out,indent=2,
                                      sort_keys=True)+"\n")
    print("CMA2_READBACK_VERIFIED_SPREAD_ONLY_NO_NET",flush=True)

if __name__=="__main__":
    try:
        readback() if "--readback" in sys.argv else collect()
    except Exception:
        print("CMA2_FAILED_CLOSED_DETAIL_WITHHELD",flush=True)
        raise SystemExit(1)

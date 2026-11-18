"""JFC1 targeted missing JPN225 original EUR expected margin and BID/ASK
read-only official Pepperstone protobuf source, original account-bound.
No predictor, no strategy code, no synthetic return or broker order.
"""
from __future__ import annotations
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
from .cma2_cost_preflight import asof_spread,_unpack

P=Path("research/jfc1_exact_jpn_source_protocol.json")
SCHEMA="mxm-jfc1-exact-jpn225-original-broker-cost-source-v1"
SOURCE=Path("jfc1-sealed-output")
OUT=Path("jfc1-public")


def need(value,code):
    if not value:raise ValueError("JFC1_"+code)


def sha(value):return hashlib.sha256(value).hexdigest()


def plan():
    d=json.loads(P.read_text())
    need(d.get("id")=="JFC1" and
         d.get("schema")=="MXM_JFC1_EXACT_JPN225_READONLY_COST_SOURCE_V1" and
         d.get("status")=="FROZEN_PRESOURCE_UNEXECUTED" and
         d.get("universe")==["JPN225"] and
         len(d["quoteClocksUtcMillis"])==3 and
         d["expectedReadOnlySourceRequests"]==11 and
         d["maximumSourceRequests"]==11 and
         d["originalPepperstoneBrokerOrders"]==0 and
         d["noModelScoring"] is True,
         "SOURCE_PROTOCOL_UNBOUND")
    return d


def reconstruct(raw,p):
    pairs=_unpack(raw)
    need(len(pairs)==11,"ORIGINAL_SOURCE_EXACT_11_REQUESTS")
    (tq,tr),(aq,ar),(lq,lr),(sq,sr),(mq,mr)=pairs[:5]
    need(type(tq) is m.ProtoOATraderReq and
         type(tr) is m.ProtoOATraderRes and
         type(aq) is m.ProtoOAAssetListReq and
         type(ar) is m.ProtoOAAssetListRes and
         type(lq) is m.ProtoOASymbolsListReq and
         type(lr) is m.ProtoOASymbolsListRes and
         type(sq) is m.ProtoOASymbolByIdReq and
         type(sr) is m.ProtoOASymbolByIdRes and
         type(mq) is m.ProtoOAExpectedMarginReq and
         type(mr) is m.ProtoOAExpectedMarginRes,
         "EXACT_GENUINE_SOURCE_TYPES")
    aid=int(tr.ctidTraderAccountId)
    need(aid>0 and all(x.ctidTraderAccountId==aid for x in
         (tq,aq,ar,lq,lr,sq,sr,mq,mr)),
         "SOURCE_ACCOUNT_BINDING")
    fp=sha(f"ctrader-account:{aid}".encode("ascii"))
    need(sha(fp.encode("ascii"))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT,
         "ORIGINAL_ACCOUNT_FINGERPRINT")
    asset_name={asset.assetId:asset.name for asset in ar.asset}
    need(tr.trader.HasField("brokerName") and
         "pepperstone" in tr.trader.brokerName.casefold() and
         asset_name.get(tr.trader.depositAssetId)=="EUR",
         "ORIGINAL_EUR_PEPPERSTONE_IDENTITY")
    need(lq.HasField("includeArchivedSymbols") and
         lq.includeArchivedSymbols is False,"ARCHIVED_SYMBOLS_DISALLOWED")
    roster={s.symbolName:s.symbolId for s in lr.symbol if s.enabled}
    need("JPN225" in roster and list(sq.symbolId)==[roster["JPN225"]] and
         len(sr.symbol)==1 and sr.symbol[0].symbolId==roster["JPN225"],
         "EXACT_JPN225_NOT_JPN225_F")
    c=sr.symbol[0]
    need(c.HasField("minVolume") and c.minVolume>0 and
         c.HasField("stepVolume") and c.stepVolume>0,
         "EXACT_JPN225_NATIVE_MIN_VOLUME")
    need(mq.symbolId==c.symbolId and list(mq.volume)==[c.minVolume] and
         mr.HasField("moneyDigits") and len(mr.margin)==1 and
         mr.margin[0].volume==c.minVolume and
         0<=mr.moneyDigits<=12,
         "EXACT_JPN225_MARGIN_REQUEST_RESPONSE")
    raw_buy=mr.margin[0].buyMargin
    raw_sell=mr.margin[0].sellMargin
    need(raw_buy>=0 and raw_sell>=0,"NEGATIVE_MARGIN_NOT_ALLOWED")
    divisor=D(10)**int(mr.moneyDigits)
    buy=D(raw_buy)/divisor;sell=D(raw_sell)/divisor
    need(buy>0 and sell>0,"ZERO_MARGIN_UNATTESTED")
    def field(name):
        return getattr(c,name) if c.HasField(name) else None
    quotes=[]
    cursor=5
    for clock in p["quoteClocksUtcMillis"]:
        sides={}
        complete=True
        for side in (e.BID,e.ASK):
            q,response=pairs[cursor];cursor+=1
            need(type(q) is m.ProtoOAGetTickDataReq and
                 type(response) is m.ProtoOAGetTickDataRes and
                 q.ctidTraderAccountId==aid and q.symbolId==c.symbolId and
                 q.type==side and
                 q.fromTimestamp==clock-p["tickWindowBeforeClockMs"] and
                 q.toTimestamp==clock and
                 response.ctidTraderAccountId==aid and
                 response.HasField("hasMore"),
                 "ORIGINAL_PAIRED_TICK_QUERY_BINDING")
            if response.hasMore:
                complete=False
                sides[side]=[]
            else:
                sides[side]=decode_side(response.tickData,
                    clock-p["tickWindowBeforeClockMs"],clock)
        row=asof_spread(sides[e.BID],sides[e.ASK],clock,
            p["maximumQuoteAgeAtClockMs"],p["maximumBidAskTimeSkewMs"],
            complete=complete)
        quotes.append({"clockUtcMs":clock,**row})
    need(cursor==len(pairs),"UNCHECKED_PROTOBUF_REMAINDER")
    current_max=max(buy,sell)
    return {
        "schema":"MXM_JFC1_ORIGINAL_EXACT_JPN225_MARGIN_AND_BIDASK_V1",
        "provider":"PEPPERSTONE_CTRADER_OFFICIAL_PROTOBUF_ORIGINAL_EUR_ACCOUNT",
        "readOnly":True,
        "originalBoundEURAccountIndependentlyVerified":True,
        "exactJpn225NotJpn225F":True,
        "sourceRequestCount":len(raw),
        "sourceDateMeaning":"WORKFLOW_EXECUTION_CURRENT_EXPECTED_MARGIN_ONLY",
        "nativeMinVolumeUnits":str(D(c.minVolume)/D(100)),
        "nativeStepVolumeUnits":str(D(c.stepVolume)/D(100)),
        "nativeLotSizeUnits":str(D(c.lotSize)/D(100))
            if c.HasField("lotSize") else None,
        "tradingModeWire":int(c.tradingMode) if c.HasField("tradingMode") else None,
        "preciseCommissionRateWire":field("preciseTradingCommissionRate"),
        "commissionTypeWire":field("commissionType"),
        "minimumCommissionTypeWire":field("minCommissionType"),
        "preciseMinCommissionWire":field("preciseMinCommission"),
        "swapCalculationTypeWire":field("swapCalculationType"),
        "swapLongWire":field("swapLong"),
        "swapShortWire":field("swapShort"),
        "swapTimeWire":field("swapTime"),
        "sourceDateExpectedBuyMarginEur":str(buy),
        "sourceDateExpectedSellMarginEur":str(sell),
        "sourceDateMinimumVolumeWorstSideMarginEur":str(current_max),
        "sourceDateMinimumLegMarginUnder300Eur":current_max<=D(300),
        "sourceDateMinimumLegMarginUnderStress210Eur":current_max<=D(210),
        "marginForOtherExistingPositionsOrPortfolioCertified":False,
        "fixedPastQuoteClocks":quotes,
        "authenticPairedBidAskCount":sum(
            x["status"]=="CAUSAL_PAIRED_SPREAD_OBSERVED" for x in quotes),
        "historicalExecutableQuoteSpreadDistributionCertified":False,
        "historicalCurrencyConversionAndRolloversCertified":False,
        "actualFundedNetEur":None,
        "brokerOrders":0,"cloudActivated":False,
        "economicQualification":False
    }


def collect():
    p=plan()
    run=os.environ.get("GITHUB_RUN_ID","")
    need(run.isdecimal() and int(run)>0,"SOURCE_RUN_BOUND")
    recipient=checked_public(Path("new-source-recipient"),run)
    transport=StdlibCTraderTransport()
    raw=[]
    try:
        account=authenticate(transport)
        def request(req,expected):
            need(len(raw)<p["maximumSourceRequests"],"SOURCE_BUDGET")
            require_read_only_request(req)
            res=transport.request(req)
            need(type(res) is expected and res.IsInitialized() and
                 res.ctidTraderAccountId==req.ctidTraderAccountId==account,
                 "ORIGINAL_BROKER_PROTOBUF_RESPONSE_BINDING")
            raw.append(_raw_record(req,res))
            return res
        request(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        roster=request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                       includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        ids={s.symbolName:s.symbolId for s in roster.symbol if s.enabled}
        need("JPN225" in ids,"EXACT_JPN225_NOT_LISTED")
        sid=ids["JPN225"]
        res=request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                    symbolId=[sid]),m.ProtoOASymbolByIdRes)
        need(len(res.symbol)==1 and res.symbol[0].symbolId==sid and
             res.symbol[0].HasField("minVolume") and
             res.symbol[0].minVolume>0,"EXACT_CURRENT_CONTRACT_UNAVAILABLE")
        request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                    symbolId=sid,volume=[res.symbol[0].minVolume]),
                m.ProtoOAExpectedMarginRes)
        for clock in p["quoteClocksUtcMillis"]:
            for side in (e.BID,e.ASK):
                request(m.ProtoOAGetTickDataReq(
                    ctidTraderAccountId=account,symbolId=sid,type=side,
                    fromTimestamp=clock-p["tickWindowBeforeClockMs"],
                    toTimestamp=clock),m.ProtoOAGetTickDataRes)
        output=reconstruct(raw,p)
        bundle={
            "schema":SCHEMA,"sourceRunId":run,"readOnly":True,
            "protocolSha256":sha(P.read_bytes()),"raw":raw,
            "originalIndependentReconstructionSha256":
                sha(json.dumps(output,sort_keys=True).encode("utf-8")),
            "ordersSubmitted":0,"cloudActivated":False
        }
        private=seal_new(json.dumps(bundle,sort_keys=True).encode("utf-8"),
                         recipient,run)
        SOURCE.mkdir(parents=True,exist_ok=True)
        (SOURCE/"source.envelope.json").write_bytes(private)
        (SOURCE/"receipt.public.json").write_text(json.dumps({
            "schema":SCHEMA,"sourceRunId":run,
            "protocolSha256":sha(P.read_bytes()),
            "sourceCiphertextSha256":sha(private),
            "originalProtobufRequests":len(raw),
            "actualBrokerOrders":0,
            "publishedRawTickData":False
        },sort_keys=True,indent=2)+"\n")
        print("JFC1_EXACT_JPN225_EUR_MARGIN_TICKS_READONLY_SOURCE_SEALED",flush=True)
    finally:
        transport.close()


def readback():
    p=plan()
    run=os.environ.get("GITHUB_RUN_ID","")
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(run.isdecimal() and bool(private.strip()),
         "ORIGINAL_READBACK_CUSTODY_UNAVAILABLE")
    envelope=(SOURCE/"source.envelope.json").read_bytes()
    receipt=json.loads((SOURCE/"receipt.public.json").read_text())
    need(receipt["sourceRunId"]==run and
         receipt["sourceCiphertextSha256"]==sha(envelope) and
         receipt["protocolSha256"]==sha(P.read_bytes()) and
         receipt["originalProtobufRequests"]==11,
         "ORIGINAL_READBACK_SOURCE_HASH_NOT_BOUND")
    bundle=json.loads(unseal_new(envelope,private,run))
    need(bundle["schema"]==SCHEMA and bundle["sourceRunId"]==run and
         bundle["protocolSha256"]==receipt["protocolSha256"] and
         bundle["ordersSubmitted"]==0 and bundle["cloudActivated"] is False,
         "ORIGINAL_READBACK_ENCRYPTED_CONTRACT_MISMATCH")
    original=reconstruct(bundle["raw"],p)
    need(sha(json.dumps(original,sort_keys=True).encode("utf-8"))==
         bundle["originalIndependentReconstructionSha256"],
         "ORIGINAL_READBACK_PROTOBUF_RECONSTRUCTION_HASH_MISMATCH")
    original["sourceRunId"]=run
    original["sourceCiphertextSha256"]=sha(envelope)
    original["sourceProtocolSha256"]=sha(P.read_bytes())
    original["rawBrokerRequestResponseIndependentlyVerified"]=True
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"jfc1-original-jpn225-margin-pairedquotes.public.json").write_text(
        json.dumps(original,sort_keys=True,indent=2)+"\n")
    print("JFC1_ORIGINAL_PEPPERSTONE_EUR_MARGIN_AND_PAIRED_QUOTE_SOURCE_VERIFIED",
          flush=True)


if __name__=="__main__":
    try:
        readback() if "--readback" in sys.argv else collect()
    except Exception:
        print("JFC1_GUARDED_ORIGINAL_BROKER_SOURCE_FAILED_DETAILS_WITHHELD",
              flush=True)
        raise SystemExit(1)

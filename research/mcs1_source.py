"""MCS1 original Pepperstone EUR account LIVE read-only H1 market source.

One fixed 324-request economic programme on THREE prior CMA2 contract-screened
asset classes, NOT three more BID/ASK pilots. Output of source stage is encrypted
raw protobuf, original-account double-hash bound. Protected independent custody
verifies same wire before running native C# market parity then forward economics.
"""
from __future__ import annotations
import json,hashlib,os,sys
from decimal import Decimal as D
from pathlib import Path
from collections import Counter
from .owner_readonly_auth import authenticate
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .custody import seal_new,unseal_new
from .custody_new import checked_public
from .full_inventory_pipeline import _raw_record
from .decode import decode_bars,decode_side
from .csp1_cost_preflight import asof_spread
from .sfx1_source import pairs_from_raw # PLAIN allowlisted decode only; NEVER SFX1 scoring
from .mcs1_economics import evaluate

P=Path("research/mcs1_protocol.json")
SCHEMA="mxm-mcs1-three-class-original-h1-source-v1"
H=3600000;DAY=24*H;WEEK=7*DAY
TARGET=("NatGas","USDX","AMD.US")
def need(ok,reason):
    if not ok:raise ValueError("MCS1_"+reason)
def sha(blob):return hashlib.sha256(blob).hexdigest()
def protocol():return json.loads(P.read_text())
def windows(p):
    z=p["source"];start=z["startUtcMs"]
    a=[(start+i*WEEK,start+(i+1)*WEEK) for i in range(52)]
    a.append((z["exposedAuditEndUtcMs"],z["newerUnscoredEndUtcMs"]))
    return a
def quote_clocks(p):
    start=p["source"]["startUtcMs"]
    return [start+w*WEEK+day*DAY+minute*60000
            for w in range(13) for day,minute in ((2,15*60+45),(3,17*60+45))]
def request_count(p):
    return 3+len(TARGET)*2+len(TARGET)*len(windows(p))+2*len(TARGET)*len(quote_clocks(p))

def reconstruct(raw,p):
    z=p["source"]
    need(p["id"]=="MCS1" and p["status"]=="REGISTERED_UNSCORED" and
         p["locked"] is True and
         [v["symbol"] for v in p["classAndRationale"]]==list(TARGET) and
         z["readOnlyBrokerRequestsExact"]==324 and request_count(p)==324,
         "FIXED_PROTOCOL")
    pairs=pairs_from_raw(raw)
    need(len(pairs)==324,"EXACT_SOURCE_REQUESTS")
    tq,tr=pairs[0];aq,ar=pairs[1];lq,lr=pairs[2]
    need(type(tq) is m.ProtoOATraderReq and type(tr) is m.ProtoOATraderRes and
         type(aq) is m.ProtoOAAssetListReq and type(ar) is m.ProtoOAAssetListRes and
         type(lq) is m.ProtoOASymbolsListReq and
         type(lr) is m.ProtoOASymbolsListRes,"HEADER_TYPE")
    account=int(tr.ctidTraderAccountId)
    fp=sha(f"ctrader-account:{account}".encode("ascii"))
    need(account>0 and sha(fp.encode("ascii"))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and
         all(q.ctidTraderAccountId==account for q,r in pairs),
         "ORIGINAL_ACCOUNT_CRYPTO_BINDING")
    assets={a.assetId:a.name for a in ar.asset}
    need(tr.trader.HasField("brokerName") and
         "pepperstone" in tr.trader.brokerName.lower() and
         assets.get(tr.trader.depositAssetId)=="EUR" and
         lq.includeArchivedSymbols is False,"ORIGINAL_EUR_BROKER")
    listing={x.symbolName:x for x in lr.symbol if x.enabled}
    need(all(s in listing for s in TARGET),"CURRENT_SYMBOL_NOT_VISIBLE")
    ids={};terms={};cursor=3
    for symbol in TARGET:
        sid=listing[symbol].symbolId;ids[symbol]=sid
        q,r=pairs[cursor];mq,mr=pairs[cursor+1];cursor+=2
        need(type(q) is m.ProtoOASymbolByIdReq and
             type(r) is m.ProtoOASymbolByIdRes and
             list(q.symbolId)==[sid] and len(r.symbol)==1 and
             r.symbol[0].symbolId==sid and
             type(mq) is m.ProtoOAExpectedMarginReq and
             type(mr) is m.ProtoOAExpectedMarginRes and
             mq.symbolId==sid,"CONTRACT_AND_MARGIN_BINDING")
        c=r.symbol[0]
        need(int(c.tradingMode)==0 and
             c.HasField("minVolume") and c.minVolume>0 and
             c.HasField("maxVolume") and c.maxVolume>=c.minVolume and
             c.HasField("stepVolume") and c.stepVolume>0 and
             c.HasField("lotSize") and c.lotSize>0 and
             c.HasField("digits") and
             list(mq.volume)==[c.minVolume] and
             mr.HasField("moneyDigits") and len(mr.margin)==1 and
             mr.margin[0].volume==c.minVolume,
             "CURRENT_VOLUME_OR_MARGIN_UNKNOWN")
        margin=max(D(mr.margin[0].buyMargin),D(mr.margin[0].sellMargin))/D(10)**mr.moneyDigits
        quote_asset=assets.get(listing[symbol].quoteAssetId)
        need(quote_asset is not None,"UNKNOWN_CONTRACT_QUOTE_ASSET")
        terms[symbol]={
          "quoteAsset":quote_asset,
          "minimumUnits":float(D(c.minVolume)/100),
          "stepUnits":float(D(c.stepVolume)/100),
          "lotSizeUnits":float(D(c.lotSize)/100),
          "minMarginEurAsObserved":str(margin),
          "digits":int(c.digits),
          "commissionType":int(c.commissionType) if c.HasField("commissionType") else None,
          "rateWire":int(c.preciseTradingCommissionRate) if c.HasField("preciseTradingCommissionRate") else None,
          "minimumWire":int(c.preciseMinCommission) if c.HasField("preciseMinCommission") else None,
          "minCommissionType":int(c.minCommissionType) if c.HasField("minCommissionType") else None,
          "minimumCommissionAsset":c.minCommissionAsset if c.HasField("minCommissionAsset") else None,
          "pnlConversionBps":int(c.pnlConversionFeeRate) if c.HasField("pnlConversionFeeRate") else None,
          "swapPeriodHours":int(c.swapPeriod) if c.HasField("swapPeriod") else None,
          "swapClockUtc":int(c.swapTime) if c.HasField("swapTime") else None,
          "swapCalcType":int(c.swapCalculationType) if c.HasField("swapCalculationType") else None,
          "historicalContractContinuityCertified":False}
    bars={s:{} for s in TARGET};trunc=[]
    for lo,hi in windows(p):
        for symbol in TARGET:
            q,r=pairs[cursor];cursor+=1
            need(type(q) is m.ProtoOAGetTrendbarsReq and
                 type(r) is m.ProtoOAGetTrendbarsRes and
                 q.symbolId==ids[symbol] and q.period==e.H1 and
                 q.fromTimestamp==lo and q.toTimestamp==hi and
                 r.period==e.H1 and r.HasField("hasMore") and
                 (not r.HasField("symbolId") or r.symbolId==ids[symbol]),
                 "H1_SOURCE_WINDOW_BINDING")
            if r.hasMore:
                trunc.append({"symbol":symbol,"fromUtcMs":lo,"reason":"PAGINATED_H1_UNUSABLE"})
                continue
            for row in decode_bars(r.trendbar,lo-H,hi+H,60):
                if lo<=row[0] and row[1]<=hi:
                    stamp=int(row[1]);value=(stamp,row[2],row[3],row[4],row[5],row[6])
                    need(stamp not in bars[symbol] or bars[symbol][stamp]==value,
                         "CONFLICTING_H1_BAR")
                    bars[symbol][stamp]=value
    quoted={s:[] for s in TARGET}
    failures={s:Counter() for s in TARGET}
    for clock in quote_clocks(p):
        for symbol in TARGET:
            sides={};complete=True
            for side in (e.BID,e.ASK):
                q,r=pairs[cursor];cursor+=1
                need(type(q) is m.ProtoOAGetTickDataReq and
                     type(r) is m.ProtoOAGetTickDataRes and
                     q.symbolId==ids[symbol] and q.type==side and
                     q.fromTimestamp==clock-z["tickLookbackMs"] and
                     q.toTimestamp==clock and r.HasField("hasMore"),
                     "BID_ASK_COST_SOURCE_CLOCK")
                if r.hasMore:
                    complete=False;sides[side]=[]
                else:
                    sides[side]=decode_side(r.tickData,
                        clock-z["tickLookbackMs"],clock)
            pair=asof_spread(sides[e.BID],sides[e.ASK],clock,
                             z["maximumBidAskAgeMs"],
                             z["maximumQuoteSkewMs"],complete)
            if pair["status"]=="CAUSAL_PAIRED_SPREAD_OBSERVED":
                quoted[symbol].append((clock,float(pair["spreadBps"])))
            else:failures[symbol][pair["status"]]+=1
    need(cursor==len(pairs),"TRAILING_UNREAD_SOURCE_RECORD")
    # The five future chronological days are retained only as encrypted source,
    # not accessed by a model decision or an outcome forecast here.
    newly={s:sum(t>z["exposedAuditEndUtcMs"] for t in bars[s]) for s in TARGET}
    result=evaluate(bars,quoted,terms,p)
    result.update({
      "originalPepperstoneEurLiveAccountAuthenticated":True,
      "sourceReadOnlyRequests":len(pairs),
      "originalEncryptedSourceVerified":True,
      "currentBrokerTermsAsObservedOnly":terms,
      "actualSourceNewerUnscoredBarsBySymbol":newly,
      "sourceH1WindowsTruncated":trunc,
      "quotedDevelopmentFailureReasons":{s:dict(v) for s,v in failures.items()},
      "historicalBrokerFeeContinuityCertified":False,
      "actualFillNetEur":None,
      "sameExistingNativeLedgerUsedForResearchParity":True})
    return result

def collect():
    p=protocol();run=os.environ["GITHUB_RUN_ID"]
    need(not Path("docs/MCS1_AUTHENTIC_ECONOMIC_RESULT_20261108.json").exists(),
         "ALREADY_RECEIVED_NO_RECOLLECTION")
    recipient=checked_public(Path("new-source-recipient"),run)
    raw=[];t=StdlibCTraderTransport()
    try:
        acct=authenticate(t)
        def req(q,expected):
            need(len(raw)<p["source"]["readOnlyBrokerRequestsExact"],"SOURCE_BUDGET")
            require_read_only_request(q)
            reply=t.request(q)
            need(type(reply) is expected and reply.IsInitialized() and
                 reply.ctidTraderAccountId==q.ctidTraderAccountId==acct,
                 "ORIGINAL_ACCOUNT_RESPONSE")
            raw.append(_raw_record(q,reply));return reply
        req(m.ProtoOATraderReq(ctidTraderAccountId=acct),m.ProtoOATraderRes)
        req(m.ProtoOAAssetListReq(ctidTraderAccountId=acct),m.ProtoOAAssetListRes)
        listing=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=acct,
                  includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        roster={x.symbolName:x for x in listing.symbol if x.enabled}
        need(all(s in roster for s in TARGET),"PRE_REGISTERED_SYMBOL_UNAVAILABLE")
        for symbol in TARGET:
            sid=roster[symbol].symbolId
            d=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=acct,
                symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(d.symbol)==1 and d.symbol[0].symbolId==sid and
                 d.symbol[0].minVolume>0,"CONTRACT_UNAVAILABLE")
            req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=acct,
                symbolId=sid,volume=[d.symbol[0].minVolume]),
                m.ProtoOAExpectedMarginRes)
        for lo,hi in windows(p):
            for symbol in TARGET:
                req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=acct,
                    symbolId=roster[symbol].symbolId,period=e.H1,
                    fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
        for clock in quote_clocks(p):
            for symbol in TARGET:
                for side in (e.BID,e.ASK):
                    req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=acct,
                        symbolId=roster[symbol].symbolId,type=side,
                        fromTimestamp=clock-p["source"]["tickLookbackMs"],
                        toTimestamp=clock),m.ProtoOAGetTickDataRes)
        need(len(raw)==request_count(p),"UNFINISHED_REQUEST_GRID")
        sealed=seal_new(json.dumps({"schema":SCHEMA,"runId":run,
             "protocolSha256":sha(P.read_bytes()),"raw":raw},
             sort_keys=True).encode(),recipient,run)
        out=Path("sealed-output");out.mkdir(exist_ok=True)
        (out/"source.envelope.json").write_bytes(sealed)
        (out/"receipt.public.json").write_text(json.dumps({
           "schema":SCHEMA,"runId":run,"protocolSha256":sha(P.read_bytes()),
           "sourceReadOnlyRequests":len(raw),"ciphertextSha256":sha(sealed),
           "complete":True,"ordersSubmitted":0},sort_keys=True)+"\n")
        print("MCS1_AUTHENTIC_THREE_CLASS_H1_RAW_SEALED_NO_ECONOMIC_SCORE",flush=True)
    finally:t.close()

def readback():
    p=protocol();run=os.environ["GITHUB_RUN_ID"]
    ciphertext=Path("sealed-output/source.envelope.json").read_bytes()
    receipt=json.loads(Path("sealed-output/receipt.public.json").read_text())
    need(receipt["runId"]==run and receipt["schema"]==SCHEMA and
         receipt["complete"] is True and
         receipt["sourceReadOnlyRequests"]==324 and
         receipt["protocolSha256"]==sha(P.read_bytes()) and
         receipt["ciphertextSha256"]==sha(ciphertext),"SEAL_BINDING")
    bundle=json.loads(unseal_new(ciphertext,
        os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),run))
    need(bundle["runId"]==run and bundle["schema"]==SCHEMA and
         bundle["protocolSha256"]==sha(P.read_bytes()),
         "DECRYPTED_ORIGINAL_PROTOCOL")
    outcome=reconstruct(bundle["raw"],p)
    outcome.update({"sourceRunId":int(run),
        "sourceCiphertextSha256":sha(ciphertext),
        "protocolSha256":sha(P.read_bytes()),
        "authenticatedIndependentCustodyReadback":True,
        "futureConfirmationStillRequired":True})
    Path("mcs1-authentic-public.json").write_text(json.dumps(outcome,
        sort_keys=True,indent=2,allow_nan=False)+"\n")
    print("MCS1_ORIGINAL_NATIVE_H1_FEATURE_PARITY_AND_DUAL_STAT_ECONOMICS_DONE",flush=True)

if __name__=="__main__":
    try:readback() if "--readback" in sys.argv else collect()
    except Exception:
        print("MCS1_RESEARCH_FAILED_CLOSED_NO_SOURCE_OR_ECONOMIC_CLAIM",flush=True)
        raise SystemExit(1)

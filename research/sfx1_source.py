"""SFX1: one fixed original Pepperstone LIVE read-only annual M15 collector.

Source and economic stages are separated. Source collects encrypted raw
protobuf only. Protected custody independently decodes, authenticates,
verifies C# parity on completed authentic bars BEFORE forward-return scoring.
No permanent Python dependency in Cloud and no order requests.
"""
from __future__ import annotations
import base64,hashlib,json,os,sys
from collections import Counter
from decimal import Decimal as D
from pathlib import Path
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
from .sfx1_economics import evaluate

P=Path("research/sfx1_protocol.json")
SCHEMA="mxm-sfx1-authenticated-original-m15-source-v1"
M15=900000;W=604800000;DAY=86400000

def need(ok,code):
    if not ok:raise ValueError("SFX1_"+code)
def sha(x):return hashlib.sha256(x).hexdigest()
def protocol():return json.loads(P.read_text())
def windows(p):
    s=p["source"];start=s["startUtcMs"]
    out=[(start+w*W,start+(w+1)*W) for w in range(s["historicalWeeks"])]
    out.append((s["endHistoricalUtcMs"],s["newUnscoredEndUtcMs"]))
    return out
def quote_clocks(p):
    s=p["source"];start=s["startUtcMs"]
    # 13 fixed development weeks, Wednesday 08:15 and Thursday 07:00 UTC.
    return [start+w*W+d*DAY+clock*60000
        for w in range(13) for d,clock in [(2,495),(3,420)]]
def expected_requests(p):
    return 3+len(p["universe"])*2+len(windows(p))*len(p["universe"])+len(quote_clocks(p))*len(p["candidates"])*2

CLASSES={
 "ProtoOATraderReq":m.ProtoOATraderRes,
 "ProtoOAAssetListReq":m.ProtoOAAssetListRes,
 "ProtoOASymbolsListReq":m.ProtoOASymbolsListRes,
 "ProtoOASymbolByIdReq":m.ProtoOASymbolByIdRes,
 "ProtoOAExpectedMarginReq":m.ProtoOAExpectedMarginRes,
 "ProtoOAGetTrendbarsReq":m.ProtoOAGetTrendbarsRes,
 "ProtoOAGetTickDataReq":m.ProtoOAGetTickDataRes
}

def pairs_from_raw(raw):
    pairs=[]
    for item in raw:
        need(set(item)=={"requestType","requestProtobuf","type","protobuf"} and
            item["requestType"] in CLASSES,"RAW_RECORD_ALLOWLIST")
        cls=CLASSES[item["requestType"]]
        need(item["type"]==cls.__name__,"RAW_RESPONSE_TYPE")
        q=getattr(m,item["requestType"])();r=cls()
        q.ParseFromString(base64.b64decode(item["requestProtobuf"],validate=True))
        r.ParseFromString(base64.b64decode(item["protobuf"],validate=True))
        require_read_only_request(q)
        need(q.IsInitialized() and r.IsInitialized() and
            q.ctidTraderAccountId==r.ctidTraderAccountId,"RAW_ACCOUNT_RESPONSE")
        pairs.append((q,r))
    return pairs

def reconstruct(raw,p):
    s=p["source"]
    need(p["locked"] is True and p["id"]=="SFX1" and
         s["expectedAuthenticatedRequests"]==486 and expected_requests(p)==486 and
         p["candidates"]==["EURJPY","AUDJPY","NZDJPY","NZDUSD"] and
         p["universe"]==["EURJPY","AUDJPY","NZDJPY","NZDUSD","EURUSD"],
         "SOURCE_PROTOCOL_DRIFT")
    pairs=pairs_from_raw(raw)
    need(len(pairs)==486 and len(pairs)<=s["maxRequests"],"SOURCE_COUNT")
    tq,tr=pairs[0];aq,ar=pairs[1];lq,lr=pairs[2]
    need(type(tq) is m.ProtoOATraderReq and type(tr) is m.ProtoOATraderRes and
         type(aq) is m.ProtoOAAssetListReq and type(ar) is m.ProtoOAAssetListRes and
         type(lq) is m.ProtoOASymbolsListReq and
         type(lr) is m.ProtoOASymbolsListRes,"SOURCE_HEADER")
    account=int(tr.ctidTraderAccountId)
    fp=sha(f"ctrader-account:{account}".encode("ascii"))
    need(account>0 and sha(fp.encode("ascii"))==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT and
         all(q.ctidTraderAccountId==account for q,r in pairs),
         "SOURCE_ORIGINAL_ACCOUNT")
    assets={a.assetId:a.name for a in ar.asset}
    need("pepperstone" in tr.trader.brokerName.lower() and
         assets.get(tr.trader.depositAssetId)=="EUR" and
         lq.includeArchivedSymbols is False,"SOURCE_EUR_BROKER")
    listing={x.symbolName:x for x in lr.symbol if x.enabled}
    need(all(x in listing for x in p["universe"]),"SOURCE_VISIBLE_ROSTER")
    ids={};terms={};cursor=3
    for name in p["universe"]:
        light=listing[name];sid=int(light.symbolId);ids[name]=sid
        q,r=pairs[cursor];mq,mr=pairs[cursor+1];cursor+=2
        need(type(q) is m.ProtoOASymbolByIdReq and
             list(q.symbolId)==[sid] and len(r.symbol)==1 and
             int(r.symbol[0].symbolId)==sid and
             type(mq) is m.ProtoOAExpectedMarginReq and mq.symbolId==sid,
             "SOURCE_CONTRACT_BINDING")
        c=r.symbol[0]
        need(int(c.tradingMode)==0 and c.HasField("minVolume") and
             c.minVolume>0 and c.HasField("stepVolume") and
             c.stepVolume>0 and c.HasField("lotSize") and c.lotSize>0 and
             c.HasField("maxVolume") and c.maxVolume>=c.minVolume,
             "SOURCE_CONTRACT_DISABLED")
        need(list(mq.volume)==[c.minVolume] and
             mr.HasField("moneyDigits") and len(mr.margin)==1 and
             mr.margin[0].volume==c.minVolume,"SOURCE_MARGINS")
        quoteAsset=assets.get(light.quoteAssetId)
        need(quoteAsset in ("USD","JPY"),"SOURCE_QUOTE_ASSET")
        margin=max(D(mr.margin[0].buyMargin),D(mr.margin[0].sellMargin))/D(10)**mr.moneyDigits
        terms[name]={
          "symbolIdInternalNotPublished":sid,"quoteAsset":quoteAsset,
          "digits":int(c.digits),"pipPosition":int(c.pipPosition),
          "minimumUnits":str(D(c.minVolume)/100),
          "stepUnits":str(D(c.stepVolume)/100),
          "maximumUnits":str(D(c.maxVolume)/100),
          "lotSizeUnits":float(D(c.lotSize)/100),
          "minMarginEur":str(margin),
          "commissionType":int(c.commissionType) if c.HasField("commissionType") else None,
          "rateWire":int(c.preciseTradingCommissionRate) if c.HasField("preciseTradingCommissionRate") else None,
          "minimumWire":int(c.preciseMinCommission) if c.HasField("preciseMinCommission") else None,
          "minCommissionType":int(c.minCommissionType) if c.HasField("minCommissionType") else None,
          "minCommissionAsset":c.minCommissionAsset if c.HasField("minCommissionAsset") else None,
          "pnlConversionBps":int(c.pnlConversionFeeRate) if c.HasField("pnlConversionFeeRate") else None,
          "swapTimeUtcMinute":int(c.swapTime) if c.HasField("swapTime") else None,
          "swapPeriodHours":int(c.swapPeriod) if c.HasField("swapPeriod") else None,
          "swapCalcType":int(c.swapCalculationType) if c.HasField("swapCalculationType") else None,
          "tripleWeekday":int(c.swapRollover3Days) if c.HasField("swapRollover3Days") else None,
          "weekendSwaps":c.chargeSwapAtWeekends if c.HasField("chargeSwapAtWeekends") else None,
          "historicalTariffContinuityCertified":False
        }
    bars={name:{} for name in p["universe"]}
    rejected=[]
    for lo,hi in windows(p):
        for name in p["universe"]:
            q,r=pairs[cursor];cursor+=1
            need(type(q) is m.ProtoOAGetTrendbarsReq and
                 type(r) is m.ProtoOAGetTrendbarsRes and
                 q.symbolId==ids[name] and q.period==e.M15 and
                 q.fromTimestamp==lo and q.toTimestamp==hi and
                 r.period==e.M15 and r.HasField("hasMore") and
                 (not r.HasField("symbolId") or r.symbolId==ids[name]),
                 "SOURCE_M15_REQUEST_PAIR")
            if r.hasMore:
                rejected.append({"symbol":name,"fromUtcMs":lo,"reason":"PAGINATED_M15_WINDOW_UNUSABLE"})
                continue
            for row in decode_bars(r.trendbar,lo-M15,hi+M15,15):
                if lo<=row[0] and row[1]<=hi:
                    t=int(row[1]);value=(t,row[2],row[3],row[4],row[5],row[6])
                    need(t not in bars[name] or bars[name][t]==value,
                         "DUPLICATE_CONFLICT_M15")
                    bars[name][t]=value
    samples={name:[] for name in p["candidates"]}
    failures={name:Counter() for name in p["candidates"]}
    for t in quote_clocks(p):
        for name in p["candidates"]:
            sides={};complete=True
            for side in (e.BID,e.ASK):
                q,r=pairs[cursor];cursor+=1
                need(type(q) is m.ProtoOAGetTickDataReq and
                     type(r) is m.ProtoOAGetTickDataRes and
                     q.symbolId==ids[name] and q.type==side and
                     q.fromTimestamp==t-s["quoteWindowBeforeClockMs"] and
                     q.toTimestamp==t and r.HasField("hasMore"),
                     "SOURCE_HISTORICAL_TICKS_BOUND")
                if r.hasMore:
                    complete=False;sides[side]=[]
                else:
                    sides[side]=decode_side(r.tickData,t-s["quoteWindowBeforeClockMs"],t)
            cost=asof_spread(sides[e.BID],sides[e.ASK],t,
                  s["maxQuoteAgeAtClockMs"],s["maxSideSkewMs"],complete)
            if cost["status"]=="CAUSAL_PAIRED_SPREAD_OBSERVED":
                samples[name].append((t,float(cost["spreadBps"])))
            else:failures[name][cost["status"]]+=1
    need(cursor==len(pairs),"SOURCE_UNREAD_TRAILING")
    # Keep only predeclared new source timeline for audit as observational
    # presence, not a newly certified 12-month confirmation sample.
    post={name:sum(k>s["endHistoricalUtcMs"] for k in bars[name]) for name in p["universe"]}
    economically_valid={
      name:{k:v for k,v in val.items() if k!="symbolIdInternalNotPublished"}
      for name,val in terms.items()}
    result=evaluate(bars,samples,terms,p)
    result.update({
      "newChronologicallyAfterPreviouslyExposedBarsByInstrument":post,
      "originalAccountBound":True,"encryptedRawSourceReadback":True,
      "readOnlyRequestCount":len(pairs),
      "truncatedHistoricalWindows":rejected,
      "sourceContractTermsAsObserved20261108":economically_valid,
      "costPairFailuresByReason":{k:dict(v) for k,v in failures.items()},
      "quotedCostDevelopmentClockCount":len(quote_clocks(p)),
      "newSourceRequestsNoDuplicateOtherM15Archives":True})
    return result

def collect():
    p=protocol();run=os.environ["GITHUB_RUN_ID"]
    need(not Path("docs/SFX1_AUTHENTIC_RESULT_20261108.json").exists(),
         "IMMUTABLE_RESULT_ALREADY_PRESENT")
    recipient=checked_public(Path("new-source-recipient"),run)
    t=StdlibCTraderTransport();raw=[]
    try:
        account=authenticate(t)
        def req(q,klass):
            need(len(raw)<p["source"]["maxRequests"],"READ_ONLY_REQUEST_BUDGET")
            require_read_only_request(q)
            out=t.request(q)
            need(type(out) is klass and out.IsInitialized() and
                out.ctidTraderAccountId==q.ctidTraderAccountId==account,
                "ORIGINAL_ACCOUNT_RAW_RESPONSE")
            raw.append(_raw_record(q,out));return out
        req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        universe=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
            includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        roster={x.symbolName:x for x in universe.symbol if x.enabled}
        need(all(x in roster for x in p["universe"]),"NEW_SOURCE_CANDIDATES_NOT_VISIBLE")
        for name in p["universe"]:
            sid=roster[name].symbolId
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==sid and
                 detail.symbol[0].minVolume>0,"NEW_SOURCE_CONTRACT_MISSING")
            req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                symbolId=sid,volume=[detail.symbol[0].minVolume]),
                m.ProtoOAExpectedMarginRes)
        for lo,hi in windows(p):
            for name in p["universe"]:
                req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                    symbolId=roster[name].symbolId,period=e.M15,
                    fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
        for clock in quote_clocks(p):
            for name in p["candidates"]:
                for side in (e.BID,e.ASK):
                    req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                        symbolId=roster[name].symbolId,type=side,
                        fromTimestamp=clock-p["source"]["quoteWindowBeforeClockMs"],
                        toTimestamp=clock),m.ProtoOAGetTickDataRes)
        need(len(raw)==expected_requests(p),"SOURCE_REQUEST_GRID_INCOMPLETE")
        sealed=seal_new(json.dumps({"schema":SCHEMA,"runId":run,
            "protocolSha256":sha(P.read_bytes()),"raw":raw},
            sort_keys=True).encode(),recipient,run)
        path=Path("sealed-output");path.mkdir(exist_ok=True)
        (path/"source.envelope.json").write_bytes(sealed)
        (path/"receipt.public.json").write_text(json.dumps({
            "schema":SCHEMA,"runId":run,"sourceRequests":len(raw),
            "protocolSha256":sha(P.read_bytes()),"ciphertextSha256":sha(sealed),
            "complete":True,"ordersSubmitted":0},sort_keys=True)+"\n")
        print("SFX1_ORIGINAL_M15_SOURCE_SEALED_UNSCORED_NO_ORDER",flush=True)
    finally:t.close()

def readback():
    p=protocol();run=os.environ["GITHUB_RUN_ID"]
    encrypted=Path("sealed-output/source.envelope.json").read_bytes()
    receipt=json.loads(Path("sealed-output/receipt.public.json").read_text())
    need(receipt["runId"]==run and receipt["schema"]==SCHEMA and
         receipt["complete"] is True and receipt["sourceRequests"]==486 and
         receipt["protocolSha256"]==sha(P.read_bytes()) and
         receipt["ciphertextSha256"]==sha(encrypted),"CUSTODY_HASH_BINDING")
    bundle=json.loads(unseal_new(encrypted,
        os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),run))
    need(bundle["schema"]==SCHEMA and bundle["runId"]==run and
         bundle["protocolSha256"]==sha(P.read_bytes()),"CUSTODY_DECRYPTED_BOUND")
    result=reconstruct(bundle["raw"],p)
    result.update({"sourceRunId":int(run),"sourceCiphertextSha256":sha(encrypted),
        "protocolSha256":sha(P.read_bytes()),"authenticationVerified":True})
    Path("sfx1-authentic-public.json").write_text(json.dumps(result,indent=2,
        sort_keys=True,allow_nan=False)+"\n")
    print("SFX1_AUTHENTIC_M15_NATIVE_PARITY_PREDICTIVE_ECONOMICS_REPLAY_DONE",flush=True)

if __name__=="__main__":
    try:readback() if "--readback" in sys.argv else collect()
    except Exception:
        print("SFX1_FAILED_CLOSED_DETAILS_REDACTED",flush=True)
        raise SystemExit(1)

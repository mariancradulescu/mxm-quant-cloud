"""Coffee original-account *new* targeted tick provenance diagnostic, no score/trade.

Strictly postclosure technical; original MSE1 immutable. Only the three
predeclared historical windows are queried. Every raw broker message is sealed
to the preexisting protected custody recipient before the runner exits.
"""
import base64
from bisect import bisect_right
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from .collect import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as model
from .decode import decode_side
from .guard import require_read_only_request
from .custody import seal_new
from .custody_new import checked_public

WINDOWS=(
    ("sep2_preclose","2026-09-02T16:45:00Z","2026-09-02T17:45:00Z"),
    ("sep3_reopen","2026-09-03T08:00:00Z","2026-09-03T09:00:00Z"),
    ("sep3_exit","2026-09-03T13:40:00Z","2026-09-03T14:20:00Z"),
)
CLOCKS=(
    "2026-09-02T17:00:01.500Z",
    "2026-09-02T17:10:01.500Z",
    "2026-09-02T17:15:01.500Z",
    "2026-09-02T17:30:01.500Z",
    "2026-09-02T17:35:01.500Z",
    "2026-09-03T08:15:01.500Z",
    "2026-09-03T08:20:01.500Z",
    "2026-09-03T13:55:01.500Z",
    "2026-09-03T14:00:01.500Z",
    "2026-09-03T14:05:01.500Z",
)

def ms(value):
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp()*1000)

def spans():
    for label,first,last in WINDOWS:
        lo,stop=ms(first),ms(last)
        assert lo<stop
        while lo<stop:
            hi=min(lo+20*60000,stop)
            yield label,lo,hi
            lo=hi

def collect():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    transport=StdlibCTraderTransport()
    raw=[]
    pages=0
    def req(request,kind,allow_no_quotes=False):
        nonlocal pages
        if len(raw)>=160:raise ValueError("POSTCLOSURE_READONLY_REQUEST_BUDGET")
        require_read_only_request(request)
        response=transport.request(request)
        if (allow_no_quotes and type(response) is m.ProtoOAErrorRes
              and response.errorCode=="NO_QUOTES"
              and response.ctidTraderAccountId==account):
            actual=None
        else:
            if type(response) is not kind or not response.IsInitialized() or (
                response.ctidTraderAccountId!=request.ctidTraderAccountId):
                raise ValueError("POSTCLOSURE_ORIGINAL_ACCOUNT_RESPONSE_MISMATCH")
            actual=response
        raw.append({
            "RequestKind":type(request).__name__,
            "RequestProtobuf":base64.b64encode(request.SerializeToString()).decode(),
            "ResponseKind":type(response).__name__,
            "ResponseProtobuf":base64.b64encode(response.SerializeToString()).decode(),
        })
        return actual
    try:
        account=authenticate(transport)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes).trader
        assets={x.assetId:x.name for x in req(
            m.ProtoOAAssetListReq(ctidTraderAccountId=account),
            m.ProtoOAAssetListRes).asset}
        if "pepperstone" not in trader.brokerName.casefold() or (
            assets.get(trader.depositAssetId)!="EUR"):
            raise ValueError("POSTCLOSURE_NOT_ORIGINAL_PEPPERSTONE_EUR")
        roster={x.symbolName:x for x in req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes).symbol if x.enabled}
        if "Coffee" not in roster:raise ValueError("POSTCLOSURE_COFFEE_SYMBOL_ABSENT")
        symbol_id=int(roster["Coffee"].symbolId)
        detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
            symbolId=[symbol_id]),m.ProtoOASymbolByIdRes)
        if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=symbol_id:
            raise ValueError("POSTCLOSURE_COFFEE_CONTRACT_WRONG")
        schedule={"TimeZone":detail.symbol[0].scheduleTimeZone or None,
            "Intervals":[[q.startSecond,q.endSecond] for q in detail.symbol[0].schedule]}
        decoded={model.BID:[],model.ASK:[]}
        window_counts={}
        for label,start,end in spans():
            pair={}
            for side in (model.BID,model.ASK):
                page_end=end-1
                outputs=[]
                for pagination in range(24):
                    reply=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                        symbolId=symbol_id,type=side,fromTimestamp=start,
                        toTimestamp=page_end),m.ProtoOAGetTickDataRes,True)
                    if reply is None:break
                    rows=decode_side(reply.tickData,start,page_end)
                    outputs.append(rows)
                    pages+=1
                    if not reply.hasMore:break
                    if not rows or rows[0][0]<=start:
                        raise ValueError("POSTCLOSURE_TICK_PAGINATION_UNRESOLVED")
                    page_end=rows[0][0]-1
                else:raise ValueError("POSTCLOSURE_TICK_PAGE_LIMIT")
                items=[item for portion in reversed(outputs) for item in portion]
                if items!=sorted(items,key=lambda t:t[0]):
                    raise ValueError("POSTCLOSURE_TICKS_OUT_OF_ORDER")
                decoded[side].extend(items)
                pair["BID" if side==model.BID else "ASK"]=len(items)
            window_counts[label+"_"+str(start)]=pair
        stamps={}
        for side,label in ((model.BID,"BID"),(model.ASK,"ASK")):
            stamps[label]=sorted(x[0] for x in decoded[side])
        checks=[]
        for clock in CLOCKS:
            at=ms(clock)
            record={"ClockUtc":clock}
            for side in ("BID","ASK"):
                arr=stamps[side];i=bisect_right(arr,at)-1
                age=at-arr[i] if i>=0 else None
                record[side+"PreviousTickAgeMs"]=age
                record[side+"FreshUnder30s"]=bool(age is not None and age<=30000)
            record["TwoSidedFreshUnder30s"]=record["BIDFreshUnder30s"] and record["ASKFreshUnder30s"]
            checks.append(record)
        evidence={"Schema":"MXM_COFFEE_POSTCLOSURE_TICK_PROVENANCE_V1",
            "RunId":run,"ReadOnly":True,"OriginalSourceRunId":43366399346,
            "ContractAsReadNow":schedule,"Windows":WINDOWS,
            "ReadOnlyAuthenticatedMessages":raw,
            "PriceHistoryPagesNeverPublishedPlaintext":True}
        raw_bytes=json.dumps(evidence,separators=(",",":"),sort_keys=True).encode()
        Path("mse1-coffee-targeted-ticks.v2.enc").write_bytes(
            seal_new(raw_bytes,recipient,run))
        public={"Study":"MSE1_COFFEE_POSTCLOSURE_TARGETED_TICKS",
            "Classification":"POSTCLOSURE_SOURCE_DIAGNOSIS_NOT_ECONOMIC_REPLAY",
            "OriginalRunId":43366399346,"OriginalArtifactsUnmodified":True,
            "OriginalAccountBindingAttested":True,"BrokerReadOnlyRequests":len(raw),
            "PriceDataEncrypted":True,"NewSourceSha256":sha256(raw_bytes).hexdigest(),
            "CurrentWeeklySchedule":schedule,
            "HistoricalAsOfScheduleCertified":False,
            "Windows":WINDOWS,"RawBrokerTickCounts":window_counts,
            "ClockFreshnessAudit":checks,
            "IntrabarStopOrBrokerExecutionCertified":False,
            "OrdersSubmitted":0,"CloudActivated":False,
            "IndependentConfirmation":False,
            "EconomicResultsProduced":False}
        Path("mse1-coffee-targeted-ticks-public.json").write_text(
            json.dumps(public,indent=2,sort_keys=True)+"\n")
        print("MSE1_COFFEE_TARGETED_READONLY_PROVENANCE",json.dumps({
            "ReadOnlyRequests":len(raw),"OriginalRunUnmodified":True,
            "OrdersSubmitted":0,"CloudActivated":False}),flush=True)
    finally:
        transport.close()

if __name__=="__main__":
    collect()

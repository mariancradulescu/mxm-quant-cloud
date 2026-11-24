"""Distinct, bounded, SOURCE-ONLY historical deal and account universe inventory.

No tariff interpolation, economic evaluation, trade operations, or raw public data.
Existing P05 and historical study transports remain unchanged.
"""
import base64
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import time

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as model
from .ctrader_transport import (StdlibCTraderTransport, ProtoHeartbeatEvent,
    MAX_FRAME_BYTES, TransportError, decode_envelope, extract_payload, encode_envelope)
from .p05_safe_transport import P05ReadOnlyTransport, check_outbound_frame
from .owner_readonly_auth import authenticate
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .guard import require_read_only_request
from .decode import need, decode_bars
from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .funding_provenance_point_source import SWAP_FIELDS

MARKER = "OWNER_SOURCE_HISTORY_UNIVERSE_20261124"
MARKER_PATH = Path("ops/source-history-universe-once.txt")
OUT = Path("source-history-universe")
DAY = 86400000
WEEK = 7*DAY
START = int(datetime(2025,11,17,tzinfo=timezone.utc).timestamp()*1000)
END = int(datetime(2026,11,24,tzinfo=timezone.utc).timestamp()*1000)
PROBE_START = END-WEEK
MAX_ROWS = 1000
MAX_DEAL_QUERIES = 160
MAX_REQUESTS = 520
CONTRACT_BATCH = 50
TIMEFRAME_TRANCHE = 16
PERIODS = {"M1":1,"M5":5,"M15":15,"M30":30,"H1":60,"H4":240,"D1":1440}
ALL_PERIODS = ("M1","M2","M3","M4","M5","M10","M15","M30","H1","H4","H12","D1","W1","MN1")
UNCOLLECTED = "NECOLECTAT"
ATTEMPTED = "COLECTARE_INCERCATA"
NO_RESPONSE = "INCERCARE_FARA_RASPUNS"
VERIFIED = "COLECTAT_SI_VERIFICAT"

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def canonical(data):
    return json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False).encode()

def original_account(account):
    return digest(digest(("ctrader-account:"+str(account)).encode("ascii")).encode("ascii")) == HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT

def bounded_deal(q, bound):
    need(type(q) is m.ProtoOADealListReq and q.payloadType == m.ProtoOADealListReq().payloadType
         and q.IsInitialized() and bound is not None and q.ctidTraderAccountId == bound
         and all(q.HasField(f) for f in ("fromTimestamp","toTimestamp","maxRows"))
         and START <= q.fromTimestamp <= q.toTimestamp < END
         and q.toTimestamp-q.fromTimestamp < WEEK and 0 < q.maxRows <= MAX_ROWS,
         "HISTORY_DEAL_READ_ONLY_SCOPE")

class SourceHistoryTransport(P05ReadOnlyTransport):
    """The only new wire permission is a bounded read of historical deals."""
    bound = None

    def bind(self, account):
        need(self.bound is None and original_account(account), "HISTORY_ORIGINAL_ACCOUNT")
        self.bound = account

    def _send_bytes(self, frame):
        if not isinstance(frame,bytes) or len(frame)<5:
            raise TransportError("HISTORY_FRAME")
        n = struct.unpack("!I",frame[:4])[0]
        if n<=0 or n>MAX_FRAME_BYTES or n!=len(frame)-4:
            raise TransportError("HISTORY_FRAME")
        decoded = extract_payload(decode_envelope(frame[4:]))
        if type(decoded) is m.ProtoOADealListReq:
            bounded_deal(decoded,self.bound)
            return StdlibCTraderTransport._send_bytes(self,frame)
        check_outbound_frame(frame)
        return StdlibCTraderTransport._send_bytes(self,frame)

    def request(self,q,*,timeout=None):
        if type(q) is not m.ProtoOADealListReq:
            return super().request(q,timeout=timeout)
        bounded_deal(q,self.bound)
        need(self.connected,"HISTORY_AUTHENTICATED_CONNECTION_REQUIRED")
        wait=.25-(self._clock()-self._last_rate_limited_request_send)
        if wait>0:
            time.sleep(wait)
        self._sequence+=1
        msg_id=f"mxm-{self._sequence:012d}"
        self._send_bytes(encode_envelope(q,msg_id))
        self._last_rate_limited_request_send=self._clock()
        deadline=self._clock()+float(timeout or self.response_timeout)
        while True:
            envelope=self.receive_envelope(deadline=deadline)
            if envelope.payloadType==ProtoHeartbeatEvent().payloadType:
                self.send_heartbeat()
                continue
            if str(getattr(envelope,"clientMsgId",""))==msg_id:
                return extract_payload(envelope)

def deal_windows():
    return [(lo,min(lo+WEEK,END)-1) for lo in range(START,END,WEEK)]

def split_window(lo,hi):
    if lo==hi:
        return []
    mid=(lo+hi)//2
    return [(lo,mid),(mid+1,hi)]

def selected_ids(roster,limit=TIMEFRAME_TRANCHE):
    """First tranche: round-robin broker categories, ascending ID, no returns."""
    groups=defaultdict(deque)
    for sid,row in sorted(roster.items()):
        if row["visible"] is True:
            groups[row["category"] if row["category"] is not None else -1].append(sid)
    selected=[]
    while len(selected)<limit and any(groups.values()):
        for category in sorted(groups):
            if groups[category] and len(selected)<limit:
                selected.append(groups[category].popleft())
    return selected

def encode(obj):
    return base64.b64encode(obj.SerializePartialToString()).decode("ascii")

def decode(name,value):
    cls=getattr(m,name,None)
    if cls is None:
        from .ctrader_proto import OpenApiCommonMessages_pb2 as common
        cls=getattr(common,name,None)
    need(cls is not None,"HISTORY_UNKNOWN_MESSAGE_CLASS")
    q=cls()
    q.ParseFromString(base64.b64decode(value,validate=True))
    return q

class Journal:
    def __init__(self,transport,account):
        self.t=transport
        self.account=account
        self.packets=[]
        self.deadline=time.monotonic()+540
        self.halted=False

    def query(self,q):
        if self.halted or len(self.packets)>=MAX_REQUESTS or time.monotonic()>=self.deadline:
            return None,None,UNCOLLECTED
        if type(q) is m.ProtoOADealListReq:
            bounded_deal(q,self.account)
        else:
            require_read_only_request(q)
        need(q.ctidTraderAccountId==self.account,"HISTORY_REQUEST_ACCOUNT")
        # Same conservative limit even for nonhistorical requests.
        time.sleep(.25)
        rec=dict(reqType=type(q).__name__,req=encode(q),requestAt=time.time_ns()//1000000)
        response=None
        try:
            need(self.t.connected,"HISTORY_CONNECTION_LOST")
            response=self.t.request(q)
            rec.update(resType=type(response).__name__,res=encode(response),
                       availableAt=time.time_ns()//1000000)
            status=ATTEMPTED
        except Exception as exc:
            rec.update(resType=None,res=None,availableAt=time.time_ns()//1000000,
                       localFailure=type(exc).__name__)
            self.halted=True
            status=NO_RESPONSE
        self.packets.append(rec)
        return response,rec["availableAt"],status

class ReadbackJournal:
    def __init__(self,packets):
        self.packets=packets
        self.index=0
        self.halted=False

    def query(self,q):
        if self.halted or self.index==len(self.packets):
            return None,None,UNCOLLECTED
        rec=self.packets[self.index]
        self.index+=1
        need(rec["reqType"]==type(q).__name__ and rec["req"]==encode(q)
             and 0<rec["requestAt"]<=rec["availableAt"],"HISTORY_READBACK_REQUEST_OR_CLOCK")
        if rec["res"] is None:
            self.halted=True
            return None,rec["availableAt"],NO_RESPONSE
        return decode(rec["resType"],rec["res"]),rec["availableAt"],ATTEMPTED

def packet_summary(packets):
    # Public transport evidence only; never expose account IDs, raw deals,
    # labels, comments, monetary amounts or arbitrary provider error text.
    output=[]
    known_codes=set(model.ProtoOAErrorCode.keys())
    expected={"ProtoOATraderReq":"ProtoOATraderRes",
        "ProtoOAAssetListReq":"ProtoOAAssetListRes",
        "ProtoOADealListReq":"ProtoOADealListRes",
        "ProtoOASymbolsListReq":"ProtoOASymbolsListRes",
        "ProtoOASymbolByIdReq":"ProtoOASymbolByIdRes",
        "ProtoOAExpectedMarginReq":"ProtoOAExpectedMarginRes",
        "ProtoOAGetTrendbarsReq":"ProtoOAGetTrendbarsRes"}
    for index,rec in enumerate(packets,1):
        q=decode(rec["reqType"],rec["req"])
        r=decode(rec["resType"],rec["res"]) if rec["res"] is not None else None
        details={}
        for name in ("fromTimestamp","toTimestamp","period","maxRows"):
            if name in q.DESCRIPTOR.fields_by_name and q.HasField(name):
                details[name]=getattr(q,name)
        if "symbolId" in q.DESCRIPTOR.fields_by_name:
            value=q.symbolId
            details["symbolId"]=value if isinstance(value,int) else list(value)
        code=getattr(r,"errorCode",None)
        row=dict(sequence=index,requestType=rec["reqType"],responseType=rec["resType"],
                 requestAt=rec["requestAt"],availableAt=rec["availableAt"],scope=details,
                 requestSha256=digest(base64.b64decode(rec["req"])),
                 responseSha256=digest(base64.b64decode(rec["res"])) if r is not None else None,
                 expectedResponse=(rec["resType"]==expected.get(rec["reqType"]) and r is not None
                    and r.IsInitialized() and getattr(r,"ctidTraderAccountId",None)==q.ctidTraderAccountId),
                 providerErrorCode=code if code in known_codes else None,
                 otherProviderErrorCodeSha256=digest(str(code).encode()) if code and code not in known_codes else None)
        output.append(row)
    return output

def matching(r,cls,account):
    return type(r) is cls and r.IsInitialized() and r.ctidTraderAccountId==account

def classify(status,valid):
    return VERIFIED if valid else status

def field(obj,name):
    return getattr(obj,name) if obj.HasField(name) else None

def collect(j,account):
    public={"scope":{"dealStartInclusive":START,"dealEndExclusive":END,
                     "timeframeProbeStartInclusive":PROBE_START,"timeframeProbeEndExclusive":END,
                     "timeframeTrancheSize":TIMEFRAME_TRANCHE,"allSupportedTimeframes":list(ALL_PERIODS)},
            "contractRoster":[], "dealWindows":[], "historyTariffStatus":UNCOLLECTED,
            "historicalTariffContinuityCertified":False, "usableFundingOffers":0,
            "economicEvaluations":0,"ordersSubmitted":0,"cloudActivated":False}
    trader,_,st=j.query(m.ProtoOATraderReq(ctidTraderAccountId=account))
    assets,_,ast=j.query(m.ProtoOAAssetListReq(ctidTraderAccountId=account))
    if not (matching(trader,m.ProtoOATraderRes,account) and matching(assets,m.ProtoOAAssetListRes,account)
        and trader.trader.HasField("brokerName") and "pepperstone" in trader.trader.brokerName.casefold()
        and {a.assetId:a.name for a in assets.asset}.get(trader.trader.depositAssetId)=="EUR"):
        public["sourceBindingVerified"]=False
        public["bindingQueryStates"]=[st,ast]
        return public
    public["sourceBindingVerified"]=True

    # Account execution history is distinct from market-wide historical tariffs.
    queue=deque(deal_windows())
    terminal=[]
    deals=set()
    request_count=0
    while queue:
        lo,hi=queue.popleft()
        if request_count>=MAX_DEAL_QUERIES:
            public["dealWindows"].append(dict(start=lo,end=hi,status=UNCOLLECTED))
            continue
        q=m.ProtoOADealListReq(ctidTraderAccountId=account,fromTimestamp=lo,toTimestamp=hi,maxRows=MAX_ROWS)
        res,at,status=j.query(q)
        if status!=UNCOLLECTED:
            request_count+=1
        row=dict(start=lo,end=hi,status=status,availableAt=at)
        if matching(res,m.ProtoOADealListRes,account):
            row.update(rows=len(res.deal),hasMore=res.hasMore)
            children=split_window(lo,hi)
            if res.hasMore and children:
                queue.extendleft(reversed(children))
                row["split"]=True
            elif not res.hasMore:
                ids=[d.dealId for d in res.deal]
                # Provider may filter on creation or execution clock: do not
                # certify if neither timestamp matches the requested window.
                valid=(len(ids)==len(set(ids)) and not deals.intersection(ids)
                       and all(lo<=d.createTimestamp<=hi or lo<=d.executionTimestamp<=hi for d in res.deal))
                if valid:
                    deals.update(ids)
                    terminal.append((lo,hi))
                    closes=[d.closePositionDetail for d in res.deal if d.HasField("closePositionDetail")]
                    row.update(status=VERIFIED,closedDeals=len(closes),
                               explicitSwapMoneyDigits=sum(c.HasField("moneyDigits") for c in closes),
                               nonzeroSwapDeals=sum(c.swap!=0 for c in closes))
        public["dealWindows"].append(row)
    public["dealSummary"]=dict(uniqueDeals=len(deals),coveredMilliseconds=sum(b-a+1 for a,b in terminal),
        requestedMilliseconds=END-START,successfulTerminalWindows=len(terminal),
        closedDeals=sum(w.get("closedDeals",0) for w in public["dealWindows"]),
        explicitSwapMoneyDigits=sum(w.get("explicitSwapMoneyDigits",0) for w in public["dealWindows"]),
        nonzeroSwapDeals=sum(w.get("nonzeroSwapDeals",0) for w in public["dealWindows"]),
        transferableToHypotheticalModelPositions=False)

    listing,at,status=j.query(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False))
    public["rosterStatus"]=status
    if not matching(listing,m.ProtoOASymbolsListRes,account):
        return public
    ids=[s.symbolId for s in listing.symbol]
    if not ids or len(ids)!=len(set(ids)):
        return public
    public["rosterStatus"]=VERIFIED
    public["rosterAvailableAt"]=at
    roster={s.symbolId:dict(symbolId=s.symbolId,name=field(s,"symbolName"),visible=field(s,"enabled"),
                             category=field(s,"symbolCategoryId"),contractStatus=UNCOLLECTED,
                             marginStatus=UNCOLLECTED,financialEligibility="NOT_CERTIFIED",
                             timeframeStatus={p:UNCOLLECTED for p in ALL_PERIODS})
            for s in listing.symbol}
    contracts={}
    # All nonarchived roster entries are considered; visibility is not an
    # economic exclusion. Missing contracts stay attempted or uncollected.
    for start in range(0,len(ids),CONTRACT_BATCH):
        batch=sorted(ids)[start:start+CONTRACT_BATCH]
        res,at,status=j.query(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=batch))
        for sid in batch:
            roster[sid]["contractStatus"]=status
        if not matching(res,m.ProtoOASymbolByIdRes,account):
            continue
        got=[c.symbolId for c in res.symbol]
        if len(got)!=len(set(got)) or not set(got)<=set(batch):
            continue
        for c in res.symbol:
            contracts[c.symbolId]=c
            row=roster[c.symbolId]
            row.update(contractStatus=VERIFIED,contractAvailableAt=at,
                       tradingMode=field(c,"tradingMode"),minVolume=field(c,"minVolume"),
                       swapFieldsPresent=[k for k in SWAP_FIELDS if c.HasField(k)])
    selected=selected_ids(roster)
    public["timeframeProbeIds"]=selected
    for sid in selected:
        row=roster[sid]
        c=contracts.get(sid)
        if c is not None and c.HasField("minVolume") and c.minVolume>0:
            res,at,status=j.query(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                                    symbolId=sid,volume=[c.minVolume]))
            row["marginStatus"]=status
            if matching(res,m.ProtoOAExpectedMarginRes,account) and res.HasField("moneyDigits") and len(res.margin)==1:
                margin=res.margin[0]
                if margin.volume==c.minVolume and 0<=res.moneyDigits<=12 and min(margin.buyMargin,margin.sellMargin)>=0:
                    row.update(marginStatus=VERIFIED,marginAvailableAt=at,marginMoneyDigits=res.moneyDigits,
                               buyMarginRaw=margin.buyMargin,sellMarginRaw=margin.sellMargin)
        for period,minutes in PERIODS.items():
            res,at,status=j.query(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=sid,
                                     period=getattr(model,period),fromTimestamp=PROBE_START,toTimestamp=END-1))
            row["timeframeStatus"][period]=status
            if not matching(res,m.ProtoOAGetTrendbarsRes,account) or res.period!=getattr(model,period) or (res.HasField("symbolId") and res.symbolId!=sid):
                continue
            try:
                bars=decode_bars(res.trendbar,PROBE_START,END-1,minutes)
            except Exception:
                continue
            # Empty/partial response is an authentic attempt, not proof of
            # general unavailability or full history coverage.
            row.setdefault("timeframeEvidence",{})[period]=dict(
                availableAt=at,closedBars=len(bars),firstOpen=bars[0][0] if bars else None,
                lastClose=bars[-1][1] if bars else None,hasMore=field(res,"hasMore"),
                wholeHistoryCertified=False)
            if bars and not (res.HasField("hasMore") and res.hasMore):
                row["timeframeStatus"][period]=VERIFIED
    public["contractRoster"]=[roster[sid] for sid in sorted(roster)]
    public["inventorySummary"]=dict(roster=len(roster),
        visible=sum(row["visible"] is True for row in roster.values()),
        contracts=dict(Counter(row["contractStatus"] for row in roster.values())),
        margins=dict(Counter(row["marginStatus"] for row in roster.values())),
        timeframes={p:dict(Counter(row["timeframeStatus"][p] for row in roster.values())) for p in ALL_PERIODS},
        globalUniverseRestricted=False)
    return public

def source_main():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_REF")=="refs/heads/main"
         and os.environ.get("GITHUB_RUN_ATTEMPT")=="1" and MARKER_PATH.read_text()==MARKER+"\n",
         "HISTORY_SOURCE_NOT_AUTHORIZED")
    rid=os.environ.get("GITHUB_RUN_ID","")
    recipient=checked_public(Path("new-source-recipient"),rid)
    t=SourceHistoryTransport(response_timeout=15)
    try:
        account=authenticate(t)
        t.bind(account)
        j=Journal(t,account)
        report=collect(j,account)
        report["runId"]=rid
        report["requestCount"]=len(j.packets)
        report["responsesReceived"]=sum(p["res"] is not None for p in j.packets)
        report["responseMissingCount"]=sum(p["res"] is None for p in j.packets)
        report["requestJournal"]=packet_summary(j.packets)
        report["unexpectedOrMissingResponses"]=sum(not p["expectedResponse"] for p in report["requestJournal"])
        raw=canonical(dict(runId=rid,packets=j.packets,report=report))
        cipher=seal_new(raw,recipient,rid)
        OUT.mkdir(exist_ok=False)
        (OUT/"original.sealed").write_bytes(cipher)
        (OUT/"receipt.json").write_bytes(canonical(dict(report,originalSha256=digest(raw),
            ciphertextSha256=digest(cipher)))+b"\n")
        print("HISTORY_SOURCE_RECEIPT_EMITTED",flush=True)
        need(report["sourceBindingVerified"],"HISTORY_SOURCE_BINDING_NOT_VERIFIED")
    finally:
        t.close()

def readback_main():
    rid=os.environ.get("GITHUB_RUN_ID","")
    receipt=json.loads((OUT/"receipt.json").read_text())
    cipher=(OUT/"original.sealed").read_bytes()
    need(receipt["runId"]==rid and receipt["ciphertextSha256"]==digest(cipher),"HISTORY_READBACK_CIPHER")
    raw=unseal_new(cipher,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),rid)
    need(receipt["originalSha256"]==digest(raw),"HISTORY_READBACK_PLAINTEXT")
    original=json.loads(raw)
    packets=original["packets"]
    need(bool(packets) and original["runId"]==rid,"HISTORY_READBACK_BINDING")
    q=decode(packets[0]["reqType"],packets[0]["req"])
    account=q.ctidTraderAccountId
    need(original_account(account),"HISTORY_READBACK_ORIGINAL_ACCOUNT")
    j=ReadbackJournal(packets)
    report=collect(j,account)
    report.update(runId=rid,requestCount=len(packets),
                  responsesReceived=sum(p["res"] is not None for p in packets),
                  responseMissingCount=sum(p["res"] is None for p in packets))
    report["requestJournal"]=packet_summary(packets)
    report["unexpectedOrMissingResponses"]=sum(not p["expectedResponse"] for p in report["requestJournal"])
    need(j.index==len(packets) and report==original["report"] and
         receipt==dict(report,originalSha256=digest(raw),ciphertextSha256=digest(cipher)),
         "HISTORY_READBACK_REPORT_MISMATCH")
    Path("source-history-readback.json").write_bytes(canonical(dict(runId=rid,
        ciphertextSha256=digest(cipher),originalSha256=digest(raw),receiptSha256=digest((OUT/"receipt.json").read_bytes()),
        requestCount=len(packets),fullRawReadbackMatched=True,
        historicalTariffContinuityCertified=False,economicEvaluations=0,ordersSubmitted=0,cloudActivated=False))+b"\n")

if __name__=="__main__":
    try:
        if sys.argv[1:]==["--readback"]:
            readback_main()
        elif not sys.argv[1:]:
            source_main()
        else:
            raise ValueError("HISTORY_MODE")
    except Exception:
        print("HISTORY_SOURCE_OR_READBACK_FAILED_DETAIL_WITHHELD",flush=True)
        sys.exit(1)

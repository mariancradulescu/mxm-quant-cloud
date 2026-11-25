"""Official Open API evidence for the native EUR book and contract chronology."""
from collections import Counter, defaultdict
from decimal import Decimal
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import owner_source_history_use as history
from . import source_history_universe as source
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as model
from .ctrader_transport import (StdlibCTraderTransport, ProtoHeartbeatEvent, HEARTBEAT_IDLE_SECONDS,
    MAX_FRAME_BYTES, TransportError, decode_envelope, extract_payload, encode_envelope)
from .p05_safe_transport import P05ReadOnlyTransport
from .owner_readonly_auth import authenticate
from .decode import CaptureContractError, need
from .custody import seal_new, unseal_new
from .custody_new import checked_public

OUT = Path("official-eur")
ORIGINAL = Path("original-source-history")
STEP = 300_000
MINUTE = 60_000
PROBE_MARKETS = 12
FRAMES = 5
OBSERVE_OFFSET = 45_000
EXTRA = {c: r for c, r in (
    (m.ProtoOAVersionReq, m.ProtoOAVersionRes),
    (m.ProtoOAAssetClassListReq, m.ProtoOAAssetClassListRes),
    (m.ProtoOASymbolCategoryListReq, m.ProtoOASymbolCategoryListRes),
    (m.ProtoOASymbolsForConversionReq, m.ProtoOASymbolsForConversionRes),
    (m.ProtoOASubscribeSpotsReq, m.ProtoOASubscribeSpotsRes),
)}


def now_ms():
    return time.time_ns() // 1_000_000


class OfficialEvidenceTransport(P05ReadOnlyTransport):
    """Add documented account-bound reads to the existing socket guard."""
    def __init__(self):
        super().__init__(response_timeout=15)
        self.bound = None
        self.journal = []
        self.spots = []
        self.changes = []
        self.pending_changes = set()
        self.interrupted = False
        self.watch_ids = set()
        self.incoming = bytearray()

    def bind(self, account):
        need(self.bound is None and source.original_account(account), "OFFICIAL_ACCOUNT_BINDING")
        self.bound = account

    def validate_extra(self, request):
        need(self.bound is not None and request.IsInitialized()
             and request.payloadType == type(request)().payloadType, "OFFICIAL_EXTRA_READ_SCOPE")
        if type(request) is not m.ProtoOAVersionReq:
            need(request.ctidTraderAccountId == self.bound, "OFFICIAL_EXTRA_ACCOUNT")
        if type(request) is m.ProtoOASubscribeSpotsReq:
            need(0 < len(request.symbolId) <= 48 and set(request.symbolId) <= self.watch_ids
                 and request.subscribeToSpotTimestamp, "OFFICIAL_SPOT_SCOPE")

    def _send_bytes(self, frame):
        if isinstance(frame, bytes) and len(frame) > 4 and len(frame) <= MAX_FRAME_BYTES+4:
            if struct.unpack("!I", frame[:4])[0] == len(frame)-4:
                message = extract_payload(decode_envelope(frame[4:]))
                if type(message) in EXTRA:
                    self.validate_extra(message)
                    return StdlibCTraderTransport._send_bytes(self, frame)
        return super()._send_bytes(frame)

    def receive_envelope(self, *, deadline):
        # Retain incomplete bytes across quiet observation deadlines.
        sock=self._require_connected()
        while True:
            if len(self.incoming)>=4:
                size=struct.unpack_from("!I",self.incoming)[0]
                if not 0<size<=MAX_FRAME_BYTES:
                    raise TransportError("OFFICIAL_INVALID_INCOMING_FRAME")
                if len(self.incoming)>=size+4:
                    envelope=decode_envelope(bytes(self.incoming[4:size+4]))
                    del self.incoming[:size+4]
                    break
            left=deadline-self._clock()
            if left<=0:
                raise TimeoutError("OFFICIAL_OBSERVATION_TIMEOUT")
            if self._clock()-self._last_send>=HEARTBEAT_IDLE_SECONDS:
                self.send_heartbeat()
            sock.settimeout(min(1.,left))
            try:
                block=sock.recv(65_536)
            except socket.timeout:
                continue
            except OSError:
                raise TransportError("OFFICIAL_SESSION_RECEIVE_INTERRUPTED") from None
            if not block:
                raise TransportError("OFFICIAL_SESSION_CLOSED")
            self.incoming.extend(block)
        at = now_ms()
        def is_type(cls):
            return envelope.payloadType == cls().payloadType
        if is_type(m.ProtoOASpotEvent) and self.bound is not None:
            spot = extract_payload(envelope)
            if spot.IsInitialized() and spot.ctidTraderAccountId == self.bound and spot.symbolId in self.watch_ids:
                if len(self.spots) >= 275_000:
                    raise TransportError("OFFICIAL_SPOT_CAPTURE_CAP")
                self.spots.append([at, source.encode(spot)])
        elif is_type(m.ProtoOASymbolChangedEvent) and self.bound is not None:
            event = extract_payload(envelope)
            if event.IsInitialized() and event.ctidTraderAccountId == self.bound:
                self.changes.append([at, source.encode(event)])
                self.pending_changes.update(event.symbolId)
        elif any(is_type(cls) for cls in (m.ProtoOAAccountDisconnectEvent,
                m.ProtoOAClientDisconnectEvent, m.ProtoOAAccountsTokenInvalidatedEvent)):
            self.interrupted = True
            raise TransportError("OFFICIAL_SESSION_INTERRUPTED")
        return envelope

    def request(self, request, *, timeout=None):
        if type(request) not in EXTRA:
            return super().request(request, timeout=timeout)
        self.validate_extra(request)
        need(self.connected, "OFFICIAL_AUTH_REQUIRED")
        delay = .21-(self._clock()-self._last_rate_limited_request_send)
        if delay > 0:
            time.sleep(delay)
        self._sequence += 1
        token = f"mxm-{self._sequence:012d}"
        self._send_bytes(encode_envelope(request, token))
        self._last_rate_limited_request_send = self._clock()
        deadline = self._clock()+float(timeout or self.response_timeout)
        while True:
            envelope = self.receive_envelope(deadline=deadline)
            if envelope.payloadType == ProtoHeartbeatEvent().payloadType:
                self.send_heartbeat()
            elif getattr(envelope, "clientMsgId", None) == token:
                return extract_payload(envelope)

    def read(self, request, expected, tag):
        need(self.connected and (type(request) is m.ProtoOAVersionReq
             or request.ctidTraderAccountId == self.bound), "OFFICIAL_READ_ACCOUNT")
        sent = now_ms()
        result = self.request(request)
        at = now_ms()
        ok = type(result) is expected and result.IsInitialized() and (
            isinstance(result, m.ProtoOAVersionRes) or result.ctidTraderAccountId == self.bound)
        self.journal.append(dict(tag=tag, reqType=type(request).__name__, req=source.encode(request),
            resType=type(result).__name__, res=source.encode(result), sent=sent, at=at, verified=ok))
        return result if ok else None

    def observe_until(self, at, refresh=True):
        while now_ms() < at:
            if refresh and self.pending_changes:
                ids = sorted(self.pending_changes)
                self.pending_changes.clear()
                for first in range(0, len(ids), 50):
                    self.read(m.ProtoOASymbolByIdReq(ctidTraderAccountId=self.bound,
                        symbolId=ids[first:first+50]), m.ProtoOASymbolByIdRes, "change-refresh")
            try:
                left = min(1.0, max(0.0, (at-now_ms())/1000))
                envelope = self.receive_envelope(deadline=self._clock()+left)
            except TimeoutError:
                continue
            if envelope.payloadType == ProtoHeartbeatEvent().payloadType:
                self.send_heartbeat()


def public_original():
    raw = (ORIGINAL/"receipt.json").read_bytes()
    need(source.digest(raw) == history.RECEIPT_SHA, "OFFICIAL_ROSTER_RECEIPT")
    return json.loads(raw)


def select_market_rows(receipt, categories):
    roster = {r["symbolId"]: r for r in receipt["contractRoster"]}
    rows = [roster[i] for i in receipt["timeframeProbeIds"]]
    groups = defaultdict(list)
    for row in rows:
        if row.get("marginStatus") != source.VERIFIED or row["tradingMode"] != 0:
            continue
        margin = Decimal(max(row["buyMarginRaw"],row["sellMarginRaw"])).scaleb(-row["marginMoneyDigits"])
        if 0 < margin <= 210:
            cat = row["category"]
            group=categories.get(cat, ("UNMAPPED",cat))[1]
            groups[group].append((margin,row["symbolId"],row))
    for value in groups.values():
        value.sort(key=lambda x:(x[0],x[1]))
    selected=[]
    while len(selected)<PROBE_MARKETS and any(groups.values()):
        for group in sorted(groups,key=str):
            if groups[group] and len(selected)<PROBE_MARKETS:
                selected.append(groups[group].pop(0)[2])
    return selected


def quoted_volumes(contract):
    if contract.minVolume <= 0 or contract.stepVolume <= 0 or contract.maxVolume < contract.minVolume:
        return []
    minimum, step = contract.minVolume, contract.stepVolume
    # The smallest opening size that can split into two legal fragments.
    return [minimum, 2*minimum] if minimum % step==0 and 2*minimum<=contract.maxVolume else [minimum]


def read_bars(t, symbol, period, lo, hi, tag):
    enum=model.ProtoOATrendbarPeriod.Value(period)
    width=source.PERIODS[period]*MINUTE
    for start in range(lo,hi,900*width):
        end=min(hi,start+900*width)
        t.read(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=t.bound,symbolId=symbol,period=enum,
            fromTimestamp=start,toTimestamp=end-1),m.ProtoOAGetTrendbarsRes,tag)


def capture():
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and os.environ.get("GITHUB_REF")=="refs/heads/main"
         and os.environ.get("GITHUB_RUN_ATTEMPT")=="1", "OFFICIAL_EUR_OWNER_RUN_CONTEXT")
    rid=os.environ["GITHUB_RUN_ID"]
    receiver=checked_public(Path("official-recipient"),rid)
    original=public_original()
    t=OfficialEvidenceTransport()
    boundaries=[]
    begin=stream_start=None
    ids=[]
    version=None
    interruption=None
    try:
        account=authenticate(t)
        t.bind(account)
        begin=now_ms()
        version=t.read(m.ProtoOAVersionReq(),m.ProtoOAVersionRes,"version")
        trader=t.read(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes,"trader")
        assets=t.read(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes,"assets")
        listing=t.read(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes,"light-roster")
        classes=t.read(m.ProtoOAAssetClassListReq(ctidTraderAccountId=account),m.ProtoOAAssetClassListRes,"classes")
        category_rows=t.read(m.ProtoOASymbolCategoryListReq(ctidTraderAccountId=account),
            m.ProtoOASymbolCategoryListRes,"categories")
        codes={a.assetId:a.name for a in assets.asset}
        need("pepperstone" in trader.trader.brokerName.lower() and
             codes.get(trader.trader.depositAssetId)=="EUR","OFFICIAL_EUR_TRADER")
        categories={c.id:(c.name,c.assetClassId) for c in category_rows.symbolCategory}
        selected=select_market_rows(original,categories)
        ids=sorted(row["symbolId"] for row in selected)
        need(len(ids)>=2,"OFFICIAL_EUR_MULTI_ASSET_SCOPE")
        lights={s.symbolId:s for s in listing.symbol}
        usd=next(i for i,n in codes.items() if n=="USD")
        current=t.read(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=ids),
            m.ProtoOASymbolByIdRes,"initial-terms")
        contracts={x.symbolId:x for x in current.symbol}
        needed_assets={usd}|{lights[sid].quoteAssetId for sid in contracts}
        needed_assets|={i for i,n in codes.items() if n in {c.minCommissionAsset for c in contracts.values()}}
        for asset in sorted(needed_assets-{trader.trader.depositAssetId}):
            chain=t.read(m.ProtoOASymbolsForConversionReq(ctidTraderAccountId=account,firstAssetId=asset,
                lastAssetId=trader.trader.depositAssetId),m.ProtoOASymbolsForConversionRes,"conversion-route")
            if chain is not None:
                t.watch_ids.update(row.symbolId for row in chain.symbol)
        for level in sorted({c.leverageId for c in contracts.values() if c.HasField("leverageId") and c.leverageId>0}):
            t.read(m.ProtoOAGetDynamicLeverageByIDReq(ctidTraderAccountId=account,leverageId=level),
                m.ProtoOAGetDynamicLeverageByIDRes,"leverage")

        # Requests start at the boundary of the previous capture. Prior bars
        # remain the warmup for its covered period, with no recollection.
        history_start=source.END
        t.watch_ids.update(ids)
        response=t.read(m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=account,
            symbolId=sorted(t.watch_ids),subscribeToSpotTimestamp=True),m.ProtoOASubscribeSpotsRes,"spot-subscription")
        need(response is not None,"OFFICIAL_TIMESTAMPED_STREAM")
        stream_start=now_ms()
        first=(stream_start//STEP+1)*STEP+OBSERVE_OFFSET
        last_requested={}
        for index in range(FRAMES):
            at=first+index*STEP
            boundary=at-OBSERVE_OFFSET
            t.observe_until(boundary+1000)
            for sid in ids:
                for period in ("M5","M15"):
                    width=source.PERIODS[period]*MINUTE
                    lo=last_requested.get((sid,period),history_start)
                    hi=boundary//width*width
                    if hi>lo:
                        last_requested[(sid,period)]=hi
                        read_bars(t,sid,period,lo,hi,f"session-bars-{index}")
            snapshots=t.read(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=ids),
                m.ProtoOASymbolByIdRes,f"frame-terms-{index}")
            for contract in (snapshots.symbol if snapshots is not None else ()):
                volumes=quoted_volumes(contract)
                if volumes:
                    t.read(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=contract.symbolId,
                        volume=volumes),m.ProtoOAExpectedMarginRes,f"frame-margin-{index}")
            t.observe_until(at)
            boundaries.append(at)
            print("OFFICIAL_EUR_CLOCKS_OBSERVED",len(boundaries),"/",FRAMES,flush=True)
        # Collect additional missing lower timeframes for the selected
        # instruments on the common period after the last historical tranche.
        for sid in ids:
            for period in ("M1","M30","H1","H4","D1"):
                width=source.PERIODS[period]*MINUTE
                hi=boundaries[-1]//width*width
                if hi>history_start:
                    read_bars(t,sid,period,history_start,hi,"history-extension")
    except (TransportError, TimeoutError, CaptureContractError) as error:
        if begin is None:
            raise
        t.interrupted=True
        interruption=safe_reason(error)
    finally:
        t.close()
    end=now_ms()
    stream_end=boundaries[-1] if boundaries else None
    payload=dict(runId=rid,accountBound=True,currency="EUR",selected=ids,streamStart=stream_start,
        streamEnd=stream_end,captureStart=begin,captureEnd=end,interrupted=t.interrupted,
        frames=boundaries,requests=t.journal,spots=t.spots,changes=t.changes)
    report=dict(runId=rid,openApiVersion=version.version if version is not None else None,
        authenticatedAccountCurrency="EUR",selected=len(ids),frames=len(boundaries),
        officialRequests=len(t.journal),officialResponses=len(t.journal),
        expectedResponses=sum(p["verified"] for p in t.journal),
        spotMessages=len(t.spots),contractChangeNotices=len(t.changes),
        streamObservation=[stream_start,stream_end],interrupted=t.interrupted,interruption=interruption,
        historicalSwapContinuityCertified=False,ordersSubmitted=0,cloudActivated=False)
    OUT.mkdir(exist_ok=False)
    clear=source.canonical(payload)
    sealed=seal_new(clear,receiver,rid)
    (OUT/"original.sealed").write_bytes(sealed)
    report.update(plaintextSha256=source.digest(clear),ciphertextSha256=source.digest(sealed))
    (OUT/"receipt.json").write_bytes(source.canonical(report)+b"\n")
    print("OFFICIAL_EUR_SEALED",report["expectedResponses"],report["frames"],
          interruption or "COMPLETE",flush=True)


def unpack_original(folder,key,run):
    receipt=json.loads((folder/"receipt.json").read_text())
    cipher=(folder/"original.sealed").read_bytes()
    need(receipt["runId"]==run and receipt["ciphertextSha256"]==source.digest(cipher),
         "OFFICIAL_EUR_CIPHERTEXT")
    clear=unseal_new(cipher,key,run)
    original=json.loads(clear)
    need(receipt["plaintextSha256"]==source.digest(clear) and original["runId"]==run and
         len(original["requests"])==receipt["officialRequests"] and len(original["spots"])==receipt["spotMessages"],
         "OFFICIAL_EUR_PLAINTEXT")
    return original,receipt


def decoded_packets(original):
    bound=None
    for row in original["requests"]:
        request=source.decode(row["reqType"],row["req"])
        reply=source.decode(row["resType"],row["res"])
        need(0 < row["sent"] <= row["at"],"OFFICIAL_EUR_REQUEST_CLOCK")
        if hasattr(request,"ctidTraderAccountId"):
            account=request.ctidTraderAccountId
            if bound is None:
                need(source.original_account(account),"OFFICIAL_EUR_ACCOUNT")
                bound=account
            need(account==bound and (not row["verified"] or reply.ctidTraderAccountId==bound),
                 "OFFICIAL_EUR_RESPONSE_ACCOUNT")
        if row["verified"]:
            need(reply.IsInitialized(),"OFFICIAL_EUR_RESPONSE_INCOMPLETE")
            yield row,request,reply


def terms_input(contract, symbol, asset, at):
    terms=history.fields_of(contract)
    kind,value,unknown=history.calculation_type(contract)
    required=("minVolume","maxVolume","stepVolume","lotSize","commissionType",
        "preciseTradingCommissionRate","minCommissionType","preciseMinCommission","pnlConversionFeeRate")
    if asset is None or not all(k in terms for k in required):
        return None
    raw_units=lambda k:str(Decimal(terms[k]).scaleb(-2))
    result=dict(Symbol=symbol,QuoteAsset=asset,ObservedAtUtcMs=at,MinimumUnits=raw_units("minVolume"),
        VolumeStepUnits=raw_units("stepVolume"),MaximumUnits=raw_units("maxVolume"),LotUnits=raw_units("lotSize"),
        CommissionType=terms["commissionType"],PreciseRateWire=terms["preciseTradingCommissionRate"],
        MinimumCommissionType=terms["minCommissionType"],PreciseMinimumWire=terms["preciseMinCommission"],
        MinimumCommissionAsset=terms.get("minCommissionAsset"),PnlConversionFeeBps=terms["pnlConversionFeeRate"],
        SwapCalculationType=value,LongSwap=terms.get("swapLong"),ShortSwap=terms.get("swapShort"),
        PipPosition=terms.get("pipPosition"),SwapPeriodHours=terms.get("swapPeriod"),
        SwapTimeUtcMinute=terms.get("swapTime"),TripleSwapWeekday=terms.get("swapRollover3Days"),
        ChargeSwapAtWeekends=terms.get("chargeSwapAtWeekends"),SkipSwapPeriods=terms.get("skipSWAPPeriods"),
        OriginalBrokerAuthenticated=True,HistoricalTariffContinuityCertified=False)
    return result,terms,kind,unknown


def next_scheduled_witness(contract, at):
    try:
        zone=ZoneInfo(contract["scheduleTimeZone"])
        start=datetime.fromtimestamp(at/1000,timezone.utc)
        end=datetime.fromtimestamp((at+STEP)/1000,timezone.utc)
        for holiday in contract.get("holiday",[]):
            day=date(1970,1,1)+timedelta(days=holiday["holidayDate"])
            hzone=ZoneInfo(holiday["scheduleTimeZone"])
            first=start.astimezone(hzone).date()-timedelta(days=1)
            last=end.astimezone(hzone).date()
            for offset in range((last-first).days+1):
                current=first+timedelta(days=offset)
                if current!=day and not (holiday["isRecurring"] and
                        (current.month,current.day)==(day.month,day.day)):
                    continue
                beginning=holiday.get("startSecond",0)
                finish=holiday.get("endSecond",86400)
                if not 0<=beginning<finish<=86400:
                    return None
                midnight=datetime.combine(current,datetime.min.time(),hzone)
                if midnight+timedelta(seconds=beginning)<=end and midnight+timedelta(seconds=finish)>start:
                    return None
    except (KeyError, ZoneInfoNotFoundError, ValueError, OverflowError):
        return None
    def week_second(clock):
        d=clock.astimezone(zone)
        return ((d.weekday()+1)%7)*86400+d.hour*3600+d.minute*60+d.second
    a,b=week_second(start),week_second(end)
    if a<=b and any(s["startSecond"]<=a and b<s["endSecond"] for s in contract.get("schedule",[])):
        return at+STEP
    return None


def extract_input(original):
    packets=list(decoded_packets(original))
    account=next(q.ctidTraderAccountId for _,q,_ in packets if hasattr(q,"ctidTraderAccountId"))
    trader=next(r.trader for _,_,r in packets if type(r) is m.ProtoOATraderRes)
    assets=next({x.assetId:x.name for x in r.asset} for _,_,r in packets if type(r) is m.ProtoOAAssetListRes)
    roster=next({x.symbolId:x for x in r.symbol} for _,_,r in packets if type(r) is m.ProtoOASymbolsListRes)
    need(assets.get(trader.depositAssetId)=="EUR" and source.original_account(account),"OFFICIAL_EUR_BINDING")
    categories=next({c.id:(c.name,c.assetClassId) for c in r.symbolCategory}
                    for _,_,r in packets if type(r) is m.ProtoOASymbolCategoryListRes)
    classes=next({c.id:c.name for c in r.assetClass if c.HasField("id") and c.HasField("name")}
                 for _,_,r in packets if type(r) is m.ProtoOAAssetClassListRes)
    fx={}
    changes=defaultdict(list)
    for at,encoded in original["changes"]:
        e=source.decode("ProtoOASymbolChangedEvent",encoded)
        need(e.ctidTraderAccountId==account and original["captureStart"]<=at<=original["captureEnd"],
             "OFFICIAL_EUR_EVENT_BINDING")
        for sid in e.symbolId:
            changes[sid].append(at)
    for row,q,r in packets:
        if type(q) is m.ProtoOASymbolsForConversionReq:
            fx[assets[q.firstAssetId]]=(row["at"],list(r.symbol))
    leases={q.leverageId:dict(observedAt=row["at"],tiers=[history.fields_of(t) for t in r.leverage.tiers])
            for row,q,r in packets if type(q) is m.ProtoOAGetDynamicLeverageByIDReq and r.leverage.leverageId==q.leverageId}
    refreshed=[(row["at"],c.symbolId,source.digest(c.SerializeToString())) for row,q,r in packets
               if row["tag"]=="change-refresh" for c in r.symbol if c.symbolId in q.symbolId]
    marks={}
    frames=[]
    spot_cursor=iter(original["spots"])
    next_spot=next(spot_cursor,None)
    tape={}
    diagnostics=Counter()
    for row,q,r in packets:
        if type(q) is not m.ProtoOAGetTrendbarsReq:
            continue
        series,accepted=history.inspect_bars(q,r,row["at"])
        period=model.ProtoOATrendbarPeriod.Name(q.period)
        diagnostics[period]+=len(accepted)
        name=roster[q.symbolId].symbolName
        values=tape.setdefault(name,{}).setdefault(period,{})
        for bar in accepted:
            need(bar[0] not in values or values[bar[0]][0]==bar,"OFFICIAL_EUR_BAR_CONFLICT")
            values.setdefault(bar[0],(bar,row["at"]))

    def currency_route(asset, at):
        if asset=="EUR":
            return []
        if asset not in fx or fx[asset][0]>at:
            return None
        current=asset
        hops=[]
        for pair in fx[asset][1]:
            base,quote=assets.get(pair.baseAssetId),assets.get(pair.quoteAssetId)
            mark=quote_at(pair.symbolId,at)
            if mark is None or base is None or quote is None or current not in (base,quote):
                return None
            bid,ask,witness=mark
            hops.append(dict(Symbol=pair.symbolName,BaseAsset=base,QuoteAsset=quote,AtUtcMs=witness,
                             Bid=bid,Ask=ask,OriginalBrokerAuthenticated=True))
            current=quote if current==base else base
        return hops if current=="EUR" else None

    def quote_at(sid, at):
        pair=marks.get(sid,{})
        if not all(k in pair for k in ("bid","ask")):
            return None
        bid,bid_at=pair["bid"]
        ask,ask_at=pair["ask"]
        older=min(bid_at,ask_at)
        if at-older>60_000 or ask<bid or bid<=0:
            return None
        return str(Decimal(bid).scaleb(-5)),str(Decimal(ask).scaleb(-5)),older

    for index,at in enumerate(original["frames"]):
        while next_spot is not None and next_spot[0]<=at:
            received,encoded=next_spot
            spot=source.decode("ProtoOASpotEvent",encoded)
            need(spot.ctidTraderAccountId==account,"OFFICIAL_EUR_SPOT_ACCOUNT")
            if spot.HasField("timestamp") and 0<spot.timestamp<=received:
                mark=marks.setdefault(spot.symbolId,{})
                for side in ("bid","ask"):
                    if spot.HasField(side) and (side not in mark or mark[side][1]<=spot.timestamp):
                        mark[side]=(getattr(spot,side),spot.timestamp)
            next_spot=next(spot_cursor,None)
        observed={c.symbolId:(row,c) for row,q,r in packets
                  if row["tag"]==f"frame-terms-{index}" and row["at"]<=at
                  for c in r.symbol if c.symbolId in q.symbolId}
        margin={q.symbolId:(row,q,r) for row,q,r in packets if row["tag"]==f"frame-margin-{index}" and row["at"]<=at}
        markets=[]
        for sid in original["selected"]:
            if sid not in observed or sid not in margin or quote_at(sid,at) is None:
                continue
            row,contract=observed[sid]
            if any(row["at"]<changed<=at for changed in changes[sid]):
                continue
            symbol=roster[sid].symbolName
            asset=assets.get(roster[sid].quoteAssetId)
            decoded=terms_input(contract,symbol,asset,row["at"])
            if decoded is None:
                continue
            terms,raw,_,_=decoded
            routes={a:currency_route(a,at) for a in {asset,"USD",raw.get("minCommissionAsset") or asset}}
            if routes[asset] is None:
                continue
            bid,ask,witness=quote_at(sid,at)
            margin_row,requested,measured=margin[sid]
            if not measured.HasField("moneyDigits") or not 0<=measured.moneyDigits<=12:
                continue
            margin_values=[]
            sha=source.digest(measured.SerializeToString())
            for entry in measured.margin:
                if entry.volume not in requested.volume:
                    continue
                volume=str(Decimal(entry.volume).scaleb(-2))
                for side,amount in ((1,entry.buyMargin),(-1,entry.sellMargin)):
                    if amount>0:
                        margin_values.append(dict(Side=side,Units=volume,
                            MarginEur=str(Decimal(amount).scaleb(-measured.moneyDigits)),
                            ObservedAt=margin_row["at"],SourceSha256=sha))
            bars={period:[bar for bar,available in sorted(values.values())
                  if available<=at and bar[1]<at][-count:]
                  for period,count in (("M5",5),("M15",3))
                  if (values:=tape.get(symbol,{}).get(period))}
            markets.append(dict(Contract=terms,Bid=bid,Ask=ask,QuoteAt=witness,Routes=routes,
                MinimumFeeAsset=raw.get("minCommissionAsset"),Margin=margin_values,Bars=bars,
                TradingMode=raw.get("tradingMode"),ShortAllowed=raw.get("enableShortSelling"),
                VerifiedManagementClock=next_scheduled_witness(raw,at),
                ContractSha256=source.digest(contract.SerializeToString()),
                LastContractChange=max((stamp for stamp in changes[sid] if stamp<=at),default=None),
                AccountSwapFree=source.field(trader,"swapFree"),LeverageId=raw.get("leverageId")))
        frames.append(dict(At=at,Markets=markets))
    inventory=dict(assetClasses=classes,categories=categories,leverage=leases,
        officialConversionChainAssets=sorted(fx),officialContractChangeCount=len(original["changes"]),
        refreshedContractPoints=[dict(at=at,symbolId=sid,sha256=sha) for at,sid,sha in refreshed],
        newClosedBarsByTimeframe=dict(diagnostics))
    return dict(Frames=frames,StreamStart=original["streamStart"],StreamEnd=original["streamEnd"],
        ContinuousSessionObserved=not original["interrupted"]), inventory, tape


def extension_history(key):
    from . import owner_source_history_expand as extension
    folder=Path("previous-extension")
    receipt=json.loads((folder/"receipt.json").read_text())
    cipher=(folder/"extension.sealed").read_bytes()
    run="45409527714"
    need(source.digest(cipher)=="569afdbf06d616c2927102fb4819981b987a2b9d020e7c9f033ce2845e6756c3",
         "OFFICIAL_EUR_PRIOR_EXTENSION_CIPHER")
    clear=unseal_new(cipher,key,run)
    need(source.digest(clear)=="f3f0147ba0ca60721cb0cc6645378bc79c8ae605058fb92fb99aa16a9b9cb944",
         "OFFICIAL_EUR_PRIOR_EXTENSION_PLAIN")
    previous=json.loads(clear)
    base,p05=extension.inputs()
    selection=extension.plan(base,p05)
    first=previous["packets"][0]
    account=source.decode(first["reqType"],first["req"]).ctidTraderAccountId
    need(source.original_account(account),"OFFICIAL_EUR_PRIOR_EXTENSION_ACCOUNT")
    journal=source.ReadbackJournal(previous["packets"])
    report,archive,margin=extension.collect(journal,account,selection,run)
    need(journal.index==len(previous["packets"]) and report==receipt["coverage"],
         "OFFICIAL_EUR_PRIOR_EXTENSION_JOURNAL")
    return archive, {r["name"]:margin.get(r["symbolId"]) for r in selection}


def observed_bar_span(period,values):
    if not values:
        return None
    width=source.PERIODS[period]*MINUTE
    stamps=sorted(values)
    first=stamps[0]
    intervals=[]
    for a,b in zip(stamps,stamps[1:]):
        if a+width!=b:
            intervals.append((first,a+width))
            first=b
    intervals.append((first,stamps[-1]+width))
    return dict(closedBars=len(stamps),fromOpen=stamps[0],throughClose=stamps[-1]+width,
        observedIntervals=intervals,internalClockBreaks=len(intervals)-1,
        officialHistoricalSessionsCertified=False)


def market_matrix(work,key,inventory,authenticated,today):
    from .v32_unified_source_adapter import execute
    coverage=defaultdict(lambda:defaultdict(set))
    def add(name,period,opens):
        coverage[name][period].update(opens)
    annual=work/"custody-v32-tape.json"
    proof=execute(annual)
    with annual.open() as data:
        transfer=json.load(data)
    for market in transfer["Markets"]:
        for period,rows in market["Bars"].items():
            add(market["Symbol"],period,(r["OpenAt"] for r in rows))
    del transfer
    annual.unlink()
    packets,receipt=history.verified_original(ORIGINAL,key)
    contracts,_,short=history.extract(packets,receipt)
    extended,estimated=extension_history(key)
    for archive in (short,extended):
        for market in archive["Markets"]:
            for period,rows in market["Bars"].items():
                add(market["Symbol"],period,(r[0] for r in rows))
    for name,series in today.items():
        for period,rows in series.items():
            add(name,period,rows.keys())

    category_names=inventory["categories"]
    class_names=inventory["assetClasses"]
    leverage=inventory["leverage"]
    quotes_observed={m["Contract"]["Symbol"] for f in authenticated["Frames"] for m in f["Markets"]}
    results=[]
    for c in contracts:
        symbol=c["Symbol"]
        category=category_names.get(int(c["Category"])) if c["Category"].isdigit() else None
        observed=estimated.get(symbol) or c.get("Margin")
        fields=c["Fields"]
        series={p:observed_bar_span(p,z) for p,z in coverage[symbol].items() if z}
        results.append(dict(symbol=symbol,categoryId=c["Category"],category=category[0] if category else None,
            assetClass=class_names.get(category[1]) if category else None,contractObservedAt=c["AvailableAt"],
            tradingMode=fields.get("tradingMode"),shortSelling=fields.get("enableShortSelling"),
            minimumVolumeCents=fields.get("minVolume"),stepVolumeCents=fields.get("stepVolume"),
            maxVolumeCents=fields.get("maxVolume"),leverageId=fields.get("leverageId"),
            observedLeverageTiers=leverage.get(fields.get("leverageId")),currency=c["QuoteAsset"],
            observedMinimumMargin=observed,currentQuoteAndEurRouteWitness=symbol in quotes_observed,
            swapType=c["SwapKind"],swapPeriodHours=fields.get("swapPeriod"),swapTimeUtcMinute=fields.get("swapTime"),
            swap3Days=fields.get("swapRollover3Days"),skipPeriods=fields.get("skipSWAPPeriods"),
            scheduleTimeZone=fields.get("scheduleTimeZone"),scheduleIntervals=len(fields.get("schedule",[])),
            warmup={p:series[p]["closedBars"] for p in source.PERIODS if p in series},
            timeframes={p:series.get(p) for p in source.PERIODS},
            historicFundingEffectiveIntervals=0,historicalFinancingEligibility="UNKNOWN"))
    matrix=dict(proof=proof,reusedRecentRuns=[short["Source"],extended["Source"]],
        coverageWithClocks=sum(bool(coverage[x["symbol"]]) for x in results),
        historicSyncedMultiAssetFinancedEligibilityCertified=False,
        countingMethod="AUTHENTIC_CLOSED_OPEN_TIMESTAMPS_DEDUPLICATED_ACROSS_ARCHIVES",matrix=results)
    (OUT/"universe-evidence-matrix.json").write_bytes(source.canonical(matrix)+b"\n")
    return dict(contracts=len(results),instrumentsWithBars=matrix["coverageWithClocks"],
                officialCategoriesMatched=sum(x["category"] is not None for x in results),
                clocksByTimeframe={p:sum(len(z.get(p,())) for z in coverage.values()) for p in source.PERIODS},
                authenticInputs=list(proof["SourceRuns"])+matrix["reusedRecentRuns"])


def use(matrix_only=False,reconcile_published=False):
    key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    run="45478379270" if reconcile_published else os.environ["GITHUB_RUN_ID"]
    original,public=unpack_original(OUT,key,run)
    inputs,inventory,tape=extract_input(original)
    with tempfile.TemporaryDirectory(prefix="official-eur-") as tmp:
        work=Path(tmp)
        if matrix_only:
            summary=market_matrix(work,key,inventory,inputs,tape)
            (OUT/"coverage-public.json").write_bytes(source.canonical(summary)+b"\n")
            return
        need(bool(inputs["Frames"]),"OFFICIAL_EUR_NO_COMMITTED_CLOCK")
        source_path=work/"source.json"
        source_path.write_bytes(source.canonical(inputs))
        result_path=work/"result.json"
        environment={k:v for k,v in os.environ.items() if k!="R3_CUSTODY_PRIVATE_KEY_PEM"}
        subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source_path),str(result_path),"--owner-official-eur"],env=environment,check=True)
        output=json.loads(result_path.read_text())
        output.update(public,officialEvidence=inventory)
        if reconcile_published:
            reference=Path("published-eur/native-eur-public.json").read_bytes()
            need(source.digest(reference)=="df9a9499bbe3899019d1df5b9911928b110c79aef2b89ba448beb8fbd815c57f",
                 "OFFICIAL_EUR_PUBLISHED_RECEIPT_HASH")
            expected={b["Policy"]:b["EventTraceSha256"] for b in json.loads(reference)["Books"]}
            matched={b["Policy"]:b["EventTraceSha256"] for b in output["Books"]}==expected
            need(matched,"OFFICIAL_EUR_PUBLISHED_EVENT_TRACE_MISMATCH")
            output.update(originalEconomicDecisionTraceVerified=True,readbackRunId=os.environ["GITHUB_RUN_ID"],
                          newBrokerRequests=0,newOrders=0)
            (OUT/"native-eur-settlement-public.json").write_bytes(source.canonical(output)+b"\n")
            return
        (OUT/"native-eur-public.json").write_bytes(source.canonical(output)+b"\n")


def safe_reason(error):
    # Only fixed program codes survive. SDK text can contain provider fields.
    value=str(error)
    return value if value.isascii() and value.replace("_","").isalnum() and value.isupper() else type(error).__name__


if __name__=="__main__":
    try:
        if sys.argv[1:]==["--readback"]:
            use()
        elif sys.argv[1:]==["--matrix"]:
            use(matrix_only=True)
        elif sys.argv[1:]==["--reconcile-published"]:
            use(reconcile_published=True)
        else:
            need(not sys.argv[1:],"OFFICIAL_EUR_MODE")
            capture()
    except Exception as error:
        # No provider payload, identifiers or credentials in the run log.
        print("OFFICIAL_EUR_FAILED",safe_reason(error),flush=True)
        raise SystemExit(1) from None

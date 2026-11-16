"""LQR1 new original EUR conversion BID/ASK and current broker contract SOURCE ONLY.

One 80-clock source, each paired EURUSD quote at entry and exit (320 side
requests). No LQR1 outcome scoring until this protected source is sealed.
"""
from __future__ import annotations
import base64, json, os
from collections import Counter
from datetime import date,datetime,timedelta,timezone
from hashlib import sha256
from pathlib import Path

from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .owner_readonly_auth import authenticate
from .guard import require_read_only_request
from .decode import decode_side, need
from .custody_new import checked_public
from .custody import seal_new

PROTO=Path("research/LQR1_ASYNC_BIDASK_REFRESH_PRESOURCE_20261116.md")
START=date(2026,9,14)
TARGETS=("USDCHF","EURGBP")
MAX_REQUESTS=360
FX_MAX_AGE_MS=20_000


def clocks():
    for w in range(8):
        for d in range(5):
            day=START+timedelta(weeks=w,days=d)
            for hour in (9,14):
                t=int(datetime(day.year,day.month,day.day,hour,tzinfo=timezone.utc).timestamp()*1000)
                yield t,w


def asof(rows,at):
    eligible=[x for x in rows if 0<=at-x[0]<=FX_MAX_AGE_MS and x[1]>0]
    if not eligible:return None
    return max(eligible,key=lambda x:x[0])


def fresh_pair(bids,asks,at):
    b,a=asof(bids,at),asof(asks,at)
    if b is None or a is None or b[1]>a[1]:return None
    return [b,a]


def main():
    need(PROTO.is_file(),"LQR1_PRE_FROZEN_PROTOCOL_MISSING")
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    t=StdlibCTraderTransport()
    raw=[]
    account=0
    def req(q,kind,optional=False):
        need(len(raw)<MAX_REQUESTS,"LQR1_REQUEST_BUDGET")
        require_read_only_request(q)
        reply=t.request(q)
        if optional and type(reply) is m.ProtoOAErrorRes and reply.errorCode=="NO_QUOTES" and reply.ctidTraderAccountId==account:
            value=None
        else:
            need(type(reply) is kind and reply.IsInitialized() and
                 reply.ctidTraderAccountId==account,"LQR1_ACCOUNT_RESPONSE")
            value=reply
        raw.append(dict(requestType=type(q).__name__,
                        request=base64.b64encode(q.SerializeToString()).decode(),
                        responseType=type(reply).__name__,
                        response=base64.b64encode(reply.SerializeToString()).decode()))
        return value
    try:
        account=authenticate(t)
        tr=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        names={a.assetId:a.name for a in assets.asset}
        need("pepperstone" in tr.trader.brokerName.casefold() and
             names.get(tr.trader.depositAssetId)=="EUR","LQR1_NOT_BOUND_EUR_BROKER")
        roster=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                                             includeArchivedSymbols=False),
                   m.ProtoOASymbolsListRes)
        symbols={s.symbolName:s for s in roster.symbol if s.enabled}
        need(all(x in symbols for x in TARGETS+("EURUSD",)),"LQR1_TARGET_ROSTER")
        contracts={}
        margins={}
        for sym in TARGETS+("EURUSD",):
            s=symbols[sym]
            reply=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                                               symbolId=[s.symbolId]),
                      m.ProtoOASymbolByIdRes)
            need(len(reply.symbol)==1 and reply.symbol[0].symbolId==s.symbolId,
                 "LQR1_CONTRACT_ID")
            contracts[sym]=reply.symbol[0]
        for sym in TARGETS:
            c=contracts[sym]
            need(c.HasField("minVolume") and c.minVolume>0,"LQR1_MIN_VOLUME_UNKNOWN")
            v=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                    symbolId=symbols[sym].symbolId,volume=[c.minVolume]),
                  m.ProtoOAExpectedMarginRes)
            need(v.HasField("moneyDigits") and len(v.margin)==1 and
                 v.margin[0].volume==c.minVolume,"LQR1_MARGIN_OR_GRID_UNKNOWN")
            margins[sym]=[v.margin[0].buyMargin/10**v.moneyDigits,
                           v.margin[0].sellMargin/10**v.moneyDigits]
        fx={}
        status=Counter()
        for t0,w in clocks():
            values={}
            for tag,at in (("entry",t0+60_000),("exit",t0+1_800_000)):
                observed=[]
                incomplete=False
                for side in (e.BID,e.ASK):
                    low=at-60_000
                    ans=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                            symbolId=symbols["EURUSD"].symbolId,type=side,
                            fromTimestamp=low,toTimestamp=at),m.ProtoOAGetTickDataRes,True)
                    if ans is None:
                        rows=[]
                    elif not ans.HasField("hasMore") or ans.hasMore:
                        incomplete=True; rows=[]
                    else:
                        rows=decode_side(ans.tickData,low,at)
                    observed.append(rows)
                q=None if incomplete else fresh_pair(*observed,at)
                values[tag]={"at":at,"pair":q,"truncated":incomplete}
                status["TRUNCATED" if incomplete else "VALID" if q else "UNKNOWN"]+=1
            fx[str(t0)]=dict(week=w,quotes=values)
        need(len(fx)==80 and len(raw)<=MAX_REQUESTS,
             "LQR1_FIXED_FX_CLOCKS_OR_BUDGET")
    finally:
        t.close()
    plaintext=json.dumps(dict(schema="MXM_LQR1_ORIGINAL_PEPPERSTONE_EURUSD_FX_FINANCIAL_SOURCE_V1",
        originalRunId=run,originalReadOnlyRequestCount=len(raw),originalRawProtobuf=raw,
        fixedEurUsdFxClockCount=len(fx),quotes=fx,accountSwapFree=bool(tr.trader.swapFree),
        currentTargetMargins=margins,originalPepperstoneEurAccount=True,
        originalSourceSealedBeforeLqr1EconomicScoring=True),separators=(",",":"),sort_keys=True).encode()
    sealed=seal_new(plaintext,recipient,run)
    Path("lqr1-original-financial-source.v2.enc").write_bytes(sealed)
    public=dict(schema="MXM_LQR1_ORIGINAL_PRESOURCE_FX_COVERAGE_V1",
        runId=int(run),frozenProtocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
        cipherSha256=sha256(sealed).hexdigest(),plainSha256=sha256(plaintext).hexdigest(),
        originalReadOnlyRequests=len(raw),originalFxClocks=len(fx),
        originalPairedQuoteStatus=dict(status),originalAccountEurVerified=True,
        sourceSealedBeforeAnyLqr1EconomicScoring=True,ordersSubmitted=0,cloudActivated=False)
    Path("lqr1-original-fx-source-coverage.public.json").write_text(json.dumps(public,sort_keys=True,indent=2)+"\n")
    print("LQR1_ORIGINAL_NEW_READONLY_FX_SOURCE_SEALED_BEFORE_ECONOMIC_SCORING",flush=True)


if __name__=="__main__":
    main()

"""GCL1 one-time original-account DOL-claims study quote acquisition ONLY.

Immutable protocol frozen on main before source code. All 43 Thursday
and 43 Tuesday clocks captured independent of causal signal/outcome.
NO prediction, BDP1 closed study replay, account orders or Cloud.
"""
from __future__ import annotations
import base64,json,os
from collections import Counter
from datetime import date,datetime,time,timedelta,timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .owner_readonly_auth import authenticate
from .guard import require_read_only_request
from .decode import decode_side
from .custody_new import checked_public
from .custody import seal_new

PROTO=Path("research/GCL1_CLAIMS_GOLD_EURUSD_ECONOMIC_PROTOCOL_20261116.md")
NY=ZoneInfo("America/New_York")
START=date(2026,1,8)
WEEKS=43
SAMPLES=((8,50),(9,10),(9,35))
MAX_CALLS=750
MAX_AGE=20_000
LOOKBACK=60_000


def ts(d,h,mi):
    return int(datetime.combine(d,time(h,mi),NY).timestamp()*1000)


def day_schedule():
    out=[]
    for i in range(WEEKS):
        t=START+timedelta(weeks=i)
        if t.weekday()!=3:raise ValueError("GCL1_CALENDAR_NOT_THURSDAY")
        out.extend(((t-timedelta(days=2),"PLACEBO_TUE",i),
                    (t,"DOL_THURSDAY",i)))
    if len(out)!=86 or out[-1][0]!=date(2026,10,29):
        raise ValueError("GCL1_CALENDAR_CENSUS")
    return out


def fresh(rows,at):
    x=[z for z in rows if z[0]<=at and z[1]>0]
    if not x:return None
    val=max(x,key=lambda z:z[0])
    return dict(at=val[0],raw=val[1],ageMs=at-val[0]) if at-val[0]<=MAX_AGE else None


def pair(bids,asks,at):
    bid,ask=fresh(bids,at),fresh(asks,at)
    return dict(bid=bid,ask=ask) if bid and ask and bid["raw"]<=ask["raw"] else None


def main():
    if not PROTO.is_file():raise ValueError("GCL1_PRE_FREEZE_NOT_PRESENT")
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    tr=StdlibCTraderTransport()
    raw=[];status=Counter();days={}
    def req(q,expected,allow_empty=False):
        if len(raw)>=MAX_CALLS:raise ValueError("GCL1_BROKER_REQUEST_CEILING")
        require_read_only_request(q)
        res=tr.request(q)
        if allow_empty and type(res) is m.ProtoOAErrorRes and res.errorCode=="NO_QUOTES" and res.ctidTraderAccountId==account:
            value=None
        elif type(res) is expected and res.IsInitialized() and res.ctidTraderAccountId==account:
            value=res
        else:raise ValueError("GCL1_ORIGINAL_ACCOUNT_REPLY_MISMATCH")
        raw.append(dict(requestType=type(q).__name__,request=base64.b64encode(q.SerializeToString()).decode(),
                        responseType=type(res).__name__,response=base64.b64encode(res.SerializeToString()).decode()))
        return value
    try:
        account=authenticate(tr)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        currency={a.assetId:a.name for a in assets.asset}
        if "pepperstone" not in trader.trader.brokerName.casefold() or currency.get(trader.trader.depositAssetId)!="EUR":
            raise ValueError("GCL1_ACCOUNT_NOT_ORIGINAL_PEPPERSTONE_EUR")
        symbols=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        listing={s.symbolName:s for s in symbols.symbol if s.enabled}
        if "EURUSD" not in listing:raise ValueError("GCL1_EURUSD_BROKER_NOT_ENABLED")
        s=listing["EURUSD"]
        if currency.get(s.baseAssetId)!="EUR" or currency.get(s.quoteAssetId)!="USD":
            raise ValueError("GCL1_EURUSD_BAD_CURRENCY_IDENTITIES")
        detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[s.symbolId]),m.ProtoOASymbolByIdRes)
        if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=s.symbolId:
            raise ValueError("GCL1_EURUSD_BROKER_CONTRACT")
        contract=detail.symbol[0]
        if contract.minVolume<=0 or contract.minVolume%100!=0:
            raise ValueError("GCL1_EURUSD_MINIMUM_VOLUME_UNKNOWN")
        margin=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=s.symbolId,volume=[contract.minVolume]),m.ProtoOAExpectedMarginRes)
        if not margin.HasField("moneyDigits") or len(margin.margin)!=1 or margin.margin[0].volume!=contract.minVolume:
            raise ValueError("GCL1_MARGIN_RESPONSE_UNUSABLE")
        for day,arm,week in day_schedule():
            obs=dict(week=week,arm=arm,quotes={})
            days[day.isoformat()]=obs
            for h,mi in SAMPLES:
                at=ts(day,h,mi)
                observations=[];incomplete=False
                for side in (e.BID,e.ASK):
                    ans=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=s.symbolId,
                                  type=side,fromTimestamp=at-LOOKBACK,toTimestamp=at),
                            m.ProtoOAGetTickDataRes,True)
                    if ans is None:rows=[]
                    elif not ans.HasField("hasMore") or ans.hasMore:
                        incomplete=True;rows=[]
                    else:
                        rows=decode_side(ans.tickData,at-LOOKBACK,at)
                    observations.append(rows)
                q=None if incomplete else pair(*observations,at)
                obs["quotes"][str(at)]=dict(pair=q,truncated=incomplete)
                status["PAIR" if q else "TRUNCATED" if incomplete else "MISSING_OR_STALE"]+=1
            if week%8==7 and arm=="DOL_THURSDAY":
                print("GCL1_READONLY_CALENDAR_WEEK",week+1,"/",WEEKS,"REQUESTS",len(raw),flush=True)
    finally:tr.close()
    plaintext=json.dumps(dict(schema="MXM_GCL1_ORIGINAL_PEPPERSTONE_EURUSD_BIDASK_SOURCE_V1",run=run,
        originalPepperstoneEurBound=True,originalReadOnlyCallsAfterAuth=len(raw),
        originalRawProtobuf=raw,monthCalendar=days,sourceOnlyBeforeAllGcl1EconomicScoring=True,
        accountSwapFreeEffective=bool(trader.trader.swapFree),
        currentMinVolume=contract.minVolume,
        currentMarginBuyEur=margin.margin[0].buyMargin/10**margin.moneyDigits,
        currentMarginSellEur=margin.margin[0].sellMargin/10**margin.moneyDigits),
        sort_keys=True,separators=(",",":")).encode()
    ciphertext=seal_new(plaintext,recipient,run)
    Path("gcl1-original-source.v2.enc").write_bytes(ciphertext)
    public=dict(schema="MXM_GCL1_ORIGINAL_READONLY_QUOTE_SOURCE_ONLY_V1",
        runId=int(run),preFrozenProtocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
        originalSourceCipherSha256=sha256(ciphertext).hexdigest(),
        originalSourcePlainSha256=sha256(plaintext).hexdigest(),
        readOnlyCallsAfterAuth=len(raw),fixedDays=86,clocksPerDay=3,
        quotes=dict(status),sourceSealedBeforeOutcomeEvaluation=True,
        authenticatedPepperstoneEurAccount=True,
        sourceNoBrokerOrders=True,
        currentMinVolume=contract.minVolume,
        currentMarginBuyEur=margin.margin[0].buyMargin/10**margin.moneyDigits,
        currentMarginSellEur=margin.margin[0].sellMargin/10**margin.moneyDigits,
        noMarketPriceRowsPublished=True,noNewPrediction=True,orders=0,cloudActivated=False)
    Path("gcl1-original-source-coverage.public.json").write_text(json.dumps(public,indent=2,sort_keys=True)+"\n")
    print("GCL1_ORIGINAL_SOURCE_SEALED_NO_OUTCOME_SCORING",
          json.dumps({"requests":len(raw),"quoteStatus":dict(status)}),flush=True)

if __name__=="__main__":
    main()

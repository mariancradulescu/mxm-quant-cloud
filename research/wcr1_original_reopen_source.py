"""WCR1 first-original Pepperstone scope-view WEEKEND crypto to US500 source.
SOURCE ONLY. No prior closed strategy, no economic labels/score, no orders.
"""
from __future__ import annotations
import base64,json,os
from collections import Counter
from datetime import date,datetime,timedelta,time
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo

from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .guard import require_read_only_request
from .decode import decode_bars,decode_side,need
from .custody_new import checked_public
from .custody import seal_new

PROTO=Path("research/WCR1_WEEKEND_CRYPTO_US500_REOPEN_PRESOURCE_20261116.md")
START=date(2025,11,16)
WEEKS=52
NY=ZoneInfo("America/New_York")
SYMS=("BTCUSD","US500","EURUSD")
MAX_CALLS=1600
MAX_AGE=20000
BAR_MS=300000
BACK=60000

def stamp(day,hour,minute=0):
    return int(datetime.combine(day,time(hour,minute),NY).timestamp()*1000)

def calendar():
    for i in range(WEEKS):
        sun=START+timedelta(weeks=i)
        fri=sun-timedelta(days=2)
        bars=(("BTCUSD",stamp(fri,17)),("BTCUSD",stamp(sun,17)),
              ("US500",stamp(sun,18,5)),("US500",stamp(sun,18,15)))
        marks=tuple(stamp(sun,18,m) if m<60 else stamp(sun,19,m-60)
                    for m in (20,40,60,80))
        yield i,sun,bars,marks

def last_pair(rows,at):
    bb,aa=[],[]
    for src,dst in zip(rows,(bb,aa)):
        dst.extend((int(t),int(p)) for t,p in src if int(t)<=at and int(p)>0)
    if not bb or not aa:return None
    b=bb[-1];a=aa[-1]
    if b[0]<at-MAX_AGE or a[0]<at-MAX_AGE or b[1]>a[1]:return None
    return [list(b),list(a)]

def main():
    need(PROTO.is_file() and "PRESOURCE FROZEN" in PROTO.read_text(),
         "WCR1_PROTOCOL_NOT_FROZEN")
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    raw=[]
    t=StdlibCTraderTransport()
    def request(q,kind,can_be_missing=False):
        need(len(raw)<MAX_CALLS,"WCR1_READONLY_REQUEST_CAP")
        require_read_only_request(q)
        ans=t.request(q)
        if type(ans) is m.ProtoOAErrorRes and can_be_missing:
            need(ans.errorCode=="NO_QUOTES" and ans.ctidTraderAccountId==account,
                 "WCR1_BROKER_UNEXPECTED_MISSING_RESPONSE")
            ok=None
        else:
            need(type(ans) is kind and ans.IsInitialized()
                 and ans.ctidTraderAccountId==account,
                 "WCR1_BROKER_ORIGINAL_RESPONSE_OR_SCOPE_INVALID")
            ok=ans
        raw.append(dict(requestType=type(q).__name__,
            responseType=type(ans).__name__,
            request=base64.b64encode(q.SerializeToString()).decode(),
            response=base64.b64encode(ans.SerializeToString()).decode()))
        return ok,len(raw)-1
    try:
        account=authenticate(t)
        trader,_=request(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets,_=request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        roster,_=request(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        names={x.assetId:x.name for x in assets.asset}
        need("pepperstone" in trader.trader.brokerName.casefold()
             and names.get(trader.trader.depositAssetId)=="EUR","WCR1_ORIGINAL_EUR_BROKER")
        fixed={x.symbolName:x for x in roster.symbol if x.enabled}
        need(all(s in fixed for s in SYMS),"WCR1_ORIGINAL_ROSTER_MISSING_FIXED_SYMBOL")
        need(names.get(fixed["US500"].quoteAssetId)=="USD"
             and names.get(fixed["EURUSD"].baseAssetId)=="EUR"
             and names.get(fixed["EURUSD"].quoteAssetId)=="USD",
             "WCR1_ORIGINAL_CFD_USD_TO_EUR_BINDING_UNKNOWN")
        ids={s:fixed[s].symbolId for s in SYMS}
        contracts={}
        for s in SYMS:
            detail,_=request(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                symbolId=[ids[s]]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==ids[s],
                 "WCR1_SYMBOL_DETAIL_CHANGED")
            contracts[s]=detail.symbol[0]
        volume=contracts["US500"].minVolume
        need(volume>0,"WCR1_INVALID_US500_MINIMUM")
        margin,_=request(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                symbolId=ids["US500"],volume=[volume]),m.ProtoOAExpectedMarginRes)
        need(margin.HasField("moneyDigits") and len(margin.margin)==1
             and margin.margin[0].volume==volume,"WCR1_ORIGINAL_BOTH_SIDE_MARGIN_UNKNOWN")
        mscale=10**margin.moneyDigits
        margins=[margin.margin[0].buyMargin/mscale,margin.margin[0].sellMargin/mscale]
        rows=[]
        coverage=Counter()
        for week,sun,bars,marks in calendar():
            entry=dict(week=week,day=sun.isoformat(),bars=[],marks=[])
            for sym,end in bars:
                req=m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,
                    symbolId=ids[sym],period=e.M5,fromTimestamp=end-BAR_MS,
                    toTimestamp=end)
                ans,idx=request(req,m.ProtoOAGetTrendbarsRes,True)
                incomplete=ans is not None and (not ans.HasField("hasMore") or ans.hasMore)
                chosen=None
                if ans is not None and not incomplete:
                    got=decode_bars(ans.trendbar,end-BAR_MS,end,5)
                    matches=[v for v in got if int(v[1])==end]
                    need(len(matches)<=1,"WCR1_ORIGINAL_DUPLICATE_ENDPOINT")
                    chosen=int(matches[0][5]) if matches else None
                entry["bars"].append(dict(symbol=sym,at=end,rawIndex=idx,
                                          closeRaw=chosen,truncated=bool(incomplete)))
                coverage["PRE_BAR_VALID" if chosen is not None else "PRE_BAR_UNKNOWN"]+=1
            for at in marks:
                block=dict(at=at,symbols={})
                for sym in ("US500","EURUSD"):
                    sides=[]
                    inds=[]
                    incomplete=False
                    for typ in (e.BID,e.ASK):
                        ans,idx=request(m.ProtoOAGetTickDataReq(
                            ctidTraderAccountId=account,symbolId=ids[sym],type=typ,
                            fromTimestamp=at-BACK,toTimestamp=at),m.ProtoOAGetTickDataRes,True)
                        inds.append(idx)
                        if ans is None:values=[]
                        elif not ans.HasField("hasMore") or ans.hasMore:
                            incomplete=True;values=[]
                        else:values=decode_side(ans.tickData,at-BACK,at)
                        sides.append(values)
                    p=None if incomplete else last_pair(sides,at)
                    block["symbols"][sym]=dict(pair=p,truncated=incomplete,
                                                   rawIndices=inds)
                    coverage["PAIR_"+sym if p is not None else "UNKNOWN_"+sym]+=1
                entry["marks"].append(block)
            rows.append(entry)
            if week%8==7:print("WCR1_ORIGINAL_WEEK",week+1,"OF",WEEKS,
                                 "READONLY_CALLS",len(raw),flush=True)
    finally:
        t.close()
    need(len(rows)==52 and len(raw)==7+52*(4+16),
         "WCR1_ORIGINAL_REQUEST_CALENDAR_INCOMPLETE")
    plain=json.dumps(dict(schema="MXM_WCR1_ORIGINAL_CRYPTO_US500_REOPEN_SOURCE_V1",
        runId=run,accountIsOriginalPepperstoneEur=True,scopeViewOnlyRequests=True,
        sourceSealedBeforeScore=True,ordersSubmitted=0,cloudActivated=False,
        raw=raw,rows=rows,originalMinVolume=volume,
        currentBuySellMarginEur=margins,
        accountSwapFree=trader.trader.swapFree if trader.trader.HasField("swapFree") else None),
        sort_keys=True,separators=(",",":")).encode()
    ciphertext=seal_new(plain,recipient,run)
    Path("wcr1-original-reopen-source.v2.enc").write_bytes(ciphertext)
    receipt=dict(schema="MXM_WCR1_ORIGINAL_SOURCE_PREOUTCOME_V1",
        originalRunId=int(run),frozenProtocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
        cipherSha256=sha256(ciphertext).hexdigest(),plainSha256=sha256(plain).hexdigest(),
        originalReadOnlyRequests=len(raw),scheduledWeeks=WEEKS,
        quoteCoverage=dict(coverage),currentBuySellMarginEur=margins,
        currentUS500MinimumVolumeRaw=volume,
        sourceSealedBeforeEconomicScore=True,noFuturePriceScored=True,
        brokerOrders=0,cloudActivated=False,independentChronology=False,
        brokerSource="original-Pepperstone-EUR-readonly")
    Path("wcr1-original-source-public.json").write_text(
        json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("WCR1_ORIGINAL_AUTHENTIC_PREOUTCOME_SEALED",json.dumps({
        "requests":len(raw),"weeks":len(rows),"coverage":dict(coverage)}),flush=True)

if __name__=="__main__":
    main()

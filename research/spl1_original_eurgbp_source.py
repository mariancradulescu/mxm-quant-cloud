"""SPL1 original-account strictly read-only EURGBP M5 + GBPUSD/EURUSD quote source.

Frozen main protocol first (PR #330). No prediction, money scoring or prior
closed study run in original broker job. All scheduled clocks independent of returns.
"""
from __future__ import annotations
from collections import Counter
from datetime import date,datetime,timedelta,time,timezone
from hashlib import sha256
from pathlib import Path
from zoneinfo import ZoneInfo
import base64,json,os

from .owner_readonly_auth import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .decode import decode_bars,decode_side
from .guard import require_read_only_request
from .custody_new import checked_public
from .custody import seal_new

PROTO=Path("research/SPL1_STERLING_CROSS_PRICE_DISCOVERY_FROZEN_20261116.md")
LONDON=ZoneInfo("Europe/London")
START=date(2025,11,3)
WEEKS=52
CLOCKS=((9,30),(14,30))
ENTRY_OFFSET=5
EXIT_OFFSET=35
PERIOD_MS=300000
FROM_MS=1762128000000
TO_MS=1793577600000
CHUNK_MS=10*86400000
MAX_CALLS=4500
MAX_AGE=20000
LOOKBACK=60000
SYMBOLS=("EURGBP","GBPUSD","EURUSD")


def stamp(d,h,m):
    return int(datetime.combine(d,time(h,m),LONDON).timestamp()*1000)


def calendar():
    for w in range(WEEKS):
        for dw in range(5):
            d=START+timedelta(weeks=w,days=dw)
            for h,mi in CLOCKS:
                yield d,w,stamp(d,h,mi)
                
def event_clocks():
    for d,w,t in calendar():
        yield d,w,t,t+ENTRY_OFFSET*60000,t+EXIT_OFFSET*60000


def chunks():
    t=FROM_MS
    while t<TO_MS:
        end=min(t+CHUNK_MS,TO_MS)
        yield t,end
        t=end


def side_last(rows,at):
    values=[x for x in rows if x[0]<=at and x[1]>0]
    if not values:return None
    t,p=values[-1]
    if t<at-MAX_AGE:return None
    return dict(at=int(t),raw=int(p),ageMs=int(at-t))


def sampled(bids,asks,at):
    b=side_last(bids,at)
    a=side_last(asks,at)
    return dict(bid=b,ask=a) if b and a and b["raw"]<=a["raw"] else None


def main():
    if not PROTO.is_file():raise ValueError("SPL1_PROTOCOL_NOT_FROZEN")
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    t=StdlibCTraderTransport()
    raw=[]; coverage=Counter();responses={}
    def req(q,typ,allow_missing=False):
        if len(raw)>=MAX_CALLS:raise RuntimeError("SPL1_REQUEST_CEILING")
        require_read_only_request(q)
        ans=t.request(q)
        if allow_missing and type(ans) is m.ProtoOAErrorRes and ans.errorCode=="NO_QUOTES" and ans.ctidTraderAccountId==account:
            out=None
        elif type(ans) is typ and ans.IsInitialized() and ans.ctidTraderAccountId==account:
            out=ans
        else:raise RuntimeError("SPL1_ORIGINAL_BROKER_RESPONSE_OR_SCOPE")
        idx=len(raw)
        raw.append(dict(requestType=type(q).__name__,request=base64.b64encode(q.SerializeToString()).decode(),
                        responseType=type(ans).__name__,response=base64.b64encode(ans.SerializeToString()).decode()))
        return out,idx
    try:
        account=authenticate(t)
        trader,_=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        assets,_=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        asset={x.assetId:x.name for x in assets.asset}
        if "pepperstone" not in trader.trader.brokerName.casefold() or asset.get(trader.trader.depositAssetId)!="EUR":
            raise RuntimeError("SPL1_NOT_ORIGINAL_EUR_ACCOUNT")
        roster,_=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        named={x.symbolName:x for x in roster.symbol if x.enabled}
        if not all(s in named for s in SYMBOLS):
            raise RuntimeError("SPL1_FIXED_SYMBOL_NOT_ENABLED")
        if not (asset.get(named["GBPUSD"].quoteAssetId)=="USD" and
                asset.get(named["EURUSD"].baseAssetId)=="EUR" and
                asset.get(named["EURUSD"].quoteAssetId)=="USD" and
                asset.get(named["EURGBP"].quoteAssetId)=="GBP"):
            raise RuntimeError("SPL1_FX_CROSS_CURRENCY_BINDING")
        terms={}
        for s in SYMBOLS:
            response,_=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[named[s].symbolId]),m.ProtoOASymbolByIdRes)
            if len(response.symbol)!=1 or response.symbol[0].symbolId!=named[s].symbolId:
                raise RuntimeError("SPL1_CONTRACT_BINDING")
            terms[s]=response.symbol[0]
        minv=terms["GBPUSD"].minVolume
        if minv<=0 or minv%100:raise RuntimeError("SPL1_GBPUSD_MIN_VOLUME")
        margin,_=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,
                symbolId=named["GBPUSD"].symbolId,volume=[minv]),m.ProtoOAExpectedMarginRes)
        if not margin.HasField("moneyDigits") or len(margin.margin)!=1 or margin.margin[0].volume!=minv:
            raise RuntimeError("SPL1_GBPUSD_MIN_MARGIN_UNAVAILABLE")
        history=[];done=set()
        for first,last in chunks():
            reply,idx=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=named["EURGBP"].symbolId,
                  period=e.M5,fromTimestamp=first,toTimestamp=last),m.ProtoOAGetTrendbarsRes)
            if reply.period!=e.M5 or not reply.HasField("hasMore") or reply.hasMore:
                raise RuntimeError("SPL1_EURGBP_ORIGINAL_BAR_PAGE_INCOMPLETE")
            rows=decode_bars(reply.trendbar,first-PERIOD_MS,last+PERIOD_MS,5)
            for row in rows:
                if first<=row[0] and row[1]<=last:
                    if row[0] in done:raise RuntimeError("SPL1_DUPLICATE_SOURCE_BAR")
                    done.add(row[0]);history.append(row)
            coverage["originalEURGBPHistoryWindows"]+=1
        history.sort()
        if not history:raise RuntimeError("SPL1_EURGBP_M5_HISTORY_EMPTY")
        fixed={}
        for d,w,decision,entry,exit in event_clocks():
            key=f"{d.isoformat()}|{decision}"
            day=dict(week=w,decision=decision,quoteTimes={})
            for at in (entry,exit):
                for symbol in ("GBPUSD","EURUSD"):
                    sides=[]; incomplete=False; indices=[]
                    for side in (e.BID,e.ASK):
                        reply,idx=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=named[symbol].symbolId,
                                type=side,fromTimestamp=at-LOOKBACK,toTimestamp=at),m.ProtoOAGetTickDataRes,True)
                        indices.append(idx)
                        if reply is None:points=[]
                        elif not reply.HasField("hasMore") or reply.hasMore:
                            incomplete=True;points=[]
                        else:points=decode_side(reply.tickData,at-LOOKBACK,at)
                        sides.append(points)
                    pair=None if incomplete else sampled(*sides,at)
                    day["quoteTimes"][f"{at}|{symbol}"]=dict(pair=pair,truncated=incomplete,rawIndices=indices)
                    coverage["PAIR_"+symbol if pair else "INCOMPLETE_"+symbol if incomplete else "MISSING_"+symbol]+=1
            fixed[key]=day
            if d.weekday()==4 and decision==stamp(d,*CLOCKS[-1]) and w%4==3:
                print("SPL1_AUTHENTIC_READONLY_WEEK",w+1,"OF",WEEKS,"REQUESTS",len(raw),flush=True)
    finally:
        t.close()
    payload=dict(schema="MXM_SPL1_STERLING_ORIGINAL_ANNUAL_M5_BIDASK_V1",sourceRun=run,
                 originalPepperstoneEur=True,readOnly=True,brokerOrders=0,cloudActivated=False,
                 rawCalls=raw,originalEURGBPBars=history,calendar=fixed,scopeBeforeFinance=True,
                 contractVolume=terms["GBPUSD"].minVolume,
                 buyMarginEur=margin.margin[0].buyMargin/10**margin.moneyDigits,
                 sellMarginEur=margin.margin[0].sellMargin/10**margin.moneyDigits,
                 swapFreeKnown=trader.trader.HasField("swapFree"),
                 swapFree=bool(trader.trader.swapFree) if trader.trader.HasField("swapFree") else None,
                 fullOriginalCalendar=len(fixed))
    plaintext=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    cipher=seal_new(plaintext,recipient,run)
    Path("spl1-original-source.v2.enc").write_bytes(cipher)
    report=dict(schema="MXM_SPL1_ORIGINAL_SOURCE_ONLY_NO_FINANCIAL_SCORE",
                originalRunId=int(run),protocolSha256=sha256(PROTO.read_bytes()).hexdigest(),
                originalSourceCipherSha256=sha256(cipher).hexdigest(),
                originalSourcePlainSha256=sha256(plaintext).hexdigest(),
                sourceCausalM5EURGBPRows=len(history),originalReadOnlyCalls=len(raw),
                fullCalendar=len(fixed),scheduledWeeks=WEEKS,quoteCoverage=dict(coverage),
                currentMinimumVolume=terms["GBPUSD"].minVolume,
                currentBuyMarginEur=payload["buyMarginEur"],
                currentSellMarginEur=payload["sellMarginEur"],
                sourceSealedBeforeScoring=True,financialOutcomeScored=False,
                historicalFillCertified=False,rawMarketDataPublic=False,
                originalOrders=0,cloudActivated=False)
    Path("spl1-original-source-public.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print("SPL1_SOURCE_COLLECTED_AND_SEALED_NO_SCORING",json.dumps({
        "requests":len(raw),"calendar":len(fixed),"coverage":dict(coverage)}),flush=True)

if __name__=="__main__":
    main()

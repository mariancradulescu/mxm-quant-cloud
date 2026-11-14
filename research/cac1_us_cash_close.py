"""CAC1: original-account ETF cash-close matched economic pressure.

Original-account Pepperstone read-only; 26 globally exposed weeks.
Cash-close vs midday matched original quote-side EUR net, archived BEFORE scoring.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import date,datetime,time,timedelta,timezone
from decimal import Decimal as D
from hashlib import sha256
import json,os
from math import log
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars,decode_side
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody_new import checked_public
from .custody import seal_new
from .rne1_eur_protected_exact_reconciliation import current_eur,no_swap,Unpriced

NY=ZoneInfo("America/New_York")
START=date(2026,5,4)
WEEKS=26
M5=300000
PAIRS={"SPY.US":"US500","QQQ.US":"NAS100"}
SYMBOLS=("US500","SPY.US","NAS100","QQQ.US","EURUSD")
CLOCKS=(("13:35",13,35),("13:55",13,55),("15:35",15,35),("15:55",15,55))
MAX_CALLS=5000
MAX_AGE_MS=20000


def stamp(day,hh,mm):
    return int(datetime.combine(day,time(hh,mm),NY).timestamp()*1000)


def priced_pair(bids,asks,clock):
    def asof(rows):
        good=[x for x in rows if x[0]<=clock and x[1]>0]
        if not good:return None
        last=max(good,key=lambda x:x[0])
        if clock-last[0]>MAX_AGE_MS:return None
        return last
    bid,ask=asof(bids),asof(asks)
    if not bid or not ask or bid[1]>ask[1]:
        return None
    return [bid[1],ask[1]]


def bar_at(rows,open_at):
    found=[x for x in rows if x[0]==open_at and x[1]==open_at+M5]
    if len(found)!=1:
        return None
    return found[0]



def feature(day,index_bars,etf_bars,hour,minute):
    """Decision at hour:minute+15; only the preceding three CLOSED M5 candles."""
    begin=stamp(day,hour,minute)
    idx=[bar_at(index_bars,begin+i*M5) for i in range(3)]
    etf=[bar_at(etf_bars,begin+i*M5) for i in range(3)]
    if any(x is None for x in idx+etf):
        return {"state":"UNKNOWN_M5_MISSING"}
    if any(min(x[2],x[5])<=0 for x in idx+etf):
        return {"state":"UNKNOWN_PRICE"}
    indexmove=idx[-1][5]-idx[0][2]
    etfmove=etf[-1][5]-etf[0][2]
    indexside=(indexmove>0)-(indexmove<0)
    etfside=(etfmove>0)-(etfmove<0)
    side=indexside if indexside==etfside and indexside!=0 else 0
    return {"state":"CAUSAL_ALIGNED" if side else "CAUSAL_ABSTAIN",
            "side":side,"etfSide":etfside,"indexSide":indexside}


def get_money(c,entry,exit_,fx_in,fx_out,side,slip,entry_at,exit_at):
    if not side:
        return 0.0
    no_swap(c,entry_at,exit_at)
    opening=tuple(D(p)/D(100000) for p in entry)
    ending=tuple(D(p)/D(100000) for p in exit_)
    fxopen=tuple(D(p)/D(100000) for p in fx_in)
    fxclose=tuple(D(p)/D(100000) for p in fx_out)
    out=current_eur(c,opening,ending,fxopen,fxclose,side,slip)
    return float(out["netEur"])


def summarize(rows):
    complete=[x for x in rows if x["state"]=="COMPLETE_COMPARABLE_DAY"]
    keys=("close","midday","etfOnly","long","short","cash")
    def sums(scenario):
        return {k:round(sum(x["money"][scenario][k] for x in complete),6)
                for k in keys}
    out={"scheduledDays":len(rows),
         "states":dict(Counter(x["state"] for x in rows)),
         "completeComparableDays":len(complete),
         "completeWeeks":len({x["week"] for x in complete}),
         "causalCloseIntents":sum(x.get("closeSide",0)!=0 for x in rows),
         "causalMiddayIntents":sum(x.get("middaySide",0)!=0 for x in rows),
         "completeCloseIntents":sum(x["closeSide"]!=0 for x in complete),
         "completeMiddayIntents":sum(x["middaySide"]!=0 for x in complete),
         "allDaysMissingRemainUnknown":True}
    for scenario in ("central","adverse"):
        values=sums(scenario)
        out[scenario+"CurrentContractNetEur"]=values
        out[scenario+"CloseIncrementVsMiddayEur"]=round(
            values["close"]-values["midday"],6)
        out[scenario+"CloseIncrementVsEtfOnlyEur"]=round(
            values["close"]-values["etfOnly"],6)
        out[scenario+"CloseIncrementVsLongEur"]=round(
            values["close"]-values["long"],6)
        out[scenario+"CloseIncrementVsShortEur"]=round(
            values["close"]-values["short"],6)
    return out


def evaluate(original,contracts,status):
    outcomes={}
    for etf,index in PAIRS.items():
        rows=[]
        for week in range(WEEKS):
            monday=START+timedelta(weeks=week)
            for wd in range(5):
                day=monday+timedelta(days=wd)
                rec=original["dates"][day.isoformat()]
                idx=rec["bars"].get(index)
                fund=rec["bars"].get(etf)
                if (idx is None or fund is None or
                        rec["barTruncated"].get(index) or
                        rec["barTruncated"].get(etf)):
                    rows.append({"week":week,"state":"UNKNOWN_BAR_SOURCE"})
                    continue
                close=feature(day,idx,fund,15,15)
                midday=feature(day,idx,fund,13,15)
                if close["state"].startswith("UNKNOWN") or midday["state"].startswith("UNKNOWN"):
                    rows.append({"week":week,"state":"UNKNOWN_FEATURE_M5"})
                    continue
                rec_base={"week":week,"closeSide":close["side"],
                          "middaySide":midday["side"]}
                quotes=rec["quotes"].get(etf,{})
                eurusd=rec["quotes"].get("EURUSD",{})
                if any(quotes.get(k) is None for k,_,_ in CLOCKS):
                    rows.append({**rec_base,"state":"UNKNOWN_ETF_BID_ASK"})
                    continue
                if any(eurusd.get(k) is None for k,_,_ in CLOCKS):
                    rows.append({**rec_base,"state":"UNKNOWN_FX_BID_ASK"})
                    continue
                margins=status.get(etf,{})
                if (margins.get("marginBuyEur") is None or
                        margins.get("marginSellEur") is None or
                        min(margins["marginBuyEur"],margins["marginSellEur"])<0 or
                        max(margins["marginBuyEur"],margins["marginSellEur"])>=300):
                    rows.append({**rec_base,"state":"UNKNOWN_EUR300_CONTRACT_MARGIN"})
                    continue
                policy={"close":(close["side"],"15:35","15:55"),
                        "midday":(midday["side"],"13:35","13:55"),
                        "etfOnly":(close["etfSide"],"15:35","15:55"),
                        "long":(1,"15:35","15:55"),
                        "short":(-1,"15:35","15:55"),
                        "cash":(0,"15:35","15:55")}
                money={}
                try:
                    for scenario,slip in (("central",0.5),("adverse",2.0)):
                        money[scenario]={}
                        for name,(side,qin,qout) in policy.items():
                            hin,minin=next((h,m) for label,h,m in CLOCKS if label==qin)
                            hout,minout=next((h,m) for label,h,m in CLOCKS if label==qout)
                            money[scenario][name]=get_money(
                                contracts[etf],quotes[qin],quotes[qout],
                                eurusd[qin],eurusd[qout],side,slip,
                                stamp(day,hin,minin),stamp(day,hout,minout))
                except (Unpriced,ValueError,ArithmeticError,KeyError,TypeError) as err:
                    rows.append({**rec_base,"state":"UNKNOWN_TARIFF_OR_CONVERSION",
                                 "reason":str(err)[:80]})
                    continue
                rows.append({**rec_base,"state":"COMPLETE_COMPARABLE_DAY",
                             "money":money})
        outcomes[etf]={
            "index":index,
            "minMarginCurrentBuyEur":status.get(etf,{}).get("marginBuyEur"),
            "minMarginCurrentSellEur":status.get(etf,{}).get("marginSellEur"),
            "all":summarize(rows),
            "first13Weeks":summarize([x for x in rows if x["week"]<13]),
            "last13Weeks":summarize([x for x in rows if x["week"]>=13]),
            "supportedPortfolioAdmission":False}
    return outcomes

def gross_quote_bps(entry,exit_,side):
    if side==0:return [0.,0.]
    if entry is None or exit_ is None:return None
    b0,a0=(D(p)/D(100000) for p in entry)
    b1,a1=(D(p)/D(100000) for p in exit_)
    if min(b0,a0,b1,a1)<=0 or b0>a0 or b1>a1:
        return None
    mid0=(b0+a0)/2;mid1=(b1+a1)/2
    crossing=D(side)*((b1 if side>0 else a1)-
                       (a0 if side>0 else b0))/mid0*D(10000)
    return [float(D(side)*(mid1-mid0)/mid0*D(10000)),float(crossing)]


def mean_field(rows,path):
    vals=[]
    for r in rows:
        a=r
        for p in path:a=a[p]
        vals.append(a)
    return mean(vals) if vals else None


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    originalRequests=[]
    t=StdlibCTraderTransport()
    count=0
    original={"dates":{}}
    ids={}
    status={}
    contracts={}
    fx_cache={}
    bar_quote_intents=0

    def req(q,klass,empty=False):
        nonlocal count
        if count>=MAX_CALLS:
            raise RuntimeError("CAC1_ORIGINAL_READ_ONLY_CEILING")
        require_read_only_request(q)
        reply=t.request(q)
        count+=1
        if (empty and type(reply) is m.ProtoOAErrorRes and
            reply.errorCode=="NO_QUOTES" and
            reply.ctidTraderAccountId==account):
            result=None
        elif (type(reply) is klass and reply.IsInitialized() and
              reply.ctidTraderAccountId==account):
            result=reply
        else:
            raise RuntimeError("CAC1_ORIGINAL_ACCOUNT_OR_RESPONSE_MISMATCH")
        originalRequests.append({
            "requestType":type(q).__name__,
            "request":base64.b64encode(q.SerializeToString()).decode(),
            "responseType":type(reply).__name__,
            "response":base64.b64encode(reply.SerializeToString()).decode()})
        return result

    def source_pair(symbol,day,label,hh,mm):
        at=stamp(day,hh,mm)
        side_rows=[];unresolved=False
        for side in (e.BID,e.ASK):
            q=req(m.ProtoOAGetTickDataReq(
                ctidTraderAccountId=account,symbolId=ids[symbol],
                type=side,fromTimestamp=at-60000,toTimestamp=at),
                m.ProtoOAGetTickDataRes,True)
            if q is None:
                side_rows.append([])
            elif q.hasMore:
                unresolved=True
                side_rows.append([])
            else:
                side_rows.append(decode_side(q.tickData,at-60000,at))
        return None if unresolved else priced_pair(*side_rows,at)

    try:
        account=authenticate(t)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),
                   m.ProtoOATraderRes)
        asset=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                  m.ProtoOAAssetListRes)
        assets={x.assetId:x.name for x in asset.asset}
        if ("pepperstone" not in trader.trader.brokerName.casefold()
            or assets.get(trader.trader.depositAssetId)!="EUR"):
            raise RuntimeError("CAC1_NOT_ORIGINAL_PEPPERSTONE_EUR")
        roster=req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        symbols={x.symbolName:x for x in roster.symbol if x.enabled}
        if not all(x in symbols for x in SYMBOLS):
            raise RuntimeError("CAC1_EXACT_PAIR_ORIGINAL_ROSTER_CHANGED")
        for name in SYMBOLS:
            light=symbols[name]
            if assets.get(light.quoteAssetId)!="USD":
                raise RuntimeError("CAC1_FROZEN_PAIR_QUOTE_ASSET_NOT_USD")
            ids[name]=light.symbolId
            detail=req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[light.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=light.symbolId:
                raise RuntimeError("CAC1_CONTRACT_UNMATCHED")
            c=detail.symbol[0]
            contracts[name]=c
            status[name]={
                "presentCurrent":True,
                "quoteAsset":"USD","minimumWireVolume":int(c.minVolume),
                "tradingMode":int(c.tradingMode),
                "marginBuyEur":None,"marginSellEur":None,
                "historicalTradingPermissionCertified":False}
            if c.minVolume>0:
                margin=req(m.ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account,symbolId=light.symbolId,
                    volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
                if margin.HasField("moneyDigits") and len(margin.margin)==1 and (
                    margin.margin[0].volume==c.minVolume):
                    status[name]["marginBuyEur"]=(
                        margin.margin[0].buyMargin/10**margin.moneyDigits)
                    status[name]["marginSellEur"]=(
                        margin.margin[0].sellMargin/10**margin.moneyDigits)
        for week in range(WEEKS):
            monday=START+timedelta(weeks=week)
            for wd in range(5):
                day=monday+timedelta(days=wd)
                key=day.isoformat()
                rec={"week":week,"bars":{},"barTruncated":{},"quotes":{}}
                original["dates"][key]=rec
                for name in ("US500","SPY.US","NAS100","QQQ.US"):
                    all_bars=[]
                    truncated=False
                    for hh,mm,eh,em in ((13,10,14,0),(15,10,16,0)):
                        begin,end=stamp(day,hh,mm),stamp(day,eh,em)
                        reply=req(m.ProtoOAGetTrendbarsReq(
                            ctidTraderAccountId=account,symbolId=ids[name],
                            period=e.M5,fromTimestamp=begin,toTimestamp=end),
                            m.ProtoOAGetTrendbarsRes,True)
                        if reply is None:
                            truncated=True
                        elif reply.hasMore:
                            truncated=True
                        elif reply.period!=e.M5 or (reply.HasField("symbolId") and
                              reply.symbolId!=ids[name]):
                            raise RuntimeError("CAC1_M5_SOURCE_IDENTITY_MISMATCH")
                        else:
                            all_bars.extend(decode_bars(
                                reply.trendbar,begin-2*M5,end+2*M5,5))
                    rec["bars"][name]=all_bars if not truncated else None
                    rec["barTruncated"][name]=truncated
                # Fixed quotes for ALL scheduled days, not conditioned on future moves.
                # This ensures midday and cash-close share an honest denominator.
                for name in ("SPY.US","QQQ.US","EURUSD"):
                    rec["quotes"][name]={}
                    for label,hh,mm in CLOCKS:
                        rec["quotes"][name][label]=source_pair(
                            name,day,label,hh,mm)
            if week%5==4:
                print("CAC1_SOURCE_ONLY_PROGRESS_WEEKS",week+1,
                      "OF",WEEKS,"ORIGINAL_READONLY_REQUESTS",count,flush=True)
    finally:
        t.close()

    # Custody first. This is raw broker original M5 and tick evidence,
    # and contract messages, sealed BEFORE any post-entry economic outcome.
    private=json.dumps({
        "schema":"MXM_CAC1_PRIVATE_ORIGINAL_BROKER_RESEARCH_SOURCE",
        "run":run,"accountOriginalPepperstoneEurVerified":True,
        "sourceOriginalRequests":originalRequests,
        "originalDecodedSource":original,
        "exactCurrentContracts":status,
        "sourceRequests":count,
        "allScheduledDaysHaveBothWindowQuoteRequests":True},
        separators=(",",":"),sort_keys=True).encode()
    cipher=seal_new(private,recipient,run)
    Path("cac1-original-protected.v2.enc").write_bytes(cipher)

    # Post-entry signal outcomes are scored ONLY AFTER encrypted original
    # evidence has been materialized on disk.
    out=evaluate(original,contracts,status)
    public={
        "schema":"MXM_CAC1_ORIGINAL_CLOSE_VS_MIDDAY_MATCHED_CONDITIONAL_EUR",
        "originalRun":int(run),
        "originalPepperstoneEurAccountVerified":True,
        "protocolSha256":sha256(Path(
            "research/CAC1_US_CASH_CLOSE_FLOW.md").read_bytes()).hexdigest(),
        "originalEncryptedSourceSha256":sha256(cipher).hexdigest(),
        "originalPlaintextSourceSha256":sha256(private).hexdigest(),
        "originalReadOnlyRequestsAfterAuthentication":count,
        "scheduledWeekdaysPerPair":WEEKS*5,
        "clockPairs":("13:35->13:55","15:35->15:55"),
        "originalQuotesAllDaysBeforeOutcomeScoring":True,
        "targets":out,
        "all2026CalendarGloballyExposedDevelopment":True,
        "currentContractExPostOnly":True,
        "historicalTariffAndFillsCertified":False,
        "actualFundedTrades":0,"brokerNetEur":None,
        "nativeCSharpCommonPortfolioNet":None,
        "independentChronologicalValidation":False,
        "continuousIntrabarDrawdownCertified":False,
        "minimum12MonthsCertified":False,
        "cloudNativeCausalInputsConceptuallyAvailable":True,
        "nativeCSharpImplementationValidated":False,
        "ordersSubmitted":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Authenticated historical ETF and index M5 + exact bilateral BID/ASK and signed EURUSD; min-unit current contract 0.5/2bps modeled execution slip, not historical fills or funded EUR300 portfolio."
    }
    Path("cac1-original-public-economic.json").write_text(
        json.dumps(public,indent=2,allow_nan=False)+"\n")
    print("CAC1_ORIGINAL_CLOSE_EUR_RESULT",json.dumps({
        "originalRequests":count,
        "coverage":{k:{"states":v["all"]["states"],
                       "complete":v["all"]["completeComparableDays"],
                       "adverse":v["all"]["adverseCurrentContractNetEur"]}
                    for k,v in out.items()}}),flush=True)


if __name__=="__main__":
    main()

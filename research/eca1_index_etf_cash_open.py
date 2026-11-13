"""ECA1: index CFD vs index-tracking ETF cash-opening discrepancy.

Original-account Pepperstone SCOPE_VIEW read-only, 26 prespecified exposed
weeks, no LIVE/DEMO orders. Causal first-bar signal; original data
sealed BEFORE evaluating any post-entry economic returns.
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
CLOCKS=(("09:40",9,40),("10:05",10,5),("10:30",10,30))
MAX_CALLS=3500
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


def decision(day,index_bars,etf_bars):
    """No feature or quote after 09:35 used to form entry intent."""
    start=stamp(day,9,30)
    idx,etf=bar_at(index_bars,start),bar_at(etf_bars,start)
    if idx is None or etf is None:
        return {"state":"MISSING_COMPLETED_FIRST_CASH_BAR"}
    if min(idx[2],idx[5],etf[2],etf[5])<=0:
        return {"state":"INVALID_PRICE_FEATURE"}
    d_idx=(idx[5]>idx[2])-(idx[5]<idx[2])
    d_etf=(etf[5]>etf[2])-(etf[5]<etf[2])
    if d_idx==0 or d_etf==0 or d_idx==d_etf:
        return {"state":"NO_OPENING_PRICE_DISCOVERY_DISCREPANCY"}
    # 10:00 monitor is ONLY an exit state, never entry selection.
    close_at_935=idx[5]
    path=[bar_at(index_bars,start+M5*i) for i in range(1,6)]
    if any(x is None for x in path):
        return {"state":"SIGNAL_EXIT_MONITOR_BARS_MISSING",
                "side":d_idx,"etfFirstSide":d_etf}
    index_to_1000=path[-1][5]
    invalidated=d_idx*(index_to_1000-close_at_935)<0
    return {"state":"SIGNAL_WITH_CAUSAL_EXIT",
            "side":d_idx,"etfFirstSide":d_etf,
            "invalidation":invalidated,
            "exit":"10:05" if invalidated else "10:30"}


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


def group(rows):
    policies=("eca1","sameSideFixed","ownEtfMomentum","long","short","cash")
    priced=[r for r in rows if r["state"]=="MATCHED_CAUSAL_ECONOMIC_QUOTES"]
    return {
        "calendarDays":len(rows),
        "states":dict(Counter(x["state"] for x in rows)),
        "eventIntents":sum(x["state"] in (
            "SIGNAL_MISSING_ENTRY_OR_EXIT_QUOTE",
            "SIGNAL_MISSING_FX_CONVERSION",
            "SIGNAL_MONITOR_UNKNOWN",
            "SIGNAL_FEE_OR_FINANCING_UNKNOWN",
            "SIGNAL_BENCHMARK_QUOTE_MISSING",
            "MATCHED_CAUSAL_ECONOMIC_QUOTES")
            for x in rows),
        "matchedPriced":len(priced),
        "weeksWithPriced":len({x["week"] for x in priced}),
        "conditionalGrossMidpointBpsMean":mean_field(priced,("policy","eca1",0)),
        "crossingBeforeCostBpsMean":mean_field(priced,("policy","eca1",1)),
        "midpointBpsMeanByPolicy":{
            k:mean_field(priced,("policy",k,0)) for k in policies},
        "crossingBeforeCostBpsMeanByPolicy":{
            k:mean_field(priced,("policy",k,1)) for k in policies},
        "currentContractConditionalEur":{
            scenario:{k:{
                "sum":round(sum(z["money"][scenario][k]["netEur"] for z in priced),6),
                "mean":round(mean_field(priced,("money",scenario,k,"netEur")),6)
                   if priced else None}
                for k in policies}
                for scenario in ("central","adverse")},
        "incrementAdverseVsSameSideFixedEur":round(sum(
            r["money"]["adverse"]["eca1"]["netEur"]-
            r["money"]["adverse"]["sameSideFixed"]["netEur"]
            for r in priced),6),
        "incrementAdverseVsOwnMomentumEur":round(sum(
            r["money"]["adverse"]["eca1"]["netEur"]-
            r["money"]["adverse"]["ownEtfMomentum"]["netEur"]
            for r in priced),6),
    }


def evaluate(original,contracts,status):
    days=original["dates"]
    outcomes={}
    for etf,index in PAIRS.items():
        rows=[]
        for week in range(WEEKS):
            monday=START+timedelta(weeks=week)
            for wd in range(5):
                day=monday+timedelta(days=wd)
                rec=days[day.isoformat()]
                idx=rec["bars"].get(index)
                cash=rec["bars"].get(etf)
                if idx is None or cash is None or rec["barTruncated"].get(index) or rec["barTruncated"].get(etf):
                    rows.append({"week":week,"state":"MISSING_OR_TRUNCATED_BAR_SOURCE"})
                    continue
                signal=decision(day,idx,cash)
                if signal["state"] in (
                    "NO_OPENING_PRICE_DISCOVERY_DISCREPANCY",
                    "MISSING_COMPLETED_FIRST_CASH_BAR","INVALID_PRICE_FEATURE"):
                    rows.append({"week":week,"state":signal["state"]})
                    continue
                if signal["state"]=="SIGNAL_EXIT_MONITOR_BARS_MISSING":
                    rows.append({"week":week,"state":"SIGNAL_MONITOR_UNKNOWN"})
                    continue
                q=rec["quotes"].get(etf,{})
                fx=rec["quotes"].get("EURUSD",{})
                entry=q.get("09:40");exit_q=q.get(signal["exit"])
                fixed=q.get("10:30")
                if entry is None or exit_q is None:
                    rows.append({"week":week,"state":"SIGNAL_MISSING_ENTRY_OR_EXIT_QUOTE"})
                    continue
                if fixed is None:
                    rows.append({"week":week,"state":"SIGNAL_BENCHMARK_QUOTE_MISSING"})
                    continue
                entry_fx=fx.get("09:40")
                exit_fx=fx.get(signal["exit"])
                fixed_fx=fx.get("10:30")
                if entry_fx is None or exit_fx is None or fixed_fx is None:
                    rows.append({"week":week,"state":"SIGNAL_MISSING_FX_CONVERSION"})
                    continue
                sides={"eca1":signal["side"],
                       "sameSideFixed":signal["side"],
                       "ownEtfMomentum":signal["etfFirstSide"],
                       "long":1,"short":-1,"cash":0}
                policy={};money={}
                try:
                    for name,side in sides.items():
                        final=exit_q if name=="eca1" else fixed
                        policy[name]=gross_quote_bps(entry,final,side)
                        if policy[name] is None:
                            raise Unpriced("CROSSING_QUOTE_MISSING")
                    c=contracts[etf]
                    money={}
                    for scenario,slip in (("central",0.5),("adverse",2.0)):
                        money[scenario]={}
                        for name,side in sides.items():
                            final=exit_q if name=="eca1" else fixed
                            final_fx=exit_fx if name=="eca1" else fixed_fx
                            at_exit=stamp(day,10,5) if name=="eca1" and signal["invalidation"] else stamp(day,10,30)
                            if side:
                                no_swap(c,stamp(day,9,40),at_exit)
                            opening=tuple(D(p)/D(100000) for p in entry)
                            ending=tuple(D(p)/D(100000) for p in final)
                            fxopen=tuple(D(p)/D(100000) for p in entry_fx)
                            fxclose=tuple(D(p)/D(100000) for p in final_fx)
                            money[scenario][name]=current_eur(
                                c,opening,ending,fxopen,fxclose,side,slip)
                except (Unpriced,ValueError) as err:
                    rows.append({"week":week,
                        "state":"SIGNAL_FEE_OR_FINANCING_UNKNOWN",
                        "reason":str(err)[:100]})
                    continue
                rows.append({"week":week,
                    "state":"MATCHED_CAUSAL_ECONOMIC_QUOTES",
                    "side":signal["side"],"exit":signal["exit"],
                    "policy":policy,"money":money})
        outcomes[etf]={
            "leader":index,
            "currentMinimumMarginBuyEur":status.get(etf,{}).get("marginBuyEur"),
            "currentMinimumMarginSellEur":status.get(etf,{}).get("marginSellEur"),
            "all":group(rows),
            "first13Weeks":group([z for z in rows if z["week"]<13]),
            "last13Weeks":group([z for z in rows if z["week"]>=13]),
            "instrumentAdmission":False}
    return outcomes


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
            raise RuntimeError("ECA1_ORIGINAL_READ_ONLY_CEILING")
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
            raise RuntimeError("ECA1_ORIGINAL_ACCOUNT_OR_RESPONSE_MISMATCH")
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
            raise RuntimeError("ECA1_NOT_ORIGINAL_PEPPERSTONE_EUR")
        roster=req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        symbols={x.symbolName:x for x in roster.symbol if x.enabled}
        if not all(x in symbols for x in SYMBOLS):
            raise RuntimeError("ECA1_EXACT_PAIR_ORIGINAL_ROSTER_CHANGED")
        for name in SYMBOLS:
            light=symbols[name]
            if assets.get(light.quoteAssetId)!="USD":
                raise RuntimeError("ECA1_FROZEN_PAIR_QUOTE_ASSET_NOT_USD")
            ids[name]=light.symbolId
            detail=req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[light.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=light.symbolId:
                raise RuntimeError("ECA1_CONTRACT_UNMATCHED")
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
                begin,end=stamp(day,9,25),stamp(day,10,40)
                for name in ("US500","SPY.US","NAS100","QQQ.US"):
                    reply=req(m.ProtoOAGetTrendbarsReq(
                        ctidTraderAccountId=account,symbolId=ids[name],
                        period=e.M5,fromTimestamp=begin,toTimestamp=end),
                        m.ProtoOAGetTrendbarsRes,True)
                    if reply is None:
                        rec["bars"][name]=None
                        rec["barTruncated"][name]=False
                    elif reply.hasMore:
                        rec["bars"][name]=None
                        rec["barTruncated"][name]=True
                    elif reply.period!=e.M5 or (reply.HasField("symbolId") and
                          reply.symbolId!=ids[name]):
                        raise RuntimeError("ECA1_M5_SOURCE_IDENTITY_MISMATCH")
                    else:
                        rec["bars"][name]=decode_bars(
                            reply.trendbar,begin-2*M5,end+2*M5,5)
                        rec["barTruncated"][name]=False
                # Use ONLY completed 09:30-09:35 bars to determine whether
                # to acquire any forward quote. No outcome inspection here.
                event_names=[]
                for etf,index in PAIRS.items():
                    i=rec["bars"][index]
                    v=rec["bars"][etf]
                    if i is None or v is None:
                        continue
                    ent=decision(day,i,v)
                    if ent["state"] in ("SIGNAL_WITH_CAUSAL_EXIT",
                                       "SIGNAL_EXIT_MONITOR_BARS_MISSING"):
                        event_names.append(etf)
                if event_names:
                    bar_quote_intents+=len(event_names)
                    rec["quotes"]["EURUSD"]={}
                    for label,hh,mm in CLOCKS:
                        rec["quotes"]["EURUSD"][label]=source_pair(
                            "EURUSD",day,label,hh,mm)
                    for name in event_names:
                        rec["quotes"][name]={}
                        for label,hh,mm in CLOCKS:
                            rec["quotes"][name][label]=source_pair(
                                name,day,label,hh,mm)
            if week%5==4:
                print("ECA1_SOURCE_ONLY_PROGRESS_WEEKS",week+1,
                      "OF",WEEKS,"ORIGINAL_READONLY_REQUESTS",count,flush=True)
    finally:
        t.close()

    # Custody first. This is raw broker original M5 and tick evidence,
    # and contract messages, sealed BEFORE any post-entry economic outcome.
    private=json.dumps({
        "schema":"MXM_ECA1_PRIVATE_ORIGINAL_BROKER_RESEARCH_SOURCE",
        "run":run,"accountOriginalPepperstoneEurVerified":True,
        "sourceOriginalRequests":originalRequests,
        "originalDecodedSource":original,
        "exactCurrentContracts":status,
        "sourceRequests":count,
        "barsFirstOnlyUsedToChooseFutureQuoteQueries":True},
        separators=(",",":"),sort_keys=True).encode()
    cipher=seal_new(private,recipient,run)
    Path("eca1-original-protected.v2.enc").write_bytes(cipher)

    # Post-entry signal outcomes are scored ONLY AFTER encrypted original
    # evidence has been materialized on disk.
    out=evaluate(original,contracts,status)
    public={
        "schema":"MXM_ECA1_ORIGINAL_CASH_OPEN_INDEX_ETF_GROSS_AND_CONDITIONAL_EUR",
        "originalRun":int(run),
        "originalPepperstoneEurAccountVerified":True,
        "protocolSha256":sha256(Path(
            "research/ECA1_INDEX_ETF_OPENING_DISCREPANCY.md").read_bytes()).hexdigest(),
        "originalEncryptedSourceSha256":sha256(cipher).hexdigest(),
        "originalPlaintextSourceSha256":sha256(private).hexdigest(),
        "originalReadOnlyRequestsAfterAuthentication":count,
        "scheduledWeekdaysPerPair":WEEKS*5,
        "sourceIntentEventsBeforeOutcomeScoring":bar_quote_intents,
        "targets":out,
        "sourceNotFromNewsHttpOrMarketDepth":True,
        "all2026CalendarGloballyExposedDevelopment":True,
        "currentContractExPostOnly":True,
        "actualFundedTrades":0,"brokerNetEur":None,
        "nativeCSharpCommonPortfolioNet":None,
        "independentChronologicalValidation":False,
        "continuousIntrabarDrawdownCertified":False,
        "minimum12MonthsCertified":False,
        "cloudNativeCausalInputsConceptuallyAvailable":True,
        "nativeCSharpImplementationValidated":False,
        "ordersSubmitted":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Causal M5 opening disagreement and sampled authenticated BID/ASK + signed EURUSD quotes; broker tariff observed later, 0.5/2bps model slippage, hypothetical entry/exit. Not actual fills, 300EUR financed ledger, or independent chronological proof."
    }
    Path("eca1-original-public-economic.json").write_text(
        json.dumps(public,indent=2,allow_nan=False)+"\n")
    print("ECA1_ORIGINAL_ECONOMIC_SCREEN",json.dumps({
        "readOnlyRequests":count,"barOnlyCausalIntents":bar_quote_intents,
        "coverage":{k:{"all":v["all"]["states"],
                       "priced":v["all"]["matchedPriced"],
                       "adverse":v["all"]["currentContractConditionalEur"]["adverse"]["eca1"]}
                    for k,v in out.items()}}),flush=True)


if __name__=="__main__":
    main()

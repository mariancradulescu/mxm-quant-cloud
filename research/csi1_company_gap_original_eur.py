"""CSI1: AMD-specific overnight innovation and continuation vs Intel/NAS100 controls.

Original-account Pepperstone read-only; globally exposed historic calendar.
Requires past four same weekdays and exact original relative AMD/peer marks.
Sealed broker source before scoring.
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
START=date(2025,10,6)
WEEKS=56
M5=300000
PAIRS={"AMD.US":"NAS100"}
SYMBOLS=("AMD.US","INTC.US","NAS100","EURUSD")
CLOCKS=(("09:40",9,40),("10:20",10,20),("11:00",11,0))
MAX_CALLS=6000
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



def sign(v):
    return (v>0)-(v<0)

def weekday_previous(day):
    return day-timedelta(days=3 if day.weekday()==0 else 1)

def gap_facts(day,records):
    rec=records.get(day.isoformat())
    prior=records.get(weekday_previous(day).isoformat())
    if rec is None or prior is None:
        return None
    overnight={};bodies={}
    for name in ("AMD.US","INTC.US","NAS100"):
        rows=rec["bars"].get(name)
        prev=prior["bars"].get(name)
        if rows is None or prev is None:
            return None
        early=bar_at(rows,stamp(day,9,30))
        old=bar_at(prev,stamp(weekday_previous(day),15,50))
        if early is None or old is None or min(early[2],early[5],old[5])<=0:
            return None
        overnight[name]=log(early[5]/old[5])
        bodies[name]=log(early[5]/early[2])
    dp=overnight["AMD.US"]-overnight["INTC.US"]
    dn=overnight["AMD.US"]-overnight["NAS100"]
    bp=bodies["AMD.US"]-bodies["INTC.US"]
    bn=bodies["AMD.US"]-bodies["NAS100"]
    return {"dP":dp,"dN":dn,"bP":bp,"bN":bn,
            "surprise":min(abs(dp),abs(dn)),
            "ownSide":sign(bodies["AMD.US"])}


def causal_event(day,records):
    """No outcome bars after 09:35 may alter event intent or direction."""
    now=gap_facts(day,records)
    if now is None:
        return {"state":"UNKNOWN_OVERNIGHT_OR_OPEN"}
    history=[]
    for k in range(1,5):
        old=gap_facts(day-timedelta(weeks=k),records)
        if old is None:
            return {"state":"UNKNOWN_FOUR_WEEK_REFERENCE"}
        history.append(old["surprise"])
    signs=[sign(now[k]) for k in ("dP","dN","bP","bN")]
    if 0 in signs or any(x!=signs[0] for x in signs):
        return {"state":"ABSTAIN_NO_FIRM_INFORMATION_CONCORDANCE"}
    if not now["surprise"]>max(history):
        return {"state":"ABSTAIN_NOT_UNUSUAL_RELATIVE_GAP"}
    return {"state":"CAUSAL_FIRM_SURPRISE","side":signs[0],
            "ownSide":now["ownSide"]}


def exit_decision(day,records,side):
    rec=records.get(day.isoformat())
    if rec is None:return None
    vals={}
    for name in ("AMD.US","INTC.US","NAS100"):
        rows=rec["bars"].get(name)
        if rows is None:return None
        initial=bar_at(rows,stamp(day,9,30))
        monitor=bar_at(rows,stamp(day,10,10))
        if initial is None or monitor is None or min(initial[5],monitor[5])<=0:
            return None
        vals[name]=log(monitor[5]/initial[5])
    bad=any(side*(vals["AMD.US"]-vals[peer])<0 for peer in ("INTC.US","NAS100"))
    return "10:20" if bad else "11:00"


def single_net(c,quotes,fx,side,exit_at,slip,day):
    if not side:return 0.0
    entry=quotes["09:40"];finish=quotes[exit_at]
    fx_in=fx["09:40"];fx_out=fx[exit_at]
    no_swap(c,stamp(day,9,40),
        stamp(day,10,20) if exit_at=="10:20" else stamp(day,11,0))
    return current_eur(
        c,tuple(D(p)/D(100000) for p in entry),
        tuple(D(p)/D(100000) for p in finish),
        tuple(D(p)/D(100000) for p in fx_in),
        tuple(D(p)/D(100000) for p in fx_out),
        side,slip)["netEur"]


def summarize(rows):
    matched=[r for r in rows if r["state"]=="MATCHED_ORIGINAL_QUOTES_CURRENT_CONTRACT_EUR"]
    names=("primary","sameSideFixed","ownMomentum","long","short","oppositeFalsifier","cash")
    out={
        "calendarDays":len(rows),
        "states":dict(Counter(r["state"] for r in rows)),
        "causalIntents":sum(r.get("side",0)!=0 for r in rows),
        "pricedEvents":len(matched),
        "pricedWeeks":len({r["week"] for r in matched}),
        "fundedTrades":0,"independentConfirmation":False}
    for scenario in ("central","adverse"):
        result={k:round(sum(r["money"][scenario][k] for r in matched),6)
                for k in names}
        out[scenario+"CurrentContractConditionalNetEur"]=result
        out[scenario+"PrimaryVsFixedEur"]=round(result["primary"]-result["sameSideFixed"],6)
        out[scenario+"PrimaryVsOwnMomentumEur"]=round(result["primary"]-result["ownMomentum"],6)
        out[scenario+"PrimaryVsCashEur"]=result["primary"]
    return out


def evaluate(original,contracts,status):
    records=original["dates"]
    rows=[]
    for wi in range(4,WEEKS):
        monday=START+timedelta(weeks=wi)
        for wd in range(5):
            day=monday+timedelta(days=wd)
            feature=causal_event(day,records)
            row={"week":wi-4,"day":day.isoformat(),
                 "state":feature["state"],"side":feature.get("side",0)}
            if feature["state"]!="CAUSAL_FIRM_SURPRISE":
                rows.append(row);continue
            finish=exit_decision(day,records,feature["side"])
            if finish is None:
                rows.append({**row,"state":"UNKNOWN_EXIT_MONITOR_BARS"});continue
            rec=records[day.isoformat()]
            quoted=rec["quotes"].get("AMD.US",{})
            fx=rec["quotes"].get("EURUSD",{})
            if any(quoted.get(label) is None for label,_,_ in CLOCKS):
                rows.append({**row,"state":"UNKNOWN_BID_ASK_AMD"});continue
            if any(fx.get(label) is None for label,_,_ in CLOCKS):
                rows.append({**row,"state":"UNKNOWN_BID_ASK_FX"});continue
            md=status["AMD.US"]
            if (md.get("marginBuyEur") is None or md.get("marginSellEur") is None or
                 max(md["marginBuyEur"],md["marginSellEur"])>=300 or
                 min(md["marginBuyEur"],md["marginSellEur"])<0):
                rows.append({**row,"state":"UNKNOWN_EUR300_MIN_MARGIN"});continue
            policies={
                "primary":(feature["side"],finish),
                "sameSideFixed":(feature["side"],"11:00"),
                "ownMomentum":(feature["ownSide"],"11:00"),
                "long":(1,"11:00"),
                "short":(-1,"11:00"),
                "oppositeFalsifier":(-feature["side"],"11:00"),
                "cash":(0,"11:00")}
            try:
                money={}
                for scen,slip in (("central",0.5),("adverse",2.0)):
                    money[scen]={}
                    for key,(side,last) in policies.items():
                        money[scen][key]=single_net(
                            contracts["AMD.US"],quoted,fx,side,last,slip,day)
            except (Unpriced,ValueError,TypeError,KeyError,ArithmeticError) as err:
                rows.append({**row,"state":"UNKNOWN_CONTRACT_EUR_COST_OR_SWAP",
                             "reason":str(err)[:90]})
                continue
            rows.append({**row,"state":"MATCHED_ORIGINAL_QUOTES_CURRENT_CONTRACT_EUR",
                         "exit":finish,"money":money})
    return {
       "AMD.US":{
           "currentMinimumMarginBuyEur":status["AMD.US"].get("marginBuyEur"),
           "currentMinimumMarginSellEur":status["AMD.US"].get("marginSellEur"),
           "all":summarize(rows),
           "first26Weeks":summarize([r for r in rows if r["week"]<26]),
           "last26Weeks":summarize([r for r in rows if r["week"]>=26]),
           "exactRuleEconomicVerdict":"NOT_QUALIFIED_REQUIRES_EXPLICIT_MATCHED_ADVERSE_EUR_GATE",
           "nativeCSharpPortfolioNetEur":None}
    }

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
            raise RuntimeError("CSI1_ORIGINAL_READ_ONLY_CEILING")
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
            raise RuntimeError("CSI1_ORIGINAL_ACCOUNT_OR_RESPONSE_MISMATCH")
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
            raise RuntimeError("CSI1_NOT_ORIGINAL_PEPPERSTONE_EUR")
        roster=req(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        symbols={x.symbolName:x for x in roster.symbol if x.enabled}
        if not all(x in symbols for x in SYMBOLS):
            raise RuntimeError("CSI1_EXACT_PAIR_ORIGINAL_ROSTER_CHANGED")
        for name in SYMBOLS:
            light=symbols[name]
            if assets.get(light.quoteAssetId)!="USD":
                raise RuntimeError("CSI1_FROZEN_PAIR_QUOTE_ASSET_NOT_USD")
            ids[name]=light.symbolId
            detail=req(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[light.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=light.symbolId:
                raise RuntimeError("CSI1_CONTRACT_UNMATCHED")
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

        # One prior Friday anchor for the first Monday warmup gap, no scoring.
        prior=START-timedelta(days=3)
        original["dates"][prior.isoformat()]={"week":-1,"bars":{},"barTruncated":{},"quotes":{}}
        for name in ("AMD.US","INTC.US","NAS100"):
            st,en=stamp(prior,15,50),stamp(prior,16,5)
            reply=req(m.ProtoOAGetTrendbarsReq(
                ctidTraderAccountId=account,symbolId=ids[name],
                period=e.M5,fromTimestamp=st,toTimestamp=en),
                m.ProtoOAGetTrendbarsRes,True)
            if reply is None or reply.hasMore:
                original["dates"][prior.isoformat()]["bars"][name]=None
                original["dates"][prior.isoformat()]["barTruncated"][name]=True
            elif reply.period!=e.M5 or (reply.HasField("symbolId") and reply.symbolId!=ids[name]):
                raise RuntimeError("CSI1_PRIOR_ANCHOR_SOURCE_IDENTITY")
            else:
                original["dates"][prior.isoformat()]["bars"][name]=decode_bars(
                    reply.trendbar,st-2*M5,en+2*M5,5)
                original["dates"][prior.isoformat()]["barTruncated"][name]=False
        for week in range(WEEKS):
            monday=START+timedelta(weeks=week)
            for wd in range(5):
                day=monday+timedelta(days=wd)
                key=day.isoformat()
                rec={"week":week,"bars":{},"barTruncated":{},"quotes":{}}
                original["dates"][key]=rec
                for name in ("AMD.US","INTC.US","NAS100"):
                    allbars=[]
                    incomplete=False
                    for hh,mm,eh,em in ((9,25,11,10),(15,50,16,5)):
                        st,en=stamp(day,hh,mm),stamp(day,eh,em)
                        reply=req(m.ProtoOAGetTrendbarsReq(
                            ctidTraderAccountId=account,symbolId=ids[name],
                            period=e.M5,fromTimestamp=st,toTimestamp=en),
                            m.ProtoOAGetTrendbarsRes,True)
                        if reply is None or reply.hasMore:
                            incomplete=True
                        elif reply.period!=e.M5 or (reply.HasField("symbolId") and
                              reply.symbolId!=ids[name]):
                            raise RuntimeError("CSI1_WRONG_M5_IDENTITY")
                        else:
                            allbars.extend(decode_bars(
                                reply.trendbar,st-2*M5,en+2*M5,5))
                    rec["bars"][name]=None if incomplete else allbars
                    rec["barTruncated"][name]=incomplete
                # Only fully matured previous-week features and 09:35
                # CLOSED event cause event-specific future quote requests.
                if week>=4:
                    causal=causal_event(day,original["dates"])
                    if causal["state"]=="CAUSAL_FIRM_SURPRISE":
                        bar_quote_intents+=1
                        for name in ("AMD.US","EURUSD"):
                            rec["quotes"][name]={}
                            for label,hh,mm in CLOCKS:
                                rec["quotes"][name][label]=source_pair(
                                    name,day,label,hh,mm)
            if week%5==4:
                print("CSI1_SOURCE_ONLY_PROGRESS_WEEKS",week+1,
                      "OF",WEEKS,"ORIGINAL_READONLY_REQUESTS",count,flush=True)
    finally:
        t.close()

    # Custody first. This is raw broker original M5 and tick evidence,
    # and contract messages, sealed BEFORE any post-entry economic outcome.
    private=json.dumps({
        "schema":"MXM_CSI1_PRIVATE_ORIGINAL_BROKER_RESEARCH_SOURCE",
        "run":run,"accountOriginalPepperstoneEurVerified":True,
        "sourceOriginalRequests":originalRequests,
        "originalDecodedSource":original,
        "exactCurrentContracts":status,
        "sourceRequests":count,
        "sourceEventQuotesChosenOnlyByCompleted0935AndFourWeekPast":True},
        separators=(",",":"),sort_keys=True).encode()
    cipher=seal_new(private,recipient,run)
    Path("csi1-original-protected.v2.enc").write_bytes(cipher)

    # Post-entry signal outcomes are scored ONLY AFTER encrypted original
    # evidence has been materialized on disk.
    out=evaluate(original,contracts,status)
    report=out["AMD.US"]
    first=report["first26Weeks"]["adverseCurrentContractConditionalNetEur"]
    last=report["last26Weeks"]["adverseCurrentContractConditionalNetEur"]
    all_=report["all"]["adverseCurrentContractConditionalNetEur"]
    positive=lambda d: d["primary"]>0
    incremental=lambda d: d["primary"]>max(d["sameSideFixed"],d["ownMomentum"],
                                          d["long"],d["short"],d["cash"])
    enough=all(x["pricedEvents"]>0 for x in (report["first26Weeks"],report["last26Weeks"]))
    passed=enough and all(positive(d) and incremental(d) for d in (first,last,all_))
    verdict="DEVELOPMENT_ONLY_POSSIBLE_FURTHER_NATIVE_RESEARCH" if passed else (
        "INSUFFICIENT_COST_COVERAGE" if not enough else
        "REJECT_EXACT_CSI1_NO_ROBUST_ABSOLUTE_INCREMENTAL_ADVERSE_NET")
    report["exactRuleEconomicVerdict"]=verdict
    public={
        "schema":"MXM_CSI1_ORIGINAL_FIRM_OVERNIGHT_EUR_DEVELOPMENT",
        "originalRun":int(run),"originalPepperstoneEurAccountVerified":True,
        "protocolSha256":sha256(Path(
            "research/CSI1_FIRM_RELATIVE_OVERNIGHT_DIFFUSION.md").read_bytes()).hexdigest(),
        "originalEncryptedSourceSha256":sha256(cipher).hexdigest(),
        "originalPlaintextSourceSha256":sha256(private).hexdigest(),
        "originalReadOnlyRequestsAfterAuthentication":count,
        "fixedPriceTarget":"AMD.US","fixedPriceControls":["INTC.US","NAS100"],
        "scheduledEvaluationDays":52*5,
        "warmupPreviousWeeks":4,"causalOriginalQuoteIntents":bar_quote_intents,
        "targets":out,"verdict":verdict,
        "all2025And2026GloballyExposedDevelopment":True,
        "currentContractExPostOnly":True,
        "historicalTariffAndFillsCertified":False,
        "originalQuoteCollectionOnFutureOutcome":False,
        "actualFundedTrades":0,"brokerNetEur":None,
        "nativeCSharpCommonPortfolioNet":None,
        "independentChronologicalValidation":False,
        "continuousIntrabarDrawdownCertified":False,
        "minimum12MonthsCertified":False,
        "ordersSubmitted":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Only original broker M5, AMD bid/ask and signed FX; 0.5/2.0bps slippage modeled. Conditional unmatched funding and historical tariffs unknown."
    }
    Path("csi1-original-public-economic.json").write_text(
        json.dumps(public,indent=2,allow_nan=False)+"\n")
    print("CSI1_ORIGINAL_EUR_RESULT",json.dumps({
        "originalRequests":count,
        "intent":bar_quote_intents,
        "verdict":verdict,
        "coverage":report["all"]["states"],
        "priced":report["all"]["pricedEvents"],
        "adverse":all_}),flush=True)


if __name__=="__main__":
    main()

"""BWR1: original Pepperstone Brent/WTI failed grade-basis dislocation.

52 weeks / 260 frozen US calendar weekdays, one single min-volume two-leg
EUR300 book. Authenticate SCOPE_VIEW read-only; seal raw original source
BEFORE any monitor/exit/financial outcome evaluation. Conditional NET EUR
is NOT original historical execution or continuous drawdown certification.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import date,datetime,time,timedelta
from decimal import Decimal as D
from hashlib import sha256
import json,os
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars,decode_side
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody_new import checked_public
from .custody import seal_new
from .rne1_eur_protected_exact_reconciliation import current_eur,no_swap,Unpriced

START=date(2025,11,3)
WEEKS=52
NY=ZoneInfo("America/New_York")
M5=300000
SCALE=D(100000)
MARKETS=("SpotBrent","SpotCrude")
ALL=("SpotBrent","SpotCrude","EURUSD")
CLOCKS=(("10:05",10,5),("10:40",10,40),("11:35",11,35))
POLICIES=("adaptive","fixedSameSide","alwaysLongBasis","alwaysShortBasis","cash")
MAX_CALLS=6200
MAX_AGE=20000


def stamp(day,hh,mm):
    return int(datetime.combine(day,time(hh,mm),NY).timestamp()*1000)


def pairs(bids,asks,at):
    def recent(rows):
        v=[x for x in rows if x[0]<=at and x[1]>0]
        if not v:return None
        z=max(v,key=lambda y:y[0])
        return z if at-z[0]<=MAX_AGE else None
    bid,ask=recent(bids),recent(asks)
    return [bid[1],ask[1]] if (bid and ask and bid[1]<=ask[1]) else None


def basis(bars,at):
    values=[]
    for name in MARKETS:
        close=bars[name].get(at)
        if close is None or close<=0:return None
        values.append(D(close)/SCALE)
    return values[0]-values[1]


def first_signal(day,bars):
    """Only original M5 completed marks available at 10:00 ET."""
    # Do not rely on endpoints alone. All M5 clocks between the
    # preceding physical basis window and the decision must be complete.
    full=[basis(bars,stamp(day,8,30)+i*M5) for i in range(19)]
    if any(x is None for x in full):
        return {"state":"INCOMPLETE_CAUSAL_M5_BASIS_SOURCE"}
    ref=full[:13]
    at945,at1000=full[15],full[18]
    hi,lo=max(ref),min(ref)
    if not lo<=at1000<=hi:
        return {"state":"NO_REJECTED_BASIS_SWEEP"}
    if at945>hi:
        return {"state":"CAUSAL_REJECTED_BASIS","side":-1,
                "upper":str(hi),"lower":str(lo)}
    if at945<lo:
        return {"state":"CAUSAL_REJECTED_BASIS","side":1,
                "upper":str(hi),"lower":str(lo)}
    return {"state":"NO_REJECTED_BASIS_SWEEP"}


def exit_policy(day,bars,sig):
    """10:35 completed bar can ONLY affect an already admitted 10:00 intent."""
    observed=basis(bars,stamp(day,10,35))
    if observed is None:
        return {"state":"INCOMPLETE_1035_EXIT_MONITOR"}
    old_extreme=D(sig["upper"] if sig["side"]<0 else sig["lower"])
    invalid=(observed>old_extreme if sig["side"]<0 else observed<old_extreme)
    return {"state":"EXIT_MONITORED","exit":"10:40" if invalid else "11:35",
            "invalidated":invalid}


def monetary(c,entry,final,fx_in,fx_out,side,slip,day,exit_key):
    if side==0:
        return {"grossEur":0.0,"netEur":0.0,"feesEur":0.0,
                "modeledSlippageEur":0.0,"pnlConversionEur":0.0}
    for q in (entry,final,fx_in,fx_out):
        if q is None or len(q)!=2 or q[0]<=0 or q[0]>q[1]:
            raise Unpriced("BWR1_MISSING_GENUINE_ASOF_PAIR")
    h,mi=(int(v) for v in exit_key.split(":"))
    no_swap(c,stamp(day,10,5),stamp(day,h,mi))
    return current_eur(c,
        tuple(D(k)/SCALE for k in entry),
        tuple(D(k)/SCALE for k in final),
        tuple(D(k)/SCALE for k in fx_in),
        tuple(D(k)/SCALE for k in fx_out),side,slip)


def book(day,rec,terms,margin):
    sig=first_signal(day,rec["bars"])
    if sig["state"]!="CAUSAL_REJECTED_BASIS":
        return {"state":sig["state"]}
    exit_=exit_policy(day,rec["bars"],sig)
    if exit_["state"]!="EXIT_MONITORED":
        return {"state":exit_["state"]}
    p=rec["quotes"]
    for name in ALL:
        if name not in p or any(p[name].get(k) is None
                                for k,_,_ in CLOCKS):
            return {"state":"BASIS_EVENT_SOURCE_QUOTE_OR_FX_MISSING"}
    directions={
        "adaptive":sig["side"],
        "fixedSameSide":sig["side"],
        "alwaysLongBasis":1,
        "alwaysShortBasis":-1,
        "cash":0}
    current_margin_buy={}
    current_margin_sell={}
    for k in MARKETS:
        z=margin[k]
        if z["currentMarginBuyEur"] is None or z["currentMarginSellEur"] is None:
            return {"state":"CURRENT_MIN_VOLUME_MARGIN_UNKNOWN"}
        if z["currentMarginBuyEur"]<=0 or z["currentMarginSellEur"]<=0:
            return {"state":"CURRENT_MIN_VOLUME_MARGIN_UNKNOWN"}
        current_margin_buy[k]=z["currentMarginBuyEur"]
        current_margin_sell[k]=z["currentMarginSellEur"]

    net={};gross={};fees={};slippage={};pnlconv={};margins={}
    try:
        for policy,side in directions.items():
            at=exit_["exit"] if policy=="adaptive" else "11:35"
            # long Brent short WTI or vice versa. In no-event cash do not
            # invent trades/fees/margin.
            legside={"SpotBrent":side,"SpotCrude":-side}
            margins[policy]=sum((
                current_margin_buy[k] if v>0 else current_margin_sell[k])
                for k,v in legside.items() if v)
            for scenario,slip in (("central",0.5),("adverse",2.0)):
                legs=[monetary(terms[k],p[k]["10:05"],p[k][at],
                               p["EURUSD"]["10:05"],p["EURUSD"][at],
                               v,slip,day,at)
                      for k,v in legside.items()]
                def total(k):return sum(v[k] for v in legs)
                net.setdefault(scenario,{})[policy]=total("netEur")
                gross.setdefault(scenario,{})[policy]=total("grossEur")
                fees.setdefault(scenario,{})[policy]=total("feesEur")
                slippage.setdefault(scenario,{})[policy]=total("modeledSlippageEur")
                pnlconv.setdefault(scenario,{})[policy]=total("pnlConversionEur")
    except (Unpriced,ValueError) as exc:
        return {"state":"CURRENT_TARIFF_OR_EXECUTION_UNKNOWN",
                "reason":str(exc)[:110]}
    if margins["adaptive"]>=300:
        return {"state":"CURRENT_PAIR_MINIMUM_MARGIN_UNDERFUNDED",
                "pairMinMarginEur":margins["adaptive"]}
    return {"state":"PAIRED_CONDITIONAL_EUR_EVALUATED",
            "side":sig["side"],"exit":exit_["exit"],
            "maxCurrentPairMarginEur":max(margins.values()),
            "adaptiveCurrentPairMarginEur":margins["adaptive"],
            "net":net,"gross":gross,"fees":fees,
            "slippage":slippage,"pnlConversion":pnlconv}


def summary(rows):
    priced=[x for x in rows if x["state"]=="PAIRED_CONDITIONAL_EUR_EVALUATED"]
    events=[x for x in rows if x["state"] in (
        "PAIRED_CONDITIONAL_EUR_EVALUATED",
        "BASIS_EVENT_SOURCE_QUOTE_OR_FX_MISSING",
        "INCOMPLETE_1035_EXIT_MONITOR",
        "CURRENT_MIN_VOLUME_MARGIN_UNKNOWN",
        "CURRENT_PAIR_MINIMUM_MARGIN_UNDERFUNDED",
        "CURRENT_TARIFF_OR_EXECUTION_UNKNOWN")]
    money={scenario:{
        policy:{
            "conditionalNetEurSum":round(sum(x["net"][scenario][policy] for x in priced),6),
            "conditionalGrossAfterBidAskEurSum":round(sum(x["gross"][scenario][policy] for x in priced),6),
            "currentTariffCommissionEurSum":round(sum(x["fees"][scenario][policy] for x in priced),6),
            "modeledSlippageEurSum":round(sum(x["slippage"][scenario][policy] for x in priced),6),
            "currentPnlConversionEurSum":round(sum(x["pnlConversion"][scenario][policy] for x in priced),6)}
            for policy in POLICIES} for scenario in ("central","adverse")}
    return {"scheduledDays":len(rows),
            "states":dict(Counter(x["state"] for x in rows)),
            "basisSweepIntents":len(events),
            "pairedCompleteEurPriced":len(priced),
            "pricedWeeks":len({r["week"] for r in priced}),
            "currentPairMarginEurMaxPriced":round(max(
                (x["maxCurrentPairMarginEur"] for x in priced),default=0),6),
            "directionLongBrentEvents":sum(x["side"]==1 for x in priced),
            "directionShortBrentEvents":sum(x["side"]==-1 for x in priced),
            "exitsEarly":sum(x["exit"]=="10:40" for x in priced),
            "exitsAtCeiling":sum(x["exit"]=="11:35" for x in priced),
            "money":money,
            "adverseIncrementVsFixedEur":round(sum(
                x["net"]["adverse"]["adaptive"]-
                x["net"]["adverse"]["fixedSameSide"]
                for x in priced),6),
            "conditionalPricedSubsetEur300FinalCashAdverse":round(
                300+sum(x["net"]["adverse"]["adaptive"] for x in priced),6)
        }


def financial(tape,contracts,margins):
    recs=[]
    for w in range(WEEKS):
        for wd in range(5):
            d=START+timedelta(weeks=w,days=wd)
            v=tape[d.isoformat()]
            recs.append({"week":w,**book(d,v,contracts,margins)})
    a=summary(recs)
    early=summary([v for v in recs if v["week"]<26])
    late=summary([v for v in recs if v["week"]>=26])
    return {
        "all52Weeks":a,"first26Weeks":early,"last26Weeks":late,
        "currentContractConditionalNotHistoricTariff":True,
        "fullFundedNativeCSharpBook":False,
        "continuousFloatingDrawdownCertified":False,
        "chronologicalIndependentConfirmation":False,
        "candidateEconomicGate":(
            a["pairedCompleteEurPriced"]>=12
            and early["pairedCompleteEurPriced"]>=5
            and late["pairedCompleteEurPriced"]>=5
            and all(z["money"]["adverse"]["adaptive"]["conditionalNetEurSum"]>0
                    and z["money"]["adverse"]["adaptive"]["conditionalNetEurSum"]>
                        z["money"]["adverse"]["fixedSameSide"]["conditionalNetEurSum"]
                    and z["money"]["adverse"]["adaptive"]["conditionalNetEurSum"]>
                        z["money"]["adverse"]["alwaysLongBasis"]["conditionalNetEurSum"]
                    and z["money"]["adverse"]["adaptive"]["conditionalNetEurSum"]>
                        z["money"]["adverse"]["alwaysShortBasis"]["conditionalNetEurSum"]
                    for z in (a,early,late)))}


def main():
    rid=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),rid)
    tr=StdlibCTraderTransport()
    account=None
    calls=[]
    count=0
    tape={}
    terms={}
    margins={}
    ids={}

    def request(q,klass,empty=False):
        nonlocal count
        if count>=MAX_CALLS:raise RuntimeError("BWR1_ORIGINAL_READONLY_LIMIT")
        require_read_only_request(q)
        answer=tr.request(q)
        count+=1
        if (empty and type(answer) is m.ProtoOAErrorRes and
            answer.errorCode=="NO_QUOTES" and
            answer.ctidTraderAccountId==account):
            out=None
        elif (type(answer) is klass and answer.IsInitialized()
              and answer.ctidTraderAccountId==account):
            out=answer
        else:raise RuntimeError("BWR1_ORIGINAL_BROKER_RESPONSE_MISMATCH")
        calls.append({"requestType":type(q).__name__,
                      "request":base64.b64encode(q.SerializeToString()).decode(),
                      "responseType":type(answer).__name__,
                      "response":base64.b64encode(answer.SerializeToString()).decode()})
        return out

    def quote(name,day,hh,mm):
        at=stamp(day,hh,mm)
        rows=[];incomplete=False
        for side in (e.BID,e.ASK):
            z=request(m.ProtoOAGetTickDataReq(
                ctidTraderAccountId=account,symbolId=ids[name],
                type=side,fromTimestamp=at-60000,toTimestamp=at),
                m.ProtoOAGetTickDataRes,True)
            if z is None:
                rows.append([])
            elif z.hasMore:
                incomplete=True
                rows.append([])
            else:
                rows.append(decode_side(z.tickData,at-60000,at))
        return None if incomplete else pairs(*rows,at)

    try:
        account=authenticate(tr)
        trader=request(m.ProtoOATraderReq(ctidTraderAccountId=account),
                       m.ProtoOATraderRes)
        assets=request(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                       m.ProtoOAAssetListRes)
        currencies={i.assetId:i.name for i in assets.asset}
        if ("pepperstone" not in trader.trader.brokerName.casefold() or
            currencies.get(trader.trader.depositAssetId)!="EUR"):
            raise RuntimeError("BWR1_NOT_ORIGINAL_PEPPERSTONE_EUR_ACCOUNT")
        roster=request(m.ProtoOASymbolsListReq(
            ctidTraderAccountId=account,includeArchivedSymbols=False),
            m.ProtoOASymbolsListRes)
        visible={i.symbolName:i for i in roster.symbol if i.enabled}
        if not all(n in visible for n in ALL):
            raise RuntimeError("BWR1_ORIGINAL_FROZEN_MARKET_NOT_ENABLED")
        for name in ALL:
            small=visible[name]
            if currencies.get(small.quoteAssetId)!="USD":
                raise RuntimeError("BWR1_QUOTE_ASSET_NOT_USD")
            ids[name]=small.symbolId
            detail=request(m.ProtoOASymbolByIdReq(
                ctidTraderAccountId=account,symbolId=[small.symbolId]),
                m.ProtoOASymbolByIdRes)
            if len(detail.symbol)!=1 or detail.symbol[0].symbolId!=ids[name]:
                raise RuntimeError("BWR1_ORIGINAL_CONTRACT_UNMATCHED")
            c=detail.symbol[0]
            terms[name]=c
            margins[name]={"minimumWireVolume":int(c.minVolume),
                           "currentMarginBuyEur":None,
                           "currentMarginSellEur":None,
                           "onlyCurrentTerms":True}
            if c.minVolume>0:
                mrg=request(m.ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account,symbolId=ids[name],
                    volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
                if mrg.HasField("moneyDigits") and len(mrg.margin)==1 and (
                        mrg.margin[0].volume==c.minVolume):
                    margins[name]["currentMarginBuyEur"]=(
                        mrg.margin[0].buyMargin/10**mrg.moneyDigits)
                    margins[name]["currentMarginSellEur"]=(
                        mrg.margin[0].sellMargin/10**mrg.moneyDigits)
        for week in range(WEEKS):
            monday=START+timedelta(weeks=week)
            for wd in range(5):
                day=monday+timedelta(days=wd)
                rec={"week":week,"bars":{},"quotes":{},"sourceStates":{}}
                tape[day.isoformat()]=rec
                begin,end=stamp(day,8,25),stamp(day,11,40)
                for name in MARKETS:
                    ans=request(m.ProtoOAGetTrendbarsReq(
                        ctidTraderAccountId=account,symbolId=ids[name],
                        period=e.M5,fromTimestamp=begin,toTimestamp=end),
                        m.ProtoOAGetTrendbarsRes,True)
                    if ans is None or ans.hasMore:
                        rec["bars"][name]={}
                        rec["sourceStates"][name]=(
                            "MISSING" if ans is None else "TRUNCATED")
                    elif ans.period!=e.M5 or (ans.HasField("symbolId")
                          and ans.symbolId!=ids[name]):
                        raise RuntimeError("BWR1_ORIGINAL_M5_SOURCE_IDENTITY")
                    else:
                        decoded=decode_bars(ans.trendbar,begin-2*M5,end+2*M5,5)
                        rec["bars"][name]={q[1]:q[5] for q in decoded}
                        rec["sourceStates"][name]="M5_ORIGINAL"
                # ONLY causal 10:00-and-earlier feature is inspected here.
                decision=first_signal(day,rec["bars"])
                if decision["state"]=="CAUSAL_REJECTED_BASIS":
                    rec["quotes"]={n:{} for n in ALL}
                    for label,hh,mm in CLOCKS:
                        for name in ALL:
                            rec["quotes"][name][label]=quote(name,day,hh,mm)
            if week%10==9:
                print("BWR1_CAPTURE_PROGRESS_WEEKS",week+1,"/",WEEKS,
                      "ORIGINAL_READONLY_CALLS",count,flush=True)
    finally:
        tr.close()
    # Preserve unmodified raw authenticated response data before scoring.
    private=json.dumps({
        "schema":"MXM_BWR1_ORIGINAL_BRENT_WTI_CFD_SOURCE_PRIVATE",
        "run":rid,
        "originalPepperstoneEurAccountBound":True,
        "originalBrokerProtobuf":calls,
        "decodedOriginalBarsAndQuotes":tape,
        "currentContractSnapshot":margins,
        "postEntryEconomicScoringNotStarted":True,
        "readonlyCallsAfterAuthentication":count},
        sort_keys=True,separators=(",",":")).encode()
    cipher=seal_new(private,recipient,rid)
    Path("bwr1-original-encrypted-source.v2.enc").write_bytes(cipher)

    result=financial(tape,terms,margins)
    public={
        "schema":"MXM_BWR1_BRENT_WTI_PAIRED_CONDITIONAL_EUR_COST_ECONOMICS",
        "frozenProtocolSha256":sha256(Path(
            "research/BWR1_BRENT_WTI_BASIS_REJECTION_EUR.md").read_bytes()).hexdigest(),
        "originalRunId":int(rid),"originalSourceCipherSha256":sha256(cipher).hexdigest(),
        "originalSourcePlainSha256":sha256(private).hexdigest(),
        "originalPepperstoneEurAccountAuthenticated":True,
        "originalReadOnlyRequestsAfterAuth":count,
        "historicallyExposedDevelopment52Weeks":True,
        "currentMinimumMargin":margins,
        "economics":result,
        "sourceSealedBeforeAnyPostEntryEconomicScoring":True,
        "newBrokerOrders":0,"liveDemoOrders":0,
        "cloudTradingActivated":False,"oauthReauthorized":False,
        "nativeCSharpFundedLedgerUsed":False,
        "intrabarEquityDrawdownCertified":False,
        "minimum12MonthIndependentConfirmation":False,
        "brokerRealizedNetEur":None,
        "disclosure":"Current broker tariffs retrospective conditional historical EUR scenario. Genuine historical BID/ASK and signed EURUSD, two min-sized legs; 0.5/2bp extra modeled slippage. No atomic fills, historical leverage proof, native funded C# book or continuous floating risk."
    }
    Path("bwr1-public-original-conditional-eur.json").write_text(
        json.dumps(public,indent=2,allow_nan=False)+"\n")
    x=result["all52Weeks"]
    print("BWR1_FULL_PAIRED_EUR_CONDITIONAL_ORIGINAL",
          json.dumps({"requests":count,
                      "states":x["states"],
                      "priced":x["pairedCompleteEurPriced"],
                      "adverse":x["money"]["adverse"]["adaptive"],
                      "firstAdverse":result["first26Weeks"]["money"]["adverse"]["adaptive"],
                      "lastAdverse":result["last26Weeks"]["money"]["adverse"]["adaptive"],
                      "gate":result["candidateEconomicGate"]}),flush=True)


if __name__=="__main__":
    main()

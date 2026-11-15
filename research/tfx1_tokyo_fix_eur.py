"""TFX1: fixed Tokyo gotobi bank-fix USDJPY reversion, original Pepperstone EUR.

Separation invariant: event calendar is immutable and NEVER depends on
source availability, including prices, bars or endpoint quote presence.
All original proto requests and decoded partitions are encrypted before scoring.
"""
from __future__ import annotations
import base64
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
import json, os
from pathlib import Path

from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .decode import decode_bars, decode_side
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate
from .custody import seal_new
from .custody_new import checked_public
from .rne1_source_financial_preflight import fee_usd,Unpriced
from .rne1_eur_protected_exact_reconciliation import no_swap

START=date(2025,11,3)
WEEKS=52
M5=300000
SCALE=D(100000)
SYMBOLS=("USDJPY","EURUSD")
CLOCKS=(("10:00",1,0),("10:15",1,15),("10:35",1,35))
MAX_CALLS=3700
MAX_AGE_MS=20000
GOTOBI=frozenset((5,10,15,20,25,30))
POLICIES=("primary","fixedShort","ownReversal","alwaysLong","cash")


def stamp(day,hh,mm):
    return int(datetime(day.year,day.month,day.day,hh,mm,
                        tzinfo=timezone.utc).timestamp()*1000)


def scheduled():
    for week in range(WEEKS):
        start=START+timedelta(weeks=week)
        for wd in range(5):
            yield (week,start+timedelta(days=wd))


def event(day):
    """Invariant: no data argument, no source-availability dependence."""
    if day.weekday()>=5:raise ValueError("TFX1_ONLY_PREDECLARED_WEEKDAYS")
    return ("FIXING_UNWIND_INTENT" if day.day in GOTOBI
            else "ABSTAIN_CALENDAR")


def bar_at(rows,open_at):
    if rows is None:return None
    found=[x for x in rows if x[0]==open_at and x[1]==open_at+M5]
    return found[0] if len(found)==1 else None


def partition(day,bars):
    """Separate 00:55 predecision from 01:10 monitor without future eligibility."""
    if bars is None:return {"pre":None,"monitor":None}
    # JST 09:25..09:55 -> UTC 00:25..00:55: six completed 5m.
    pre=[bar_at(bars,stamp(day,0,25)+i*M5) for i in range(6)]
    # JST 09:55..10:10 -> UTC 00:55..01:10: three later 5m.
    mon=[bar_at(bars,stamp(day,0,55)+i*M5) for i in range(3)]
    return {"pre":pre if all(x is not None for x in pre) else None,
            "monitor":mon if all(x is not None for x in mon) else None}


def exit_at(features):
    """May affect ONLY monitoring/exit; never alter event(day)."""
    if features["pre"] is None or features["monitor"] is None:
        return None
    upper=max(row[3] for row in features["pre"])
    last=features["monitor"][-1][5]
    return "10:15" if last>upper else "10:35"


def own_reversal(features):
    if features["pre"] is None:return None
    first=features["pre"][0][2]
    last=features["pre"][-1][5]
    if min(first,last)<=0:return None
    move=(last>first)-(last<first)
    return -move


def paired(bids,asks,clock):
    def asof(rows):
        good=[(int(at),int(value)) for at,value in rows
              if int(at)<=clock and int(value)>0]
        if not good:return None
        last=max(good,key=lambda x:x[0])
        return last if clock-last[0]<=MAX_AGE_MS else None
    bid,ask=asof(bids),asof(asks)
    if not bid or not ask or bid[1]>ask[1]:
        return None
    return [bid[1],ask[1]]


def checked_quote(pair):
    if (pair is None or len(pair)!=2 or pair[0]<=0 or
        pair[1]<pair[0]):
        raise Unpriced("ORIGINAL_TWO_SIDE_QUOTE_UNKNOWN")
    return tuple(D(x)/SCALE for x in pair)


def jpy_to_eur(value,usd_jpy,eur_usd):
    """Signed JPY->USD->EUR using the same original as-of two-sided quotes."""
    bidj,askj=checked_quote(usd_jpy)
    bide,aske=checked_quote(eur_usd)
    if value>=0:return value/askj/aske
    return value/bidj/bide


def current_fee_eur(contract,units,usd_jpy,eur_usd,side):
    """Broker original CURRENT USD_PER_LOT fee, debit in EUR at EURUSD BID."""
    _,askj=checked_quote(usd_jpy)
    bide,_=checked_quote(eur_usd)
    return fee_usd(contract,units,askj)/bide


def net_eur(contract,usd_quotes,eur_quotes,side,finish,slip,day):
    if side==0:
        return {"grossEur":0.0,"feesEur":0.0,"pnlConversionEur":0.0,
                "modeledSlippageEur":0.0,"netEur":0.0}
    if side not in (-1,1):raise Unpriced("SIDE_INVALID")
    if int(contract.commissionType)!=2 or (
        not contract.HasField("commissionType") or
        not contract.HasField("preciseTradingCommissionRate") or
        not contract.HasField("preciseMinCommission") or
        not contract.HasField("pnlConversionFeeRate") or
        not contract.HasField("lotSize") or not contract.HasField("minVolume")):
        raise Unpriced("CURRENT_USD_PER_LOT_CONTRACT_INCOMPLETE")
    no_swap(contract,stamp(day,1,0),
            stamp(day,1,15) if finish=="10:15" else stamp(day,1,35))
    units=D(contract.minVolume)/D(100)
    at=checked_quote(usd_quotes["10:00"])
    last=checked_quote(usd_quotes[finish])
    fx0=checked_quote(eur_quotes["10:00"])
    fx1=checked_quote(eur_quotes[finish])
    opening=at[1] if side>0 else at[0]
    closing=last[0] if side>0 else last[1]
    profit_jpy=D(side)*(closing-opening)*units
    gross_eur=jpy_to_eur(profit_jpy,usd_quotes[finish],eur_quotes[finish])
    fee0=current_fee_eur(contract,units,usd_quotes["10:00"],eur_quotes["10:00"],side)
    fee1=current_fee_eur(contract,units,usd_quotes[finish],eur_quotes[finish],side)
    rate=D(contract.pnlConversionFeeRate)/D(10000)
    if not D(0)<=rate<D(1):
        raise Unpriced("UNKNOWN_PNL_CONVERSION_RATE")
    # Official fee is on realized positive gross P&L, not negative gross loss.
    pnl_fee=max(D(0),gross_eur)*rate
    middle0=sum(at)/2
    middle1=sum(last)/2
    half_bps=D(str(slip))/D(20000)
    slip0=jpy_to_eur(-units*middle0*half_bps,
                     usd_quotes["10:00"],eur_quotes["10:00"])
    slip1=jpy_to_eur(-units*middle1*half_bps,
                     usd_quotes[finish],eur_quotes[finish])
    # Signed conversion of negative model slip gives a negative EUR result.
    slip_eur=-(slip0+slip1)
    fee_eur=fee0+fee1
    return {"grossEur":float(gross_eur),
            "feesEur":float(fee_eur),
            "pnlConversionEur":float(pnl_fee),
            "modeledSlippageEur":float(slip_eur),
            "netEur":float(gross_eur-fee_eur-pnl_fee-slip_eur)}


def report_group(rows):
    total={"scheduledWeekdays":len(rows),
           "intents":sum(r["intent"]=="FIXING_UNWIND_INTENT" for r in rows),
           "states":dict(Counter(r["state"] for r in rows)),
           "matchedPriced":sum(r["state"]=="MATCHED_ORIGINAL_EUR" for r in rows),
           "fixedPriced":sum(r.get("fixed") is not None for r in rows),
           "eligibleWeeks":len({r["week"] for r in rows})}
    matched=[r for r in rows if r["state"]=="MATCHED_ORIGINAL_EUR"]
    for scenario in ("central","adverse"):
        got={policy:round(sum(r["money"][scenario][policy]["netEur"]
                  for r in matched),6) for policy in POLICIES}
        total[scenario+"MatchedNetEur"]=got
        total[scenario+"MatchedMeanNetEur"]={
            k:round(v/len(matched),6) if matched else None
            for k,v in got.items()}
        total[scenario+"PricedFixedShortMeanNetEur"]=(
            round(sum(r["fixed"][scenario]["netEur"]
                 for r in rows if r.get("fixed") is not None)/
                  total["fixedPriced"],6)
            if total["fixedPriced"] else None)
    return total


def evaluate(days,contract,margin):
    rows=[]
    for week,day in scheduled():
        rec=days[day.isoformat()]
        intent=event(day)
        feature=partition(day,rec["bars"])
        row={"week":week,"day":day.isoformat(),"intent":intent,
             "state":intent,"signalSide":-1 if intent=="FIXING_UNWIND_INTENT" else 0,
             "predecisionAvailable":feature["pre"] is not None,
             "monitorAvailable":feature["monitor"] is not None}
        quotes=rec["quotes"]
        usd=quotes["USDJPY"]
        fx=quotes["EURUSD"]
        ok=all(usd.get(k) is not None and fx.get(k) is not None
               for k in ("10:00","10:35"))
        # Fixed-side true EUR-priced baseline is allowed even if a future
        # monitor candle is missing. Never changes the earlier signal state.
        if ok:
            try:
                row["fixed"]={tag:net_eur(contract,usd,fx,-1,"10:35",slip,day)
                              for tag,slip in (("central",0.5),("adverse",2.0))}
            except (Unpriced,ValueError,TypeError,ArithmeticError,KeyError):
                row["fixed"]=None
        else:
            row["fixed"]=None
        if intent!="FIXING_UNWIND_INTENT":
            rows.append(row);continue
        # This is a previously emitted calendar intent; all following
        # unknowns are OUTCOME unknowns, not retrospective abstentions.
        if (margin is None or
            margin["buy"] is None or margin["sell"] is None or
            max(margin["buy"],margin["sell"])>=300):
            row["state"]="INTENT_OUTCOME_UNKNOWN_MINIMUM_MARGIN"
        elif feature["pre"] is None:
            row["state"]="INTENT_OUTCOME_UNKNOWN_PREDECISION_BARS"
        elif feature["monitor"] is None:
            row["state"]="INTENT_OUTCOME_UNKNOWN_MONITOR_BARS"
        elif not all(usd.get(k) is not None and fx.get(k) is not None
                     for k,_,_ in CLOCKS):
            row["state"]="INTENT_OUTCOME_UNKNOWN_QUOTES_OR_FX"
        elif own_reversal(feature) is None:
            row["state"]="INTENT_OUTCOME_UNKNOWN_OWN_MOMENTUM"
        else:
            dest=exit_at(feature)
            policies={"primary":(-1,dest),
                      "fixedShort":(-1,"10:35"),
                      "ownReversal":(own_reversal(feature),"10:35"),
                      "alwaysLong":(1,"10:35"),
                      "cash":(0,"10:35")}
            try:
                row["money"]={
                    scen:{p:net_eur(contract,usd,fx,side,last,slip,day)
                          for p,(side,last) in policies.items()}
                    for scen,slip in (("central",0.5),("adverse",2.0))}
                row["state"]="MATCHED_ORIGINAL_EUR"
                row["exit"]=dest
            except (Unpriced,ValueError,TypeError,ArithmeticError,KeyError) as err:
                row["state"]="INTENT_OUTCOME_UNKNOWN_CONTRACT_OR_FINANCE"
                row["unpricedReason"]=str(err)[:70]
        rows.append(row)
    return {
        "all260":report_group(rows),
        "first26Weeks":report_group([r for r in rows if r["week"]<26]),
        "last26Weeks":report_group([r for r in rows if r["week"]>=26]),
        "gotobi":report_group([r for r in rows if r["intent"]=="FIXING_UNWIND_INTENT"]),
        "nongotobiPlacebo":report_group([r for r in rows if r["intent"]=="ABSTAIN_CALENDAR"]),
        "currentMinimumMarginBuyEur":margin["buy"] if margin else None,
        "currentMinimumMarginSellEur":margin["sell"] if margin else None,
        "brokerRealizedNetEur":None,
        "fundedNativeCSharpTrades":0,
    }


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    raw=[]
    calls=0
    tape={}
    contracts={}
    t=StdlibCTraderTransport()

    def req(q,klass,allow_empty=False):
        nonlocal calls
        if calls>=MAX_CALLS:
            raise RuntimeError("TFX1_MAX_ORIGINAL_READONLY_REACHED")
        require_read_only_request(q)
        result=t.request(q)
        calls+=1
        if not result.IsInitialized() or (
            int(result.ctidTraderAccountId)!=int(q.ctidTraderAccountId)
            or int(q.ctidTraderAccountId)!=account):
            raise RuntimeError("TFX1_ORIGINAL_RESPONSE_ACCOUNT_MISMATCH")
        if (allow_empty and type(result) is m.ProtoOAErrorRes
            and result.errorCode=="NO_QUOTES"):
            ans=None
        elif type(result) is klass:
            ans=result
        else:
            raise RuntimeError("TFX1_ORIGINAL_SOURCE_RESPONSE_TYPE")
        raw.append({
            "requestType":type(q).__name__,
            "request":base64.b64encode(q.SerializeToString()).decode(),
            "responseType":type(result).__name__,
            "response":base64.b64encode(result.SerializeToString()).decode()})
        return ans

    def quote(symbol,day,hh,mm):
        clock=stamp(day,hh,mm)
        sides={};complete=True
        for side in (e.BID,e.ASK):
            reply=req(m.ProtoOAGetTickDataReq(
                 ctidTraderAccountId=account,symbolId=ids[symbol],
                 type=side,fromTimestamp=clock-60000,toTimestamp=clock),
                 m.ProtoOAGetTickDataRes,True)
            if reply is None or reply.hasMore:
                sides[side]=[];complete=False
            else:
                sides[side]=decode_side(reply.tickData,clock-60000,clock)
        return paired(sides[e.BID],sides[e.ASK],clock) if complete else None

    try:
        account=authenticate(t)
        broker=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        aset=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),
                 m.ProtoOAAssetListRes)
        assets={a.assetId:a.name for a in aset.asset}
        if (not broker.trader.HasField("brokerName")
            or "pepperstone" not in broker.trader.brokerName.casefold()
            or assets.get(broker.trader.depositAssetId)!="EUR"):
            raise RuntimeError("TFX1_NOT_ORIGINAL_PEPPERSTONE_EUR")
        roster=req(m.ProtoOASymbolsListReq(
              ctidTraderAccountId=account,includeArchivedSymbols=False),
              m.ProtoOASymbolsListRes)
        listing={s.symbolName:s for s in roster.symbol if s.enabled}
        if not all(s in listing for s in SYMBOLS):
            raise RuntimeError("TFX1_FIXED_FX_ROUTE_NOT_ENABLED")
        if any((assets.get(listing[s].baseAssetId),
                assets.get(listing[s].quoteAssetId))!=v
                for s,v in (("USDJPY",("USD","JPY")),("EURUSD",("EUR","USD")))):
            raise RuntimeError("TFX1_FX_ROUTE_ACCOUNT_ASSETS_INVALID")
        ids={s:listing[s].symbolId for s in SYMBOLS}
        for name in SYMBOLS:
            z=req(m.ProtoOASymbolByIdReq(
                    ctidTraderAccountId=account,symbolId=[ids[name]]),
                    m.ProtoOASymbolByIdRes)
            if len(z.symbol)!=1 or z.symbol[0].symbolId!=ids[name]:
                raise RuntimeError("TFX1_CONTRACT_IDENTITY_MISMATCH")
            contracts[name]=z.symbol[0]
        c=contracts["USDJPY"]
        if (not c.HasField("minVolume") or c.minVolume<=0 or
            not c.HasField("tradingMode") or c.tradingMode!=e.ENABLED or
            not c.HasField("enableShortSelling") or not c.enableShortSelling):
            raise RuntimeError("TFX1_TARGET_SHORT_NOT_OPENABLE")
        z=req(m.ProtoOAExpectedMarginReq(
                ctidTraderAccountId=account,symbolId=ids["USDJPY"],
                volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
        if not z.HasField("moneyDigits") or len(z.margin)!=1 or (
            z.margin[0].volume!=c.minVolume):
            margin={"buy":None,"sell":None}
        else:
            div=D(10)**z.moneyDigits
            margin={"buy":float(D(z.margin[0].buyMargin)/div),
                    "sell":float(D(z.margin[0].sellMargin)/div)}
        for week,day in scheduled():
            key=day.isoformat()
            # One independent source window; a future missing M5 bar
            # NEVER cancels the immutable calendar intent.
            st,en=stamp(day,0,20),stamp(day,1,20)
            bars_reply=req(m.ProtoOAGetTrendbarsReq(
                ctidTraderAccountId=account,symbolId=ids["USDJPY"],
                period=e.M5,fromTimestamp=st,toTimestamp=en),
                m.ProtoOAGetTrendbarsRes,True)
            if bars_reply is None or bars_reply.hasMore:
                bars=None
            elif bars_reply.period!=e.M5 or (
                bars_reply.HasField("symbolId") and
                bars_reply.symbolId!=ids["USDJPY"]):
                raise RuntimeError("TFX1_WRONG_M5_RESPONSE")
            else:
                bars=decode_bars(bars_reply.trendbar,st-2*M5,en+2*M5,5)
            obs={"week":week,"event":event(day),"bars":bars,
                 "quotes":{s:{} for s in SYMBOLS}}
            # Quote all 260 scheduled dates, never select on the
            # currently stored later M5 source presence or outcome.
            for name in SYMBOLS:
                for clock,hh,mm in CLOCKS:
                    obs["quotes"][name][clock]=quote(name,day,hh,mm)
            tape[key]=obs
            if week%6==5 and day.weekday()==4:
                print("TFX1_SOURCE_ONLY_WEEKS",week+1,"OF",WEEKS,
                      "ORIGINAL_READONLY_REQUESTS",calls,flush=True)
    finally:
        t.close()
    source=json.dumps({
        "schema":"MXM_TFX1_PRIVATE_ORIGINAL_TOKYO_FIX_ECONOMIC_SOURCE",
        "run":run,"originalPepperstoneEurAccount":True,
        "originalProtobufRequestResponse":raw,
        "originalCausalSourceDates":tape,
        "accountCurrentMargin":margin,
        "sourceReadOnlyRequests":calls,
        "intentDecisionCalendarOnly":True,
        "sourcePartitionPreAndPostDecision":True,
    },sort_keys=True,separators=(",",":")).encode()
    cipher=seal_new(source,recipient,run)
    Path("tfx1-original-protected.v2.enc").write_bytes(cipher)
    # First irreversible custody, THEN economic post-entry scoring.
    result=evaluate(tape,contracts["USDJPY"],margin)
    before=result["first26Weeks"]["adverseMatchedNetEur"]
    after=result["last26Weeks"]["adverseMatchedNetEur"]
    overall=result["gotobi"]["adverseMatchedNetEur"]
    counts=result["gotobi"]
    eligible=all(x["matchedPriced"]>0 for x in (
        result["first26Weeks"],result["last26Weeks"]))
    def superior(d):
        return d["primary"]>0 and d["primary"]>max(
            d["fixedShort"],d["ownReversal"],d["alwaysLong"],d["cash"])
    passed=eligible and all(superior(x) for x in (before,after,overall))
    verdict=("DEVELOPMENT_ONLY_POSSIBLE_ECONOMIC_CANDIDATE"
             if passed else ("INSUFFICIENT_FINANCIAL_SOURCE_COVERAGE"
             if not eligible else "REJECT_EXACT_TFX1_NO_ROBUST_INCREMENTAL_ADVERSE_NET"))
    public={
        "schema":"MXM_TFX1_ORIGINAL_TOKYO_GOTOBI_FIXED_EUR_ACCOUNT",
        "originalRunId":int(run),
        "protocolSha256":sha256(Path(
            "research/TFX1_TOKYO_CORPORATE_FLOW_UNWIND.md").read_bytes()).hexdigest(),
        "originalCiphertextSha256":sha256(cipher).hexdigest(),
        "originalPlaintextSha256":sha256(source).hexdigest(),
        "authOriginalPepperstoneEur":True,
        "readOnlyRequestsAfterAuth":calls,
        "fixed52Weeks":True,"originalDates":260,
        "hadSourceBeforeEconomicScoring":True,
        "signalIndependentOfAnyFutureSourceAvailability":True,
        "sourceAndFinanceStateAreDistinct":True,
        "originalContractCurrencyRoute":"JPY->USD->EUR_SEPARATE_REAL_BID_ASK",
        "eurNet":result,
        "decisionGate":verdict,
        "allChronologyGlobalExposedDevelopment":True,
        "currentContractTariffNotHistoricalCertification":True,
        "modelSlippageNotBrokerActual":True,
        "brokerRealizedPnL":None,
        "independentConfirmation":False,
        "nativeFundedCommonBookNet":None,
        "continuousFloatDrawdownCertified":False,
        "hard21EligibleWeeksQualified":0,
        "ordersSubmitted":0,
        "cloudTradingActivated":False,
        "oauthReauthorized":False,
    }
    Path("tfx1-original-public-eur.json").write_text(
        json.dumps(public,indent=2,allow_nan=False)+"\n")
    print("TFX1_ORIGINAL_GOTOBI_EUR_FINANCIAL",json.dumps({
        "requests":calls,"intents":counts["intents"],
        "matchedGotobi":counts["matchedPriced"],
        "firstAdverse":before["primary"],"lastAdverse":after["primary"],
        "adverseGotobi":overall,
        "nonGotobiFixedMeanAdverse":result["nongotobiPlacebo"]["adversePricedFixedShortMeanNetEur"],
        "verdict":verdict},sort_keys=True),flush=True)


if __name__=="__main__":
    main()

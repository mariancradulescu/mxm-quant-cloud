"""RNE1-EUR sealed two-original-source, conditional monetary readback.

No new broker request. All 26 Thursday events retained. The original RNE1
shock rule and exits are never reselected. This is NOT broker EUR NET
certification or native portfolio financing evidence.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from hashlib import sha256
import json,os
from pathlib import Path
from statistics import mean

from .custody import unseal_new
from .rne1_source_financial_preflight import get_terms,fee_usd,Unpriced
from .rne1_eia_gas_release import START,WEEKS,stamp,event_decision,score_one,bps,sign,evaluate

OLD_RUN="43468457518"
OLD_CIPHER="3da628356a40679442d65a048f37b278356cda6060afe85510195e3131bcac14"
OLD_PLAIN="5a14486c71997f29c8a6c2ffbfa24d1380ba09a862f10f75916d5d2512d8b01c"
OLD_PUBLIC="7ac85fb30374cfe20a3dad722e50aedebcfdc3ac68d23614539c8d002e5c1dd8"
NEW_RUN="43472594458"
NEW_CIPHER="3bb2a702fe4a8967be9bb59225d307f64ac25441f219bb98cc15488679088518"
NEW_PLAIN="3aa735672e866885c378b7efcf477e5b99ac04f5754513cbd6bf90beaf3ed459"
NEW_PUBLIC="4f445f2377f79cb0bdaa4ffa6fcf0163804a1722250a1e080e2181f6a531072f"
SCALE=D(100000)
MODEL_START_EUR=D(300)
POLICIES=("rne1","fixed","ownMomentum","long","short","cash")


def checked_original(path,expected):
    raw=Path(path).read_bytes()
    if sha256(raw).hexdigest()!=expected:
        raise ValueError("RNE1_EUR_ORIGINAL_DIGEST_MISMATCH")
    return raw


def unseal_both():
    old_enc=checked_original("original-source/rne1-eia-protected-original.v2.enc",OLD_CIPHER)
    old_public=json.loads(checked_original("original-public/rne1-eia-public.json",OLD_PUBLIC))
    new_enc=checked_original("dense-source/rne1-eur-original-dense-quote-source.v2.enc",NEW_CIPHER)
    new_public=json.loads(checked_original("dense-public/rne1-eur-original-source-coverage.json",NEW_PUBLIC))
    private=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    old_raw=unseal_new(old_enc,private,OLD_RUN)
    new_raw=unseal_new(new_enc,private,NEW_RUN)
    if sha256(old_raw).hexdigest()!=OLD_PLAIN or sha256(new_raw).hexdigest()!=NEW_PLAIN:
        raise ValueError("RNE1_EUR_CUSTODY_PLAINTEXT_MISMATCH")
    old=json.loads(old_raw)
    new=json.loads(new_raw)
    if (old["run"]!=OLD_RUN or old["schema"]!="MXM_ORIGINAL_RNE1_SOURCE_PRIVATE" or
        new["run"]!=NEW_RUN or new["schema"]!="MXM_RNE1_EUR_ORIGINAL_HISTORICAL_DENSE_BID_ASK" or
        not old["originalAccountVerified"] or not new["originalAccountVerified"] or
        new["fixedOriginalRne1Run"]!=int(OLD_RUN) or
        old_public["originalRun"]!=int(OLD_RUN) or
        old_public["sourcePlainSha256"]!=OLD_PLAIN or
        old_public["sealedSourceSha256"]!=OLD_CIPHER or
        new_public["runId"]!=int(NEW_RUN) or
        new_public["protectedCipherSha256"]!=NEW_CIPHER or
        new_public["protectedPlaintextSha256"]!=NEW_PLAIN or
        not new_public["originalPepperstoneEurBound"] or
        new_public["readOnlyOriginalRequestsAfterAuthentication"]!=1671):
        raise ValueError("RNE1_EUR_ORIGINAL_IDENTITY_OR_PUBLIC_SCHEMA_FAILURE")
    return old,old_public,new,new_public


def original_tape_ints(original,receipt):
    source=original["source"]
    for name,days in source.items():
        for key,v in days.items():
            v["bars"]={int(k):int(x) for k,x in v["bars"].items()}
    repeated=evaluate(source,original["currentContract"])
    for name in ("NatGas","EQT.US"):
        for arm in ("release","placebo"):
            a,b=repeated[name][arm],receipt["targets"][name][arm]
            if (a["decisionCounts"]!=b["decisionCounts"] or
                a["adaptivePriced"]!=b["adaptivePriced"] or
                a["pairedPriced"]!=b["pairedPriced"]):
                raise ValueError("ORIGINAL_RNE1_OUTCOME_OR_COUNTS_CHANGED")
    return source


def quote(panel,symbol,clock):
    sample=panel.get("symbols",{}).get(symbol,{}).get(str(clock))
    if not sample or sample.get("clock")!=clock or sample.get("truncated"):
        return None
    pair=sample.get("pair")
    if not pair:
        return None
    b,a=pair.get("bid"),pair.get("ask")
    if not b or not a:
        return None
    for v in (b,a):
        if (v.get("raw",0)<=0 or v.get("at",0)>clock or
            clock-v.get("at",0)>20000 or
            v.get("ageMs")!=clock-v.get("at")):
            raise ValueError("RNE1_EUR_INVALID_OR_FUTURE_ORIGINAL_QUOTE")
    if b["raw"]>a["raw"]:
        raise ValueError("RNE1_EUR_CROSSED_ORIGINAL_QUOTE")
    return (D(b["raw"])/SCALE,D(a["raw"])/SCALE)


def no_swap(c,entry_clock,exit_clock):
    if not c.HasField("swapTime") or not c.HasField("swapPeriod"):
        raise Unpriced("CURRENT_SWAP_SCHEDULE_UNKNOWN")
    when=int(c.swapTime)
    if not 0<=when<1440 or c.swapPeriod!=24:
        raise Unpriced("CURRENT_SWAP_HOUR_UNVERIFIED")
    d=datetime.fromtimestamp(entry_clock/1000,timezone.utc).date()
    stop=datetime.fromtimestamp(exit_clock/1000,timezone.utc).date()
    while d<=stop:
        charge=int(datetime(d.year,d.month,d.day,tzinfo=timezone.utc).timestamp()*1000)+when*60000
        if entry_clock<charge<=exit_clock:
            raise Unpriced("CROSSES_CONTRACT_FINANCING_CHARGE")
        d+=timedelta(days=1)


def current_eur(c,entry,exit_quote,entry_fx,exit_fx,side,slip_roundtrip_bps):
    """Signed USD profit via exact as-of EURUSD ask/bid; fees debit at own clock.

    These are current-tariff scenarios on historical quotes, NOT fill records.
    """
    if side==0:
        return {"grossEur":0.0,"netEur":0.0,"feesEur":0.0,
                "modeledSlippageEur":0.0,"pnlConversionEur":0.0}
    if (entry is None or exit_quote is None or
        entry_fx is None or exit_fx is None):
        raise Unpriced("ORIGINAL_MONEY_CLOCK_MISSING")
    if not c.HasField("pnlConversionFeeRate"):
        raise Unpriced("CURRENT_PNL_CONVERSION_FEE_UNKNOWN")
    volume=D(c.minVolume)/100
    if volume<=0 or min(*entry,*exit_quote,*entry_fx,*exit_fx)<=0:
        raise Unpriced("ORIGINAL_PRICE_OR_BROKER_SIZE_INVALID")
    opening=entry[1] if side>0 else entry[0]
    closing=exit_quote[0] if side>0 else exit_quote[1]
    gross_usd=D(side)*(closing-opening)*volume
    signed_fx=D(1)/exit_fx[1] if gross_usd>=0 else D(1)/exit_fx[0]
    pnl_rate=D(c.pnlConversionFeeRate)/D(10000)
    if pnl_rate<0 or pnl_rate>=1:
        raise Unpriced("INVALID_PNL_CONVERSION_FEE")
    pnl_conv=abs(gross_usd)*pnl_rate /exit_fx[0]
    gross_eur=gross_usd*signed_fx
    entry_fee=fee_usd(c,volume,opening)/entry_fx[0]
    exit_fee=fee_usd(c,volume,closing)/exit_fx[0]
    mid=(entry[0]+entry[1])/2
    slip_usd=volume*mid*D(str(slip_roundtrip_bps))/D(20000)
    slippage=slip_usd/entry_fx[0]+slip_usd/exit_fx[0]
    fee=entry_fee+exit_fee
    net=gross_eur-pnl_conv-fee-slippage
    return {"grossEur":float(gross_eur),
            "netEur":float(net),
            "feesEur":float(fee),
            "modeledSlippageEur":float(slippage),
            "pnlConversionEur":float(pnl_conv)}


def summary(rows,policy="rne1",scenario="adverse"):
    return {
        "number":len(rows),
        "weeks":len(set(x["week"] for x in rows)),
        "conditionalNetEurSum":round(sum(x[scenario][policy]["netEur"] for x in rows),6),
        "conditionalNetEurMean":round(mean(x[scenario][policy]["netEur"] for x in rows),6) if rows else None,
        "grossEurSum":round(sum(x[scenario][policy]["grossEur"] for x in rows),6),
        "feeEurSum":round(sum(x[scenario][policy]["feesEur"] for x in rows),6),
        "slippageModelEurSum":round(sum(x[scenario][policy]["modeledSlippageEur"] for x in rows),6),
    }


def evaluate_new(original,old_public,new,coverage):
    old_source=original_tape_ints(original,old_public)
    dense=new["fixedThursdayPanel"]
    terms=get_terms(original)
    meta=original["currentContract"].get("NatGas",{})
    if (meta.get("currentMinimumMarginEur") is not None or
        meta.get("currentMinVolume") is not None):
        raise ValueError("RNE1_SOURCE_CONTRACT_SCHEMA_UNEXPECTED")
    marginBuy=meta.get("currentMarginBuyEur")
    marginSell=meta.get("currentMarginSellEur")
    statuses=Counter()
    endpoints=[]
    complete=[]
    for week in range(WEEKS):
        day=START+timedelta(weeks=week,days=3)
        key=day.isoformat()
        if key not in dense or dense[key]["week"]!=week:
            raise ValueError("MISSING_PREDECLARED_26_DAY_EUR_DENSE_SOURCE")
        original_day=old_source["NatGas"].get(key)
        if original_day is None or original_day["truncated"]:
            statuses["ORIGINAL_NATGAS_MISSING_SOURCE"]+=1
            continue
        decision=event_decision(day,original_day["bars"])
        state=decision["state"]
        if state!="RELEASE_SHOCK_CANDIDATE":
            statuses[state]+=1
            continue
        statuses["ORIGINAL_RNE1_EIA_INTENT"]+=1
        orig_row=score_one({"kind":"THURSDAY_OFFICIAL_EIA_SCHEDULE",
            "gasBars":original_day["bars"],"day":day,"week":week},original_day)
        if orig_row["state"]!="ADAPTIVE_PRICED":
            statuses[orig_row["state"]]+=1
            continue
        orig_entry=original_day["quote"]["10:50"]
        original_exit=original_day["quote"][decision["exitAt"]]
        a=stamp(day,10,50)
        eclock=stamp(day,11,20) if decision["invalidatedAt1115"] else stamp(day,12,5)
        dense_day=dense[key]
        entry=quote(dense_day,"NatGas",a)
        exit_quote=quote(dense_day,"NatGas",eclock)
        if entry is None or exit_quote is None:
            statuses["DENSE_NATGAS_ENTRY_OR_EXIT_MISSING"]+=1
            continue
        # Price reconciliation with original source used to obtain
        # the earlier USD-only preflight. Never pick preferable values.
        def raw_compare(p,q):
            return p is not None and (D(p[0])/SCALE,D(p[1])/SCALE)==q
        if not raw_compare(orig_entry,entry) or not raw_compare(original_exit,exit_quote):
            statuses["ORIGINAL_SOURCE_PRICE_CONFLICT"]+=1
            continue
        fx0=quote(dense_day,"EURUSD",a)
        fxz=quote(dense_day,"EURUSD",eclock)
        if fx0 is None or fxz is None:
            statuses["USD_EUR_CONVERSION_MISSING"]+=1
            continue
        try:
            no_swap(terms,a,eclock)
            candidate={scenario:current_eur(terms,entry,exit_quote,fx0,fxz,
                     decision["side"],s)
                     for scenario,s in (("central",0.5),("adverse",2.0))}
        except Unpriced as err:
            statuses[str(err)]+=1
            continue
        endpoints.append({"week":week,"central":{"rne1":candidate["central"]},
                          "adverse":{"rne1":candidate["adverse"]}})
        statuses["COMPLETE_CONDITIONAL_EUR_ENDPOINT"]+=1
        # Full future sampled path coverage is needed before
        # printing any complete sampled float / financed-model book.
        clocks=tuple(range(a,eclock+300000,300000))
        if any(quote(dense_day,"NatGas",t) is None or
               quote(dense_day,"EURUSD",t) is None for t in clocks):
            statuses["INCOMPLETE_FIVE_MINUTE_OPEN_EQUITY_PATH"]+=1
            continue
        statuses["FULL_SAMPLED_OPEN_EQUITY_PATH"]+=1
        # Same-entry benchmark cohorts require the fixed 12:05 mark.
        last=stamp(day,12,5)
        ref=quote(dense_day,"NatGas",last)
        old_ref=original_day["quote"].get("12:05")
        if ref is None or old_ref is None:
            statuses["BENCHMARK_EXIT_PRICE_UNAVAILABLE"]+=1
            continue
        if not raw_compare(old_ref,ref):
            statuses["BENCHMARK_ORIGINAL_PRICE_CONFLICT"]+=1
            continue
        # Full full-horizon sourced equity is required for ALL
        # benchmark books, even after the adaptive policy exits early.
        full_clocks=tuple(range(a,last+300000,300000))
        if any(quote(dense_day,"NatGas",t) is None or
               quote(dense_day,"EURUSD",t) is None for t in full_clocks):
            statuses["BENCHMARK_FULL_PATH_INCOMPLETE"]+=1
            continue
        own=sign(bps(original_day["bars"],stamp(day,10,15),
                     stamp(day,10,45)))
        policies={
            "rne1":(decision["side"],eclock),
            "fixed":(decision["side"],last),
            "ownMomentum":(own,last),
            "long":(1,last),
            "short":(-1,last),
            "cash":(0,last)}
        row={"week":week,"scenarioPaths":{},
             "originalCausalSides":{k:v[0] for k,v in policies.items()}}
        for scenario,slip in (("central",0.5),("adverse",2.0)):
            row[scenario]={}
            row["scenarioPaths"][scenario]={}
            for name,(side,until) in policies.items():
                exit_q=quote(dense_day,"NatGas",until)
                exit_fx=quote(dense_day,"EURUSD",until)
                no_swap(terms,a,until)
                row[scenario][name]=current_eur(
                    terms,entry,exit_q,fx0,exit_fx,side,slip)
                sampled=[current_eur(terms,entry,
                    quote(dense_day,"NatGas",t),fx0,
                    quote(dense_day,"EURUSD",t),side,slip)["netEur"]
                    for t in range(a,until+300000,300000)]
                row["scenarioPaths"][scenario][name]=sampled
        complete.append(row)
        statuses["COMMON_MATCHED_FULL_PATH_COMPARABLE"]+=1

    # Model-only one EUR300 opening balance for each separate
    # benchmark: all prelisted event weeks, no cash reset after losses.
    books={}
    for scenario in ("central","adverse"):
        books[scenario]={}
        for policy in POLICIES:
            cash=float(MODEL_START_EUR)
            peak=cash
            drawdown=0.0
            completed=0
            for x in complete:
                # Present-day margin is an EX POST hypothetical capacity
                # guard, never proof of as-of historical broker permission.
                mode=x["originalCausalSides"][policy]
                margin=marginBuy if mode>0 else marginSell
                if policy!="cash" and (margin is None or margin<=0 or
                    cash<=margin):
                    continue
                if policy=="cash":
                    continue
                for signed_eur in x["scenarioPaths"][scenario][policy]:
                    equity=cash+signed_eur
                    peak=max(peak,equity)
                    drawdown=max(drawdown,1-equity/peak)
                cash+=x[scenario][policy]["netEur"]
                completed+=1
                peak=max(peak,cash)
                drawdown=max(drawdown,1-cash/peak)
            books[scenario][policy]={
                "conditionalCompleteSampledPaths":completed,
                "modeledFinalCashEur":round(cash,6),
                "modeledTotalEur":round(cash-float(MODEL_START_EUR),6),
                "maximumSampledDrawdownFraction":round(drawdown,8),
                "brokerHistoricalPermissionCertified":False,
                "continuousIntrabarDrawdownCertified":False,
                "nativeFundedLedgerExecuted":False,
            }
    return {
        "all26WeekDecisionClasses":dict(statuses),
        "conditionalEndpointEur":{"central":summary(endpoints,scenario="central"),
                                  "adverse":summary(endpoints,scenario="adverse")},
        "matchedCompleteSampledPaths":{
            scenario:{p:summary(complete,policy=p,scenario=scenario)
                      for p in POLICIES}
            for scenario in ("central","adverse")},
        "conditionalIndependentSingleMarketBooks":books,
        "currentMinimumMargin":{ "buyEur":marginBuy,"sellEur":marginSell },
        "originalSignalIntentsExpected":19,
        "originalConditionalAdaptivePricedExpected":17,
        "originalFullyPairedExpected":15,
        "noSurvivorshipFreePortfolioCertification":True,
        "unobservedIntervalsUnknown":True,
        "nativeFundedLedgerEurNet":None,
        "brokerFundedEurNet":None
    }


def main():
    old,oldpub,new,newpub=unseal_both()
    results=evaluate_new(old,oldpub,new,newpub)
    out={
        "schema":"MXM_RNE1_EXACT_RULE_ORIGINAL_EUR_CONVERSION_CONDITIONAL_READBACK",
        "Rne1Unmodified":True,
        "originalRunId":int(OLD_RUN),"originalCipherSha256":OLD_CIPHER,
        "denseNewRunId":int(NEW_RUN),"denseSourceCipherSha256":NEW_CIPHER,
        "originalPublicReceiptArtifact":14059488784,
        "originalSourceArtifact":14059473739,
        "densePublicArtifact":14061783553,
        "denseCipherArtifact":14061847775,
        "readbackRun":int(os.environ["GITHUB_RUN_ID"]),
        "newBrokerRequests":0,
        "originalBoundAccountAttested":True,
        "originalScoreAndExitUnchanged":True,
        "quotedOutcomes":results,
        "validity":{"currentBrokerTermsExPostOnly":True,
            "historicalTradingPermissionCertified":False,
            "usdEurSourceOriginalAtEachAvailableClock":True,
            "futureOutcomeUnseenForEventSignal":True,
            "intrabarFloatContinuityProven":False,
            "nativeCSharpFundedLedgerUsed":False,
            "chronologicalIndependentConfirmation":False,
            "minimum12MonthsMet":False,
            "hard21SystemicCertified":False,
            "eur300CommonMultiassetPortfolioNetCertified":False,
            "liveDemoOrders":0,"cloudTradingActivated":False,
            "oauthReauthorized":False}
    }
    Path("rne1-original-eur-conditional-readback.json").write_text(
        json.dumps(out,indent=2,allow_nan=False)+"\n")
    print("RNE1_ORIGINAL_EUR_READBACK_NO_BROKER_REQUESTS",
          json.dumps({"paths":results["all26WeekDecisionClasses"],
                      "adverseEndpoint":results["conditionalEndpointEur"]["adverse"]}),
          flush=True)


if __name__=="__main__":
    main()

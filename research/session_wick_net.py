"""Genuine previously sealed Pepperstone M15 BID/ASK -> new 09-15 UTC wick strategy.

This is an economically NEW frozen hypothesis. It cannot ask broker for new
quotes, place trades or evaluate final20 holdout. The source comes solely from
already authenticated protected action 41619870283; no public raw prices.
"""
import os,sys,json,hashlib,math
from pathlib import Path
from .decode import need
from .custody import unseal_new
from .session_wick_signal import signals,MODEL
from .anchor_balance_net import (reqcheck,read_quote,commission_eur,financing_proven,
    SLIP_MULTIPLIERS,SYMBOL,DAY,Quote,Contract,Decision,FundedReplay,D)
from .funded_replay import IncompleteEvidence

ORIGINAL_RUN="41619870283"
ORIGINAL_SHA256="b45633ea60ec86bef2cf3c7483bd305b3e5ee38d5829965e5163e2b525a626ba"

def funded_and_diagnostics(bundle):
    frozen=signals(bundle)
    plan=frozen["plan"]
    c=bundle["contract"];min_units=int(c["minVolume"])//100;step=int(c["stepVolume"])//100
    max_units=int(c["maxVolume"])//100
    reqcheck(min_units>0 and step>0 and min_units<=max_units and c["minVolume"]%100==0,"MIN_BROKER_VOLUME_ENCODING")
    fxfee=D(str(c["pnlConversionFeeRate"]))/D("10000")
    reqcheck(D("0")<=fxfee<D("0.2"),"FX_FEE_BROKER_INVALID")
    margin=D(str(bundle["marginEurMin"])) / D(min_units)
    reqcheck(margin>0,"MARGIN_EVIDENCE_MISSING")
    calibrated=D(str(bundle["trainSlippagePrice"]))
    spread=D(str(bundle["trainSpreadPrice"]))
    reqcheck(calibrated>0 and spread>=0,"TRAIN_QUOTE_CALIBRATION_MISSING")
    weeks=frozen["eligibleMondayUtcMs"]
    full=[];missing=0;forecast_rejected=0
    for p in plan:
        qin=read_quote(bundle,p["signal"]);qout=read_quote(bundle,p["exit"])
        if qin is None or qout is None:
            missing+=1;continue
        reqcheck(qout["time"]>qin["time"],"NONCHRONOLOGICAL_EVENT_QUOTES")
        gross=D(str(p["side"]))*D(min_units)*(D(str(qout["bid"]+qout["ask"]-qin["bid"]-qin["ask"]))/D("200000")) 
        # Above gross is quote USD at midpoint for min units, not booked funded NET.
        costscreen=spread+2*calibrated + D("2")*D(str(bundle["screenMinCommissionEur"]))*D(str(bundle["screenEurAsk"]))/D(min_units)
        eligible=abs(D(str(p["forecast"])))*D(str(p["price"]))>costscreen
        if not eligible:forecast_rejected+=1
        full.append((p,qin,qout,eligible,gross))
    outcomes=[]
    for mult in SLIP_MULTIPLIERS:
        replay=FundedReplay(starting_eur=D("200"),max_staleness_ms=15000,financing_schedule_proven=financing_proven(c))
        proposed=admitted=costblocked=stressblocked=0
        for p,ein,eout,accepted,g in full:
            proposed+=1
            if not accepted:costblocked+=1;continue
            slip=calibrated*D(mult)
            def mk(row):
                bid=D(row["bid"])/100000
                ask=D(row["ask"])/100000
                return Quote(row["time"],SYMBOL,bid,ask,
                    (D(1)-fxfee)/ask,(D(1)+fxfee)/bid,
                    hashlib.sha256((row["sha"]+bundle["sourceId"]).encode()).hexdigest())
            q1=mk(ein);q2=mk(eout)
            entry_fee=commission_eur(c,min_units,q1.ask if p["side"]>0 else q1.bid,q1.bid,q1.ask)
            # Ex-ante equity marks use only the entry-time estimate.
            # Actual exit commission is learned and booked ONLY at the exit quote.
            estimated_exit_fee=commission_eur(c,min_units,q1.bid if p["side"]>0 else q1.ask,q1.bid,q1.ask)
            con=Contract(min_units,step,max_units,margin,entry_fee,estimated_exit_fee,slip,
                "PEPPERSTONE_CURRENT_CONTRACT_SNAPSHOT_CONDITIONAL_HISTORY")
            # One predeclared causal training-tail stress, constrained by the
            # OWNER portfolio 30%-DD objective; never a universal risk-per-entry cap.
            train_stress_price=D(str(p["price"]))*D(str(frozen["train99p5AbsForwardReturn"]))
            train_stress_price+=spread+D("2")*slip
            worst_eur=D(min_units)*train_stress_price/q1.bid+entry_fee+estimated_exit_fee
            stress_peak=max(replay.peak,replay.balance)
            if replay.balance-worst_eur<=stress_peak*D("0.70"):
                stressblocked+=1
                continue
            replay.decide(Decision(p["signal"],p["signal"],frozen["trainingCutMs"]-1,
                str(p["signal"]),SYMBOL,"OPEN",1000,p["side"],min_units,con))
            replay.quote(q1)
            if str(p["signal"]) in replay.open:
                admitted+=1
                replay.decide(Decision(p["exit"],p["exit"],frozen["trainingCutMs"]-1,
                    str(p["signal"]),SYMBOL,"CLOSE",1000))
            observed_exit_fee=commission_eur(c,min_units,q2.bid if p["side"]>0 else q2.ask,q2.bid,q2.ask)
            replay.quote(q2,observed_exit_commission_eur=observed_exit_fee)
        report=replay.report(weeks)
        # Full predeclared UTC weeks, INCLUDING zero-activity weeks.
        week_nets=[sum((t["net_eur"] for t in replay.trades
                 if mon <= t["closed_at"] < mon+7*DAY),D("0")) for mon in weeks]
        weekly_mean=sum(week_nets,D("0"))/len(weeks)
        weekly_var=sum((z-weekly_mean)**2 for z in week_nets)/(len(weeks)-1)
        weekly_lower=weekly_mean-D("2.6")*D(str(math.sqrt(float(weekly_var)/len(weeks))))
        report["weekly_net_eur"]=[str(x) for x in week_nets]
        report["mean_weekly_net_eur"]=str(weekly_mean)
        report["conservative_2p6se_weekly_lower_eur"]=str(weekly_lower)
        report["cost_breakdown_eur"]={k:str(sum((t[k] for t in replay.trades),D("0"))) for k in
                ("gross_eur","spread_eur","slippage_eur","conversion_eur","commissions_eur","financing_eur")}
        outcome={"slippageScaleOfTRAINSpreadDerivedHypothesis":mult,
                 "eventQuotesPresent":len(full),"missingEntryOrExitEventQuotes":missing,
                 "forecastCostBlocked":costblocked,"trainingTailStressBlocked":stressblocked,
                 "financingCurrentScheduleOutsideHolding":financing_proven(c),
                 "portfolioEur200QuoteReplay":json.loads(json.dumps(report,default=str)),
                 "historicalTariffConfirmed":False,"historicalFillObserved":False,
                 "realBrokerHard21":False,"globalDrawdownCertified":False}
        outcomes.append(outcome)
    # Contemporaneous event-quote counterfactual min-lot all-proposal spread PnL
    # must never be reported as a causally admissible funded strategy.
    diagnostic={"proposals":len(plan),"entryExitQuotePairs":len(full),
        "quoteEventMissing":missing,"forecastBelowTrainingCost":forecast_rejected,
        "grossBarCloseDirectionalMeanBps":sum(p["side"]*p["realizedBidCloseReturn"]*10000 for p in plan)/len(plan) if plan else None,
        "positiveDirectionalBarCloseFraction":sum(p["side"]*p["realizedBidCloseReturn"]>0 for p in plan)/len(plan) if plan else None}
    survivors=all(o["portfolioEur200QuoteReplay"]["complete_round_trips"]>=30 and
                  D(o["portfolioEur200QuoteReplay"]["closed_net_eur"])>0 and
                  D(o["portfolioEur200QuoteReplay"]["sampled_max_drawdown"])<=D(".30") and
                  D(o["portfolioEur200QuoteReplay"]["conservative_2p6se_weekly_lower_eur"])>0 and
                  o["missingEntryOrExitEventQuotes"]==0 and
                  not o["portfolioEur200QuoteReplay"]["incomplete_marks"] and
                  o["financingCurrentScheduleOutsideHolding"] for o in outcomes)
    return {"schema":"mxm-m15-wick-session-cost-funded-selection-v1","model":MODEL,
            "phase":"SELECTION_60_TRAIN_20_SELECT_20_UNSCORED",
            "trainingExamples":frozen["trainingExamples"],"slippageIsSpreadDerivedHypothesis":True,"usesBrokerTickCountAsSignal":False,"trainTailAbs45MinuteReturn":frozen["train99p5AbsForwardReturn"],
            "selectionWindows":frozen["selectionWindows"],
            "selectionCompleteEligibleWeeks":len(weeks),
            "brokerSourceSpanDays":(bundle["end"]-bundle["start"])/DAY,
            "brokerM15Bars":len(bundle["bars"]),"calibrationQuoteSamples":len(bundle["trainQuoteSamples"]),
            "diagnostic":diagnostic,"fundedScenarios":outcomes,
            "predeclaredSelectionNetSupport":survivors,
            "final20Evaluated":False,"independentConfirmation":False,
            "realFills":False,"historicalTariffConfirmed":False,
            "ordersSubmitted":0,"tradingAuthorized":False,
            "economicQualification":"CONDITIONAL_HISTORICAL_QUOTES_CURRENT_BROKER_TERMS_NEVER_ACTUAL_FILLS"}

def run():
    raw=Path("sealed-output/source.envelope.json").read_bytes()
    receipt=json.loads(Path("sealed-output/receipt.public.json").read_text())
    need(receipt.get("runId")==ORIGINAL_RUN and
         receipt.get("sha256")==ORIGINAL_SHA256 and
         hashlib.sha256(raw).hexdigest()==ORIGINAL_SHA256,
         "ORIGINAL_GENUINE_M15_SOURCE_IDENTITY")
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(key.strip()),"CUSTODY_PRIVATE_KEY_NOT_INSTALLED")
    b=json.loads(unseal_new(raw,key,ORIGINAL_RUN))
    anchor=b.get("nativeReceipt",{})
    need(anchor.get("model")=="EURUSD_M15_SESSION_ANCHORED_TICK_BALANCE_V1" and
         anchor.get("diagnostic",{}).get("proposals")==270 and
         b.get("source")=="Pepperstone-cTrader-OpenAPI" and b.get("readOnly") is True,
         "ORIGINAL_SOURCE_NOT_AUTHENTICATED")
    need(b.get("sourceId")=="Pepperstone-LIVE-readOnly-"+ORIGINAL_RUN,
         "ORIGINAL_BROKER_SOURCE_BINDING")
    # Original anchor outcome never participates in the new model's signals.
    b.pop("nativeReceipt")
    b.pop("raw")
    result=funded_and_diagnostics(b)
    repeated=funded_and_diagnostics(b)
    need(result==repeated,"NONDETERMINISTIC_FUNDED_NET_REPLAY")
    result["originalSourceRunId"]=int(ORIGINAL_RUN)
    result["originalSourceCiphertextSha256"]=ORIGINAL_SHA256
    result["originalCustodyRunVerified"]=True
    result["frozenWickModelUsedPreviouslyObservedSelectionCalendar"]=True
    result["independentFutureConfirmation"]=False
    result["sourceOutcomeUnavailableForOneQuotePair"]=True
    result["entryExitHorizonHours"]=6
    result["ordersSubmitted"]=0
    Path("session-wick-net.public.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print("AUTHENTIC_M15_WICK_SESSION_FINANCED_SELECTION "+json.dumps(result,sort_keys=True),flush=True)

if __name__=="__main__":
    try:run()
    except Exception:
        print("M15_WICK_SESSION_NET_FAILED_CLOSED",flush=True)
        sys.exit(1)

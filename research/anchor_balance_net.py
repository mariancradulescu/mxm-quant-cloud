"""Frozen M15 session-anchored tick-weighted price balance: genuine quotes, funded EUR200 replay.

New economic hypothesis, not a variant of closed price-only, calendar or
conditional-neighbour models. Broker OAuth is view-only; ZERO order messages.
Historical tariffs/actual fills and continuous drawdown are NOT proven.
"""
import base64, hashlib, json, math, os, statistics, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from .collect import authenticate
from .ctrader_transport import StdlibCTraderTransport
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .decode import need,decode_side
from .economic_source import _windows,_bounded_server_window
from .intraday_net import reconstruct
from .custody_new import checked_public
from .custody import seal_new,unseal_new
from .funded_replay import Quote, Contract, Decision, FundedReplay, D, IncompleteEvidence
from .anchor_signal import signals

SYMBOL="EURUSD"
YEAR_DAYS=370
HOUR=900000
DAY=86400000
MAX_REQUESTS=9000
SLOTS=(9,11,13,15,17)
SLIP_MULTIPLIERS=("0.5","1","2")
MODEL="EURUSD_M15_SESSION_ANCHORED_TICK_BALANCE_V1"

def reqcheck(ok,reason):
    need(ok,reason)

def eligible_weeks(lo,hi):
    dt=datetime.fromtimestamp(lo/1000,timezone.utc)
    dt=(dt-timedelta(days=dt.weekday())).replace(hour=0,minute=0,second=0,microsecond=0)
    if int(dt.timestamp()*1000)<lo:dt+=timedelta(days=7)
    out=[]
    while int((dt+timedelta(days=5)).timestamp()*1000)<=hi:
        out.append(int(dt.timestamp()*1000))
        dt+=timedelta(days=7)
    return out


def commission_eur(c,units,price,eur_bid,eur_ask):
    r=D(str(c["preciseTradingCommissionRate"]));lot=D(str(c["lotSize"]))/100
    kind=int(c["commissionType"])
    if kind==1:usd=r/D("100000000")*units*price/D("1000000")
    elif kind in (2,4):usd=r/D("100000000")*units/lot
    elif kind==3:usd=r/D("100000")/100*units*price
    else:raise IncompleteEvidence("COMMISSION_TYPE_UNSUPPORTED")
    floor=D(str(c["preciseMinCommission"]))/D("100000000")
    if int(c["minCommissionType"])==1:
        currency=c.get("minCommissionAsset")
        if currency=="EUR":
            return max(usd/eur_bid,floor)
        if currency!="USD":raise IncompleteEvidence("BROKER_MIN_CURRENCY_UNKNOWN")
    return max(usd,floor)/eur_bid

def financing_proven(c):
    period=c.get("swapPeriod");minute=c.get("swapTime")
    return period==24 and isinstance(minute,int) and (minute<360 or minute>1080) and 0<=minute<1440

def read_quote(bundle,t):
    row=bundle["quotes"].get(str(t))
    if row is None:return None
    reqcheck(row["time"]>=t+1000 and row["time"]<=t+11000 and row["bid"]>0 and row["ask"]>=row["bid"],"EVENT_QUOTE_LATENCY_OR_PRICE")
    return row

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
    return {"schema":"mxm-m15-anchor-cost-funded-selection-v1","model":MODEL,
            "phase":"SELECTION_60_TRAIN_20_SELECT_20_UNSCORED",
            "trainingExamples":frozen["trainingExamples"],"slippageIsSpreadDerivedHypothesis":True,"tickVolumeIsNotExchangeVolume":True,"trainTailAbs45MinuteReturn":frozen["train99p5AbsForwardReturn"],
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
    run_id=os.environ["GITHUB_RUN_ID"];pubkey=checked_public(Path("new-source-recipient"),run_id)
    t=StdlibCTraderTransport();raw=[]
    def req(q,kind):
        reqcheck(len(raw)<MAX_REQUESTS,"M15_ANCHOR_REQUEST_BUDGET")
        a=t.request(q)
        reqcheck(isinstance(a,kind) and a.IsInitialized() and a.ctidTraderAccountId==account,"BROKER_RESPONSE_BINDING")
        raw.append({"type":type(a).__name__,"protobuf":base64.b64encode(a.SerializeToString()).decode()})
        return a
    try:
        account=authenticate(t)
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes).trader
        reqcheck(trader.HasField("brokerName") and "pepperstone" in trader.brokerName.lower() and trader.HasField("leverageInCents"),"BROKER_EUR_ACCOUNT_UNVERIFIED")
        assets={a.assetId:a.name for a in req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes).asset}
        reqcheck(assets.get(trader.depositAssetId)=="EUR","EUR_DEPOSIT_REQUIRED")
        pairs=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        choices=[s for s in pairs.symbol if s.enabled and s.symbolName==SYMBOL]
        reqcheck(len(choices)==1 and assets.get(choices[0].baseAssetId)=="EUR" and assets.get(choices[0].quoteAssetId)=="USD","EURUSD_NOT_SUPPORTED")
        s=choices[0];detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,symbolId=[s.symbolId]),m.ProtoOASymbolByIdRes).symbol
        reqcheck(len(detail)==1 and detail[0].symbolId==s.symbolId,"BROKER_CONTRACT")
        c=detail[0]
        fields=("minVolume","stepVolume","maxVolume","lotSize","preciseTradingCommissionRate","preciseMinCommission","pnlConversionFeeRate","swapLong","swapShort","swapCalculationType","digits","pipPosition")
        reqcheck(all(c.HasField(f) for f in fields),"MISSING_BROKER_CONTRACT_FIELDS")
        term={f:getattr(c,f) for f in fields}
        for f in ("commissionType","minCommissionType","minCommissionAsset"):
            term[f]=getattr(c,f)
        for f in ("swapPeriod","swapTime"):
            term[f]=getattr(c,f) if c.HasField(f) else None
        reqcheck(term["pipPosition"]==4 and int(term["minVolume"])%100==0,"EURUSD_CONTRACT_SCALE")
        margin=req(m.ProtoOAExpectedMarginReq(ctidTraderAccountId=account,symbolId=s.symbolId,volume=[c.minVolume]),m.ProtoOAExpectedMarginRes)
        reqcheck(margin.HasField("moneyDigits") and len(margin.margin)==1 and margin.margin[0].volume==c.minVolume,"MINIMUM_MARGIN_UNAVAILABLE")
        margin_eur=max(margin.margin[0].buyMargin,margin.margin[0].sellMargin)/10**margin.moneyDigits
        reqcheck(margin_eur>0,"BROKER_MARGIN_NONPOSITIVE")
        enddt=datetime.now(timezone.utc).replace(hour=0,minute=0,second=0,microsecond=0)
        end=int(enddt.timestamp()*1000);start=end-YEAR_DAYS*DAY
        def history(lo,hi,depth=0):
            reqcheck(depth<20,"M15_PAGINATION_DEPTH")
            out=req(m.ProtoOAGetTrendbarsReq(ctidTraderAccountId=account,symbolId=s.symbolId,period=e.M15,fromTimestamp=lo,toTimestamp=hi),m.ProtoOAGetTrendbarsRes)
            reqcheck(out.period==e.M15 and out.HasField("hasMore"),"M15_BROKER_PAGE")
            if out.hasMore:
                mid=(lo+hi)//2
                reqcheck(hi>lo,"M15_PAGE_STUCK")
                return history(lo,mid,depth+1)+history(mid+1,hi,depth+1)
            return _bounded_server_window(out.trendbar,lo,hi,15)
        barrows={}
        for lo,hi in _windows(start,end,4):
            for x in history(lo,hi):
                reqcheck(x[0] not in barrows,"DUPLICATE_M15")
                if x[0]+HOUR<=end:
                    barrows[x[0]]={"t":x[0],"o":x[2],"h":x[3],"l":x[4],"c":x[5],"v":x[6]}
        bars=[barrows[k] for k in sorted(barrows)]
        reqcheck(len(bars)>20000 and bars[-1]["t"]+HOUR-bars[0]["t"]>=365*DAY,"BROKER_M15_YEAR_SUPPORT")
        b={"schema":"mxm-m15-session-anchor-net-v1","source":"Pepperstone-cTrader-OpenAPI",
            "sourceId":"Pepperstone-LIVE-readOnly-"+run_id,"readOnly":True,
            "start":start,"end":end,"bars":bars,"contract":term,
            "marginEurMin":margin_eur,"quotes":{},"trainQuoteSamples":[]}
        def quote(tm):
            sides=[];sraw=[]
            for side in (e.BID,e.ASK):
                r=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=s.symbolId,
                    type=side,fromTimestamp=tm+1000,toTimestamp=tm+11000),m.ProtoOAGetTickDataRes)
                reqcheck(r.HasField("hasMore"),"TICK_PAGINATION_UNKNOWN")
                sides.append(None if r.hasMore else decode_side(r.tickData,tm+1000,tm+11000))
                sraw.append(r.SerializeToString())
            row=reconstruct(*sides,tm+1000) if all(x is not None for x in sides) else None
            if row is not None:
                row["sha"]=hashlib.sha256(b"".join(sraw)).hexdigest()
            return row
        cut=start+(end-start)*6//10
        spreads=[];moves=[]
        for j in range(1,9):
            d=datetime.fromtimestamp((start+(cut-start)*j//9)/1000,timezone.utc).replace(hour=12,minute=0,second=0,microsecond=0)
            while d.weekday()>4:d-=timedelta(days=1)
            tm=int(d.timestamp()*1000)
            reqcheck(start<tm<cut,"TRAIN_QUOTE_OUTSIDE_TRAIN")
            q=quote(tm);reqcheck(q is not None,"TRAIN_BID_ASK_MISSING")
            b["trainQuoteSamples"].append({"time":tm,"bid":q["bid"],"ask":q["ask"],"sha":q["sha"]})
            spreads.append((q["ask"]-q["bid"])/100000)
            moves.append(max(1/100000,(q["ask"]-q["bid"])/100000))
        b["trainSpreadPrice"]=max(spreads)
        b["trainSlippagePrice"]=max(1/100000,max(moves)/2)
        screen=b["trainQuoteSamples"][0]
        b["screenEurAsk"]=screen["ask"]/100000
        b["screenMinCommissionEur"]=str(commission_eur(term,int(term["minVolume"])//100,
             D(str(b["screenEurAsk"])),D(str(screen["bid"]))/100000,D(str(screen["ask"]))/100000))
        planned=signals(b)
        print("M15_ANCHOR_TRAIN_AND_SELECTION_PREFLIGHT "+json.dumps({"train":planned["trainingExamples"],"selection":planned["selectionWindows"],"proposals":len(planned["plan"]),"weeks":len(planned["eligibleMondayUtcMs"])}),flush=True)
        events=sorted({t for p in planned["plan"] for t in (p["signal"],p["exit"])})
        reqcheck(len(raw)+2*len(events)<MAX_REQUESTS,"EVENT_QUOTE_REQUEST_BUDGET")
        for ix,tm in enumerate(events):
            b["quotes"][str(tm)]=quote(tm)
            if ix%120==0:print("M15_ANCHOR_AUTHENTIC_QUOTE_PROGRESS "+str(ix)+"/"+str(len(events)),flush=True)
        result=funded_and_diagnostics(b)
        b["raw"]=raw;b["nativeReceipt"]=result
        cipher=seal_new(json.dumps(b,sort_keys=True).encode(),pubkey,run_id)
        dest=Path("sealed-output");dest.mkdir(exist_ok=True)
        (dest/"source.envelope.json").write_bytes(cipher)
        (dest/"receipt.public.json").write_text(json.dumps({"schema":"mxm.anchor-net-sealed.v1","runId":run_id,
            "sha256":hashlib.sha256(cipher).hexdigest(),"ordersSubmitted":0},sort_keys=True))
        Path("anchor-net.public.json").write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
        print("AUTHENTIC_M15_ANCHOR_FUNDED_SELECTION "+json.dumps(result,sort_keys=True),flush=True)
    finally:t.close()

def readback():
    run_id=os.environ["GITHUB_RUN_ID"]
    raw=Path("sealed-output/source.envelope.json").read_bytes()
    pub=json.loads(Path("sealed-output/receipt.public.json").read_text())
    reqcheck(pub.get("runId")==run_id and pub.get("sha256")==hashlib.sha256(raw).hexdigest(),"FUNDED_SEALED_SOURCE_DIGEST")
    b=json.loads(unseal_new(raw,os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),run_id))
    old=b.pop("nativeReceipt");b.pop("raw")
    now=funded_and_diagnostics(b)
    reqcheck(now==old and old["ordersSubmitted"]==0 and old["final20Evaluated"] is False,"ANCHOR_FUNDED_CUSTODY_PARITY_FAILED")
    now["custodyParity"]=True
    now["sourceCiphertextSha256"]=pub["sha256"]
    now["runId"]=run_id
    Path("anchor-net.public.json").write_text(json.dumps(now,indent=2,sort_keys=True)+"\n")
    print("AUTHENTIC_M15_ANCHOR_CUSTODY_PARITY "+json.dumps(now,sort_keys=True),flush=True)

if __name__=="__main__":
    try:
        readback() if "--readback" in sys.argv else run()
    except Exception as exc:
        from .guard import CaptureContractError
        print(str(exc) if isinstance(exc,CaptureContractError) and str(exc).isupper() and str(exc).replace("_","").isalnum() else "ANCHOR_EXECUTION_FAILED_DETAIL_WITHHELD",flush=True)
        sys.exit(1)

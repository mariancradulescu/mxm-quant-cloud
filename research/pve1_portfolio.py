"""PVE1 common EUR200 conditional portfolio using existing native C# selector.

Reuse RCP1's generic funded Book/holding mark primitives ONLY, never its
frozen predictive model, scenarios, params, forecasts, or economic results.
Every decision is based on independent earlier historical M5 source states.
"""
from .portfolio_economic_replay import native
from .rcp1_portfolio import Book,path,scenario_rows,funding,STATES,WEEK,MS,HR
MAX_HOLD_MS=240*60000

def request(book,t,forecasts,views,cost,p,variant):
    mark=book.mark(t,views,cost)
    if mark is None or book.frozen or not book.intact():return None,{}
    history=[t-w*WEEK for w in STATES]
    latest=max(history)+MAX_HOLD_MS+MS
    if min(history)<p["phase"]["start"] or latest>=t:return None,{}
    # ALL already-open positions contribute their adverse historical scenario
    # and present margin to the next shared-capital decision.
    open_curves={}
    for pid,pos in book.open.items():
        remaining=max(MS,min(MAX_HOLD_MS,pos["due"]-t))
        a=scenario_rows(views,pos["symbol"],t,remaining,pos["side"],
                        pos["notional"]*pos["units"])
        if a is None:return None,{}
        open_curves[pid]=a
    baseline=[]
    for i,old in enumerate(history):
        net=0.;loss=0.;peak=0.
        for pid,pos in book.open.items():
            z=open_curves[pid][i]
            remaining=max(MS,min(MAX_HOLD_MS,pos["due"]-t))
            carry=funding(cost[pos["symbol"]],pos["side"],t,t+remaining,
                          pos["notional"]*pos["units"])
            if carry is None:return None,{}
            net+=z["net"]-carry
            loss+=max(0.,-z["worst"])+pos["notional"]*pos["units"]*cost[pos["symbol"]]["stressBps"]/10000
            peak+=z["best"]
        baseline.append(dict(StateId="PVE1/"+str(old),
            KnownAt=old+MAX_HOLD_MS+MS,Estimation=True,
            NetEur=net,LossEur=loss,PeakEur=peak,MarginEur=mark["margin"]))
    candidates=[];complete=[];lookup={}
    frictionKey="stressBps" if variant=="FULL_STRESS" else "adverseBps"
    for f in forecasts:
        s=f["symbol"];h=f["horizon"];c=cost[s]
        if f["knownAt"]!=t:raise ValueError("PVE1_NONCAUSAL_FORECAST_CLOCK")
        if any(x["symbol"]==s for x in book.open.values()):continue
        boundary=p["phase"]["selectionEnd"] if t<p["phase"]["selectionEnd"] else p["phase"]["end"]
        if t+MS+h*60000>=boundary:continue
        pred=f["predBps"]
        if pred==0:continue
        side=1 if pred>0 else -1
        carry=funding(c,side,t+MS,t+MS+h*60000,c["minimumNotionalEur"])
        if carry is None:
            book.rejections["CURRENT_FUNDING_UNAVAILABLE"]+=1;continue
        modeledNet=(abs(pred)-c[frictionKey])*c["minimumNotionalEur"]/10000-carry
        if modeledNet<=0:
            book.rejections["CALENDAR_GROSS_BELOW_ADVERSE_COST"]+=1;continue
        if mark["freeMargin"]<=c["minimumMarginEur"]:
            book.rejections["NOT_FINANCED_AT_MINIMUM_BROKER_VOLUME"]+=1;continue
        observations=scenario_rows(views,s,t,MS+h*60000,side,c["minimumNotionalEur"])
        if observations is None:
            book.rejections["HISTORICAL_JOINT_EXPOSURE_PATH_UNKNOWN"]+=1;continue
        samples=[]
        for old in history:
            z=path(views,s,old+MS,h*60000,side,c["minimumNotionalEur"])
            if z is None:
                samples=[];break
            samples.append(z)
        if len(samples)!=len(history):
            book.rejections["DELAYED_ENTRY_HISTORIC_PATH_UNKNOWN"]+=1;continue
        avg=sum(z["net"] for z in samples)/len(samples)
        cases=[]
        for old,z in zip(history,samples):
            loss=max(0.,-z["worst"])+c["stressBps"]*c["minimumNotionalEur"]/10000
            cases.append(dict(StateId="PVE1/"+str(old),KnownAt=old+MS+h*60000,
                Estimation=True,
                NetPerUnitEur=modeledNet+z["net"]-avg,
                FixedCostEur=0,LossPerUnitEur=loss,
                PeakPerUnitEur=z["best"]))
        cap=min(3,int(max(0,mark["freeMargin"])//c["minimumMarginEur"]))
        if cap<1:continue
        pid="PVE1/"+variant+"/"+s+"/"+str(h)+"/"+str(t)
        grid=dict(EquityEur=mark["equity"],CertifiedPeakEur=0,
            FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
            MaximumUnits=cap,MarginPerUnitEur=c["minimumMarginEur"],
            BrokerStopoutEquityToMargin=0,Reconciled=False,
            CompleteJointRiskEvidence=False,EffectiveIndependentBlocks=4,
            UncertaintyMultiplier=1)
        candidates.append(dict(Id=pid,Candidate=f['family'],Symbol=s,
            RedundancyKey=s+"/"+str(t),Direction=side,
            AvailableAt=t,CalibratedThrough=latest,Level=1,
            ExecutionEvidenceComplete=False,VolumeGrid=grid,Scenarios=cases))
        complete.append(pid)
        lookup[pid]=dict(symbol=s,family=FAMILY,horizon=h,side=side,pred=pred)
    account=dict(EquityEur=mark["equity"],PeakReferenceEur=max(300.,book.high),
        FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
        MaximumUnits=3,MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
        EffectiveIndependentBlocks=4,UncertaintyMultiplier=1)
    return dict(Scope="PVE1_CALENDAR_CONDITIONAL_RESEARCH_NOT_CERTIFIED",
        CommonHorizonMinutes=0,Clock=t,Account=account,
        Baseline=baseline,Opportunities=candidates,
        LedgerReconciled=True,ScenarioCompleteOpportunityIds=complete),lookup

def evaluate(views,forecasts,cost,p):
    variants=("FULL","FULL_STRESS")
    books={name:Book("PVE1_"+name,initial=300.) for name in variants}
    clocks=[t for t in sorted(forecasts) if p["phase"]["developmentEnd"]<=t<p["phase"]["end"]]
    last_phase=None
    for t in clocks:
        phase="selection" if t<p["phase"]["selectionEnd"] else "exposed_audit"
        asks=[];lookups=[];names=[]
        for name,book in books.items():
            book.advance(t,views,cost)
            if phase!=last_phase:book.phaseCash[phase]=book.cash
            req,lookup=request(book,t,forecasts[t],views,cost,p,name)
            if req is None:
                book.rejections["INCOMPLETE_JOINT_NATIVE_RISK_OBSERVATION"]+=1
                continue
            # No uncosted proposals: native selector is not called to manufacture
            # activity. Existing positions still advance even when no offer.
            if not req["Opportunities"]:continue
            asks.append(req);lookups.append(lookup);names.append(name)
        last_phase=phase
        if not asks:continue
        answers=native(asks,"--estimate-portfolio-opportunities-batch")
        if len(answers)!=len(asks):raise ValueError("PVE1_NATIVE_BATCH_LENGTH")
        for name,answer,lookup in zip(names,answers,lookups):
            book=books[name]
            book.calls+=1;book.nativeOffered+=len(lookup)
            if answer.get("Qualified",False):
                raise ValueError("PVE1_UNSUPPORTED_NATIVE_TRADING_QUALIFICATION")
            for row in answer["Declined"]:
                book.rejections["NATIVE_"+str(row["Reason"])]+=1
            for row in answer["Allocations"]:
                book.fill_after_decision(t,row,lookup,views,cost,name,p)
    reports={name:book.finish(p["phase"]["end"],views,cost,p) for name,book in books.items()}
    reports["FLAT_NEUTRAL"]=dict(cashEur=300.,netClosedEur=0.,modeledRoundTrips=0,
       unresolvedPositions=0,maxSampledDrawdown=0.,nativeCalls=0,nativeAllocations=0,
       hard21EligibleWeeksPassed=0,eligibleWeeks=26)
    if any(not x["capitalContinuityReconciled"] for x in reports.values()
           if "capitalContinuityReconciled" in x):
        raise ValueError("PVE1_SINGLE_CASH_BROKEN")
    if reports["FULL"]["unresolvedPositions"]==0 and reports["FULL_STRESS"]["unresolvedPositions"]==0:
        reports["FULL_STRESS"]["conditionalCounterfactualDifferenceEur"]=round(
            reports["FULL"]["netClosedEur"]-reports["FULL_STRESS"]["netClosedEur"],8)
    else:
        reports["FULL_STRESS"]["conditionalCounterfactualDifferenceEur"]=None
    # Only the thirteen globally exposed audit weeks were eligible for the
    # new selection-gated EUR300 conditional portfolio. Selection had no trades.
    # Book.finish still holds every weekly counter and sampled risk mark.
    for item in reports.values():
        item["initialCashEur"]=300.
        item["eligibleWeeks"]=13
        if "exposedAuditWeeklyRoundTrips" in item:
            counts=item["exposedAuditWeeklyRoundTrips"]
            item["hard21EligibleWeeksPassed"]=sum(x>=21 for x in counts)
            item["minimumRoundTripsPerEligibleWeek"]=min(counts)
        item["brokerConfirmedNetEur"]=None
        item["independentConfirmation"]=False
    return reports

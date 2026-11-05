"""PVE2 modeled EUR300 single-capital economic attribution via existing native C#.

No second allocator, historical broker fills, live orders, or Cloud activation.
RCP1's generic conditional book is an accounting/holding helper ONLY; none of
its closed predictor, threshold, models, forecasts or economic outcomes run.
"""
from collections import defaultdict
from .portfolio_economic_replay import native
from .rcp1_portfolio import Book,path,scenario_rows,funding,STATES,WEEK,MS,HR

MAX_HOLD=240*60000

def request(book,t,offers,views,cost,p,variant):
    mark=book.mark(t,views,cost)
    if mark is None or book.frozen or not book.intact():return None,{}
    history=[t-w*WEEK for w in STATES]
    latest=max(history)+MAX_HOLD+MS
    if min(history)<p["calendar"]["start"] or latest>=t:return None,{}
    oldOpen={}
    for key,pos in book.open.items():
        remaining=max(MS,min(MAX_HOLD,pos["due"]-t))
        a=scenario_rows(views,pos["symbol"],t,remaining,pos["side"],
            pos["notional"]*pos["units"])
        if a is None:return None,{}
        oldOpen[key]=a
    baseline=[]
    for i,old in enumerate(history):
        net=0.;loss=0.;peak=0.
        for key,pos in book.open.items():
            curve=oldOpen[key][i]
            remaining=max(MS,min(MAX_HOLD,pos["due"]-t))
            carry=funding(cost[pos["symbol"]],pos["side"],t,t+remaining,
                pos["notional"]*pos["units"])
            if carry is None:return None,{}
            net+=curve["net"]-carry
            loss+=max(0.,-curve["worst"])+pos["notional"]*pos["units"]*cost[pos["symbol"]]["stressBps"]/10000
            peak+=curve["best"]
        baseline.append(dict(StateId="PVE2/"+str(old),
            KnownAt=old+MAX_HOLD+MS,Estimation=True,
            NetEur=net,LossEur=loss,PeakEur=peak,MarginEur=mark["margin"]))
    lookup={};proposals=[]
    keyCost="stressBps" if variant=="FULL_STRESS" else "adverseBps"
    for f in offers:
        if f["knownAt"]!=t or f["family"]!="DAILY_TREND_H1_PULLBACK":
            raise ValueError("PVE2_FUTURE_OR_UNREGISTERED_SIGNAL")
        s=f["symbol"];h=f["horizon"];side=f["side"];terms=cost[s]
        if side not in (-1,1) or h not in p["fixedSignal"]["holdingMinutes"]:
            raise ValueError("PVE2_UNREGISTERED_SIDE_OR_HORIZON")
        if any(x["symbol"]==s for x in book.open.values()):continue
        due=t+MS+h*60000
        if due>=p["calendar"]["end"]:continue
        predicted=f["predBps"]
        if predicted<=0:continue
        margin=terms["minimumMarginEur"]
        notional=terms["minimumNotionalEur"]
        carry=funding(terms,side,t+MS,due,notional)
        if carry is None:
            book.rejections["CURRENT_TERM_FINANCING_UNKNOWN"]+=1;continue
        expected=(predicted-terms[keyCost])*notional/10000-carry
        if expected<=0:
            book.rejections["EXPECTED_GROSS_BELOW_CURRENT_ADVERSE_COST"]+=1;continue
        if mark["freeMargin"]<=margin:
            book.rejections["BROKER_MINIMUM_MARGIN_NOT_FINANCED"]+=1;continue
        # Eight predecision weekly scenario paths; never peek at current exit.
        observations=scenario_rows(views,s,t,MS+h*60000,side,notional)
        if observations is None:
            book.rejections["PREDECISION_RISK_PATH_NOT_OBSERVED"]+=1;continue
        samples=[]
        for old in history:
            z=path(views,s,old+MS,h*60000,side,notional)
            if z is None:samples=[];break
            samples.append(z)
        if len(samples)!=len(history):
            book.rejections["DELAYED_HISTORY_NOT_OBSERVED"]+=1;continue
        average=sum(x["net"] for x in samples)/len(samples)
        states=[]
        for old,z in zip(history,samples):
            worst=max(0.,-z["worst"])+terms["stressBps"]*notional/10000
            states.append(dict(StateId="PVE2/"+str(old),
                KnownAt=old+MS+h*60000,Estimation=True,
                NetPerUnitEur=expected+z["net"]-average,FixedCostEur=0,
                LossPerUnitEur=worst,PeakPerUnitEur=z["best"]))
        cap=min(p["economicPolicy"]["maxMinimumVolumeMultiples"],
            int(max(0.,mark["freeMargin"])//margin))
        if cap<1:continue
        candidate_id="PVE2/"+variant+"/"+s+"/"+str(h)+"/"+str(t)
        grid=dict(EquityEur=mark["equity"],CertifiedPeakEur=0,
            FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
            MaximumUnits=cap,MarginPerUnitEur=margin,
            BrokerStopoutEquityToMargin=0,Reconciled=False,
            CompleteJointRiskEvidence=False,EffectiveIndependentBlocks=4,
            UncertaintyMultiplier=1)
        proposals.append(dict(Id=candidate_id,Candidate=f["family"],Symbol=s,
            RedundancyKey=s+"/"+str(t),Direction=side,
            AvailableAt=t,CalibratedThrough=latest,Level=1,
            ExecutionEvidenceComplete=False,VolumeGrid=grid,
            Scenarios=states))
        lookup[candidate_id]=dict(symbol=s,family=f["family"],horizon=h,side=side,
            pred=f["predBps"])
    account=dict(EquityEur=mark["equity"],PeakReferenceEur=max(300.,book.high),
        FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
        MaximumUnits=3,MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
        EffectiveIndependentBlocks=4,UncertaintyMultiplier=1)
    req=dict(Scope="PVE2_DAILY_PULLBACK_EUR300_CONDITIONAL_ONLY_NOT_CERTIFIED",
        CommonHorizonMinutes=0,Clock=t,Account=account,
        Baseline=baseline,Opportunities=proposals,LedgerReconciled=True,
        ScenarioCompleteOpportunityIds=list(lookup))
    return req,lookup

def evaluate(views,offers,cost,p):
    # Counterfactual stress and central books are never joined into a wallet.
    books={kind:Book("PVE2_"+kind,initial=300.)
           for kind in ("FULL","FULL_STRESS")}
    lastPhase=None
    for clock in sorted(offers):
        if clock<p["calendar"]["selectionEnd"] or clock>=p["calendar"]["end"]:
            raise ValueError("PVE2_NONPROSPECTIVE_OFFER_CLOCK")
        pending=[];lookups=[];names=[]
        for name,book in books.items():
            book.advance(clock,views,cost)
            if lastPhase is None:book.phaseCash["globally_exposed_audit"]=book.cash
            req,lookup=request(book,clock,offers[clock],views,cost,p,name)
            if req is None:
                book.rejections["UNCERTIFIED_POSITION_MARK_OR_HISTORY"]+=1
                continue
            if not req["Opportunities"]:continue
            pending.append(req);lookups.append(lookup);names.append(name)
        lastPhase="globally_exposed_audit"
        if not pending:continue
        result=native(pending,"--estimate-portfolio-opportunities-batch")
        if len(result)!=len(pending):raise ValueError("PVE2_NATIVE_RESPONSE_LENGTH")
        for name,out,lookup in zip(names,result,lookups):
            book=books[name]
            book.calls+=1
            book.nativeOffered+=len(lookup)
            if out.get("Qualified",False) or out.get("OrdersEnabled",False):
                raise ValueError("PVE2_UNAUTHORIZED_ECONOMIC_OR_TRADING_QUALIFICATION")
            for declined in out["Declined"]:
                book.rejections["NATIVE_"+str(declined["Reason"])]+=1
            for allocated in out["Allocations"]:
                book.fill_after_decision(clock,allocated,lookup,views,cost,name,
                    {"phase":{"selectionEnd":p["calendar"]["selectionEnd"],
                        "end":p["calendar"]["end"]}})
    reports={name:book.finish(p["calendar"]["end"],views,cost,
        {"phase":{"start":p["calendar"]["start"],
             "developmentEnd":p["calendar"]["developmentEnd"],
             "selectionEnd":p["calendar"]["selectionEnd"],
             "end":p["calendar"]["end"]}})
        for name,book in books.items()}
    for item in reports.values():
        item["initialCapitalEur"]=300.
        item["prospectivelyEligibleWeeks"]=13
        eligible=item["exposedAuditWeeklyRoundTrips"]
        item["eligibleWeeksPassingHard21"]=sum(x>=21 for x in eligible)
        item["minimumEligibleWeeklyCompleted"]=min(eligible)
        item["brokerCertifiedNetEur"]=None
        item["independentConfirmation"]=False
        item["costModelOnly"]=True
        item["globalContinuousDrawdownCertified"]=False
        if not item["capitalContinuityReconciled"]:
            raise ValueError("PVE2_SINGLE_300_CASH_IDENTITY_MISMATCH")
    reports["FLAT_NEUTRAL"]=dict(initialCapitalEur=300.,
        cashEur=300.,netClosedEur=0.,modeledRoundTrips=0,
        prospectivelyEligibleWeeks=13,eligibleWeeksPassingHard21=0,
        minimumEligibleWeeklyCompleted=0,nativeCalls=0,
        capitalContinuityReconciled=True,brokerCertifiedNetEur=None,
        independentConfirmation=False,globalContinuousDrawdownCertified=False)
    if all(x["unresolvedPositions"]==0 for x in reports.values()
           if "unresolvedPositions" in x):
        reports["FULL_STRESS"]["conditionalDifferenceFromAdverseEur"]=round(
            reports["FULL"]["netClosedEur"]-reports["FULL_STRESS"]["netClosedEur"],8)
    else:
        reports["FULL_STRESS"]["conditionalDifferenceFromAdverseEur"]=None
    return reports

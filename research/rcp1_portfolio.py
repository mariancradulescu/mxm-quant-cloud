"""RCP1 conditional common-capital research: delayed next M5 entry, native joint risk.

Reuses unchanged C# OpportunityOrchestrator and original authentic-source
pricing context. Every alternative starts EUR200 only for counterfactual
comparison, not simultaneous funded capital. Actual original historical
broker executions are unknown. No broker orders, Cloud activation or replay
of a closed predictive model.
"""
import math
from bisect import bisect_left
from collections import defaultdict
from .portfolio_economic_replay import native
from .rcp1_causal import HR,MS,WEEK,FAMILIES

DAY=24*HR
MAX_HORIZON_MINUTES=4320
MAX_HORIZON_MS=MAX_HORIZON_MINUTES*60000
STATES=tuple(range(9,1,-1))

def funding(c,side,start,end,notional):
    if end<=start:return 0.
    minute=c["swapMinute"]
    first=(start//DAY)*DAY+minute*60000
    if first<=start:first+=DAY
    n=0
    while first<=end:
        n+=1
        first+=DAY
    if n==0:return 0.
    if not c["fundingKnown"]:return None
    debit=c["longDailyDebitBps"] if side>0 else c["shortDailyDebitBps"]
    return 3*debit*n*notional/10000

def path(views,s,at,steps,side,notional):
    """No hindsight fill: require exact M5 source at BOTH clocks and H1 marks."""
    end=at+steps
    prices=views[s]["price"]
    start=prices.get(at)
    finish=prices.get(end)
    if not start or not finish or steps<=0:return None
    stamps=[at+k*HR for k in range(1,steps//HR+1)]
    if not stamps or stamps[-1]!=end:stamps.append(end)
    if any(t not in prices for t in stamps):return None
    returns=[side*notional*math.log(prices[t]/start) for t in stamps]
    return dict(net=returns[-1],worst=min(0.,*returns),best=max(0.,*returns),
                marks=len(stamps),clockStart=at,clockEnd=end)

class Book:
    def __init__(self,name,initial=200.):
        self.name=name;self.cash=initial;self.start=initial
        self.open={};self.netClosed=0.;self.closed=[]
        self.high=initial;self.drawdown=0.;self.maxOpen=0;self.peakMargin=0.
        self.lastEvent=None;self.knownMarks=0;self.unknownMarks=0;self.delayed=0
        self.allocations=0;self.calls=0;self.nativeOffered=0
        self.rejections=defaultdict(int);self.frozen=False;self.phaseCash={}
        self.rejectedExecutionSource=0;self.admissionExamples=[]
    def intact(self):
        residual=sum(p["friction"] for p in self.open.values())
        return abs(self.cash-(self.start+self.netClosed-residual)) < .00001
    def mark(self,t,views,cost):
        if not self.intact():raise ValueError("RCP1_SINGLE_CASH_IDENTITY_BROKEN")
        floating=0.;margin=0.
        for p in self.open.values():
            price=views[p["symbol"]]["price"].get(t)
            if not price:
                self.unknownMarks+=1
                return None
            x=p["side"]*p["units"]*p["notional"]*math.log(price/p["entryPrice"])
            carry=funding(cost[p["symbol"]],p["side"],p["entryAt"],t,p["notional"]*p["units"])
            if carry is None:
                self.unknownMarks+=1;return None
            floating+=x-carry
            margin+=p["margin"]
        equity=self.cash+floating
        self.high=max(self.high,equity)
        if self.high>0:self.drawdown=max(self.drawdown,1-equity/self.high)
        self.frozen=self.frozen or self.drawdown>=.30 or equity<=0
        self.peakMargin=max(self.peakMargin,margin)
        self.knownMarks+=1
        return dict(equity=equity,margin=margin,freeMargin=equity-margin)
    def settle(self,t,views,cost):
        for pid,pos in list(sorted(self.open.items())):
            if pos["due"]>t:continue
            data=views[pos["symbol"]];ts=data["observed"]
            index=bisect_left(ts,pos["due"])
            if index>=len(ts) or ts[index]>t:continue
            closeAt=ts[index];closing=data["price"].get(closeAt)
            if not closing:continue
            carry=funding(cost[pos["symbol"]],pos["side"],pos["entryAt"],closeAt,
                          pos["notional"]*pos["units"])
            if carry is None:
                self.rejections["UNCERTIFIED_CARRY_ON_EXIT"]+=1;continue
            gross=pos["side"]*pos["notional"]*pos["units"]*math.log(closing/pos["entryPrice"])
            net=gross-carry-pos["friction"]
            self.cash+=gross-carry
            self.netClosed+=net
            self.closed.append(dict(position=pid,symbol=pos["symbol"],family=pos["family"],
                decisionAt=pos["decisionAt"],entryAt=pos["entryAt"],
                closingAt=closeAt,scheduledCloseAt=pos["due"],
                conditionalNetEur=net,conditionalGrossEur=gross,
                currentTermCarryEur=carry,modeledFrictionEur=pos["friction"],
                executionDelayed=closeAt>pos["due"]))
            if closeAt>pos["due"]:self.delayed+=1
            del self.open[pid]
        if not self.intact():raise ValueError("RCP1_CASH_RECONCILIATION_AFTER_CLOSE")
    def advance(self,t,views,cost):
        if self.lastEvent is None:
            self.lastEvent=t
            return self.mark(t,views,cost)
        if t<self.lastEvent:raise ValueError("RCP1_CLOCK_REVERSED")
        if not self.open:
            self.lastEvent=t
            return self.mark(t,views,cost)
        # Within an open holding, evaluate every actual hourly mark and each
        # scheduled exit, not only times at which a *new* signal is generated.
        h=((self.lastEvent//HR)+1)*HR
        moments=set()
        while h<=t:
            moments.add(h);h+=HR
        for p in self.open.values():
            if self.lastEvent<p["due"]<=t:moments.add(p["due"])
        moments.add(t)
        last=None
        for at in sorted(moments):
            # Observe pre-close floating equity before crediting close.
            last=self.mark(at,views,cost)
            self.settle(at,views,cost)
            last=self.mark(at,views,cost)
        self.lastEvent=t
        return last
    def fill_after_decision(self,t,choice,lookup,views,cost,variant,proto):
        key=choice["Id"]
        if key not in lookup:raise ValueError("RCP1_NATIVE_UNKNOWN_ID")
        data=lookup[key];s=data["symbol"]
        units=float(choice["Units"])
        if units<1 or units>3 or abs(units-round(units))>1e-8:
            raise ValueError("RCP1_NATIVE_NONBROKER_STEP")
        if any(p["symbol"]==s for p in self.open.values()):
            self.rejections["SAME_SYMBOL_ALREADY_HELD"]+=1;return False
        entryAt=t+MS   # next independently completed bar: never decision t
        entry=views[s]["price"].get(entryAt)
        if not entry:
            self.rejections["NO_NEXT_M5_BAR_NO_MODELED_FILL"]+=1
            self.rejectedExecutionSource+=1;return False
        c=cost[s];side=data["side"];h=data["horizon"]
        due=entryAt+h*60000
        boundary=(proto["phase"]["selectionEnd"] if t<proto["phase"]["selectionEnd"]
                  else proto["phase"]["end"])
        if due>boundary:
            self.rejections["EXIT_AFTER_PREDECLARED_PHASE"]+=1;return False
        current=self.mark(entryAt,views,cost)
        if current is None or self.frozen:
            self.rejections["UNKNOWN_OR_EXCESSIVE_FLOATING_RISK_AT_FILL"]+=1;return False
        notional=c["minimumNotionalEur"]*units
        margin=c["minimumMarginEur"]*units
        frictionBps=c["stressBps"] if variant=="FULL_STRESS" else c["adverseBps"]
        friction=notional*frictionBps/10000
        carry=funding(c,side,entryAt,due,notional)
        if carry is None:
            self.rejections["FUNDING_NOT_CERTIFIABLE"]+=1;return False
        if current["freeMargin"]-margin-friction<=0 or current["equity"]-friction<=0:
            self.rejections["RECHECK_COMMON_CASH_MARGIN_AT_DELAYED_FILL"]+=1;return False
        self.cash-=friction
        self.open[key]=dict(symbol=s,family=data["family"],side=side,
            horizon=h,decisionAt=t,entryAt=entryAt,entryPrice=entry,
            due=due,units=units,notional=c["minimumNotionalEur"],margin=margin,
            friction=friction)
        self.allocations+=1;self.maxOpen=max(self.maxOpen,len(self.open))
        if len(self.admissionExamples)<8:
            self.admissionExamples.append(dict(id=key,signalAt=t,
                entryAt=entryAt,side=side,units=units,marginEur=margin,
                actualM5EntryClockWasAfterSignal=True,
                entryWasUnknownAtDecision=True))
        self.mark(entryAt,views,cost)
        return True
    def finish(self,end,views,cost,p):
        self.advance(end,views,cost)
        weeks=[p["phase"]["developmentEnd"]+i*WEEK for i in range(26)]
        counts=[sum(start<=x["closingAt"]<start+WEEK for x in self.closed) for start in weeks]
        selection=counts[:13];audit=counts[13:]
        return dict(cashEur=round(self.cash,8),netClosedEur=round(self.netClosed,8),
            modeledRoundTrips=len(self.closed),unresolvedPositions=len(self.open),
            sampledEquityPeakEur=round(self.high,7),
            maxSampledDrawdown=round(self.drawdown,6),
            maxOpenPositions=self.maxOpen,maximumModeledMarginEur=round(self.peakMargin,6),
            nativeCalls=self.calls,nativeAllocations=self.allocations,
            offeredNativeCandidates=self.nativeOffered,
            eligibleWeeks=26,hard21EligibleWeeksPassed=sum(x>=21 for x in counts),
            minimumRoundTripsPerEligibleWeek=min(counts),
            selectionWeeklyRoundTrips=selection,exposedAuditWeeklyRoundTrips=audit,
            selectionRoundTrips=sum(selection),exposedAuditRoundTrips=sum(audit),
            fullExitGapCount=self.delayed,unknownHoldingMarks=self.unknownMarks,
            observedEquityMarks=self.knownMarks,capitalContinuityReconciled=self.intact(),
            finalClosedEquityCertified=False,actualBrokerExecutionNetEur=None,
            phaseInitialCashEur=self.phaseCash,
            rejected=dict(sorted(self.rejections.items())),
            sampleDelayedEntries=self.admissionExamples,
            sampleCloses=self.closed[:10],freezeObserved=self.frozen)

def scenario_rows(views,s,t,duration,side,notional):
    history=[t-w*WEEK for w in STATES]
    states=[]
    for old in history:
        z=path(views,s,old,duration,side,notional)
        if z is None:return None
        states.append(z)
    return states

def request(book,t,forecasts,views,cost,p,variant):
    mark=book.mark(t,views,cost)
    if mark is None or book.frozen or not book.intact():
        return None,{}
    history=[t-w*WEEK for w in STATES]
    latest=max(history)+MAX_HORIZON_MS+MS
    if history[0]<p["phase"]["start"] or latest>=t:return None,{}
    # Most important prospective correction after IPF1: each joint state
    # evolves EVERY already-open position over its remaining holding period.
    # Cannot declare open portfolio zero simply because positions were paid
    # for at their own earlier native decision clock.
    openCurves={}
    for pid,pos in book.open.items():
        remaining=max(MS,min(MAX_HORIZON_MS,pos["due"]-t))
        records=scenario_rows(views,pos["symbol"],t,remaining,pos["side"],
                              pos["notional"]*pos["units"])
        if records is None:return None,{}
        openCurves[pid]=records
    baseline=[]
    for i,old in enumerate(history):
        net=0.;loss=0.;peak=0.
        for pid,pos in book.open.items():
            z=openCurves[pid][i]
            carry=funding(cost[pos["symbol"]],pos["side"],t,t+min(MAX_HORIZON_MS,max(MS,pos["due"]-t)),
                          pos["notional"]*pos["units"])
            if carry is None:return None,{}
            net+=z["net"]-carry
            loss+=max(0.,-z["worst"])+pos["notional"]*pos["units"]*cost[pos["symbol"]]["stressBps"]/10000
            peak+=z["best"]
        baseline.append(dict(StateId="RCP1/"+str(old),KnownAt=old+MAX_HORIZON_MS+MS,
            Estimation=True,NetEur=net,LossEur=loss,PeakEur=peak,MarginEur=mark["margin"]))
    candidates=[];complete=[];lookup={}
    frictionKey="stressBps" if variant=="FULL_STRESS" else "adverseBps"
    for f in forecasts:
        s=f["symbol"];h=f["horizon"];c=cost[s]
        if any(x["symbol"]==s for x in book.open.values()):continue
        if f["knownAt"]!=t:raise ValueError("RCP1_NONCAUSAL_FORECAST")
        boundary=(p["phase"]["selectionEnd"] if t<p["phase"]["selectionEnd"] else p["phase"]["end"])
        if t+MS+h*60000>boundary:continue
        if mark["freeMargin"]<c["minimumMarginEur"]:
            book.rejections["MIN_BROKER_MARGIN_NOT_FINANCED"]+=1;continue
        # The *family* is an independent predictive proposal. The native
        # selector decides marginal common-capital contribution jointly.
        for fam in FAMILIES:
            if variant=="WITHOUT_"+fam:continue
            pred=f["familyBps"][fam]
            side=1 if pred>0 else -1
            projectedCarry=funding(c,side,t+MS,t+MS+h*60000,c["minimumNotionalEur"])
            if projectedCarry is None:
                book.rejections["CURRENT_TERM_FINANCING_UNKNOWN"]+=1;continue
            if (abs(pred)-c[frictionKey])*c["minimumNotionalEur"]/10000-projectedCarry<=0:
                book.rejections["EXPECTED_GROSS_BELOW_ALLIN_ADVERSE_COST"]+=1;continue
            z=scenario_rows(views,s,t,MS+h*60000,side,c["minimumNotionalEur"])
            # Delayed entry for historical residuals needs the observed
            # complete next-bar clock, not this decision bar.
            if z is None:
                book.rejections["ALIGNED_HISTORY_MISSING"]+=1;continue
            y=[]
            for past in history:
                zz=path(views,s,past+MS,h*60000,side,c["minimumNotionalEur"])
                if zz is None:y=[];break
                y.append(zz)
            if len(y)!=len(history):
                book.rejections["DELAYED_ENTRY_HISTORIC_PATH_UNKNOWN"]+=1;continue
            avg=sum(k["net"] for k in y)/len(y)
            predMoney=abs(pred)*c["minimumNotionalEur"]/10000
            cases=[]
            for old,one in zip(history,y):
                residual=one["net"]-avg
                loss=max(0.,-one["worst"])+3*f["scaleBps"]*c["minimumNotionalEur"]/10000
                loss+=c["stressBps"]*c["minimumNotionalEur"]/10000
                cases.append(dict(StateId="RCP1/"+str(old),
                    KnownAt=old+MS+h*60000,Estimation=True,
                    NetPerUnitEur=predMoney+residual-c[frictionKey]*c["minimumNotionalEur"]/10000-projectedCarry,
                    FixedCostEur=0,LossPerUnitEur=loss,
                    PeakPerUnitEur=one["best"]))
            cap=min(3,int(max(0,mark["freeMargin"])//c["minimumMarginEur"]))
            if cap<1:continue
            pid="RCP1/"+variant+"/"+fam+"/"+s+"/"+str(h)+"/"+str(t)
            grid=dict(EquityEur=mark["equity"],CertifiedPeakEur=0,
                FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
                MaximumUnits=cap,MarginPerUnitEur=c["minimumMarginEur"],
                BrokerStopoutEquityToMargin=0,Reconciled=False,
                CompleteJointRiskEvidence=False,EffectiveIndependentBlocks=4,
                UncertaintyMultiplier=1)
            candidates.append(dict(Id=pid,Candidate=fam,Symbol=s,
                RedundancyKey=s+"/"+str(t),Direction=side,
                AvailableAt=t,CalibratedThrough=latest,Level=1,
                ExecutionEvidenceComplete=False,VolumeGrid=grid,Scenarios=cases))
            complete.append(pid);lookup[pid]=dict(symbol=s,family=fam,horizon=h,
                                                 side=side,pred=pred)
    account=dict(EquityEur=mark["equity"],PeakReferenceEur=max(200,book.high),
        FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
        MaximumUnits=3,MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
        EffectiveIndependentBlocks=4,UncertaintyMultiplier=1)
    req=dict(Scope="RCP1_GLOBAL_RISK_DELAYED_FILL_CONDITIONAL_NOT_CERTIFIED",
        CommonHorizonMinutes=0,Clock=t,Account=account,
        Baseline=baseline,Opportunities=candidates,
        LedgerReconciled=True,ScenarioCompleteOpportunityIds=complete)
    return req,lookup

def deny_request(t,book):
    # No unknown-risk state is silently reset to an empty certifiable book.
    return dict(Scope="RCP1_GLOBAL_RISK_DELAYED_FILL_CONDITIONAL_NOT_CERTIFIED",
        CommonHorizonMinutes=0,Clock=t,Account=dict(
            EquityEur=max(.01,book.cash),PeakReferenceEur=max(200.,book.high),
            FreeMarginEur=0,MinimumUnits=1,StepUnits=1,MaximumUnits=1,
            MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
            EffectiveIndependentBlocks=4,UncertaintyMultiplier=1),
        Baseline=[dict(StateId="RCP1/UNPROVEN/"+str(i),KnownAt=t-1,
          Estimation=True,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0) for i in range(8)],
        Opportunities=[],LedgerReconciled=False,ScenarioCompleteOpportunityIds=[])

def evaluate(views,forecasts,cost,p):
    names=["FULL"]+["WITHOUT_"+f for f in FAMILIES]+["FULL_STRESS"]
    books={s:Book(s) for s in names}
    clocks=[t for t in sorted(forecasts) if
        p["phase"]["developmentEnd"]<=t<p["phase"]["end"]]
    lastPhase=None
    for t in clocks:
        phase="selection" if t<p["phase"]["selectionEnd"] else "exposed_audit"
        queries=[];lookups=[]
        for name,book in books.items():
            book.advance(t,views,cost)
            if phase!=lastPhase:
                book.phaseCash[phase]=book.cash
            req,lookup=request(book,t,forecasts[t],views,cost,p,name)
            if req is None:
                book.rejections["FLOATING_OR_ALIGNED_RISK_EVIDENCE_NOT_COMPLETE"]+=1
                req=deny_request(t,book)
            queries.append(req);lookups.append(lookup)
        lastPhase=phase
        answers=native(queries,"--estimate-portfolio-opportunities-batch")
        if len(answers)!=len(names):raise ValueError("RCP1_NATIVE_BATCH_INVALID")
        for name,answer,lookup in zip(names,answers,lookups):
            book=books[name];book.calls+=1;book.nativeOffered+=len(lookup)
            if answer.get("Qualified",False):
                raise ValueError("RCP1_UNAUTHORIZED_TRADING_QUALIFICATION")
            for row in answer["Declined"]:
                book.rejections["NATIVE_"+str(row["Reason"])]+=1
            for row in answer["Allocations"]:
                book.fill_after_decision(t,row,lookup,views,cost,name,p)
    results={k:book.finish(p["phase"]["end"],views,cost,p) for k,book in books.items()}
    full=results["FULL"]
    results["FLAT_NEUTRAL"]=dict(cashEur=200.,netClosedEur=0.,modeledRoundTrips=0,
        unresolvedPositions=0,maxSampledDrawdown=0.,nativeCalls=0,nativeAllocations=0,
        hard21EligibleWeeksPassed=0,eligibleWeeks=26)
    for name in names:
        if not results[name]["capitalContinuityReconciled"]:
            raise ValueError("RCP1_CASH_IDENTITY_FAILED_"+name)
    for name in names[1:]:
        if full["unresolvedPositions"]==0 and results[name]["unresolvedPositions"]==0:
            results[name]["conditionalPathDependentMarginalPolicyDifferenceEur"]=round(
                full["netClosedEur"]-results[name]["netClosedEur"],8)
        else:
            results[name]["conditionalPathDependentMarginalPolicyDifferenceEur"]=None
    return results

"""IPF1 one continuous modeled EUR200 portfolio, four causal ablations.

The native C# OpportunityOrchestrator.Estimate is the ONLY selection/risk
optimizer. This module schedules modeled bar-price entry/exit accounting from
the same predictions, not broker fills. No orders, invented bid/ask or historic
swap certificate. All standalone models share the same true historic states.
"""
import math
from bisect import bisect_left
from collections import defaultdict
from .portfolio_economic_replay import native
from .integrated_predictive_funded import FAMS,DAY,HOUR,WEEK

def candidate_prediction(f,variant):
    if variant=="FULL":return f["predictedBps"]
    removed=variant.removeprefix("WITHOUT_")
    weights=f["familyWeights"]
    total=sum(weights[k] for k in FAMS if k!=removed)
    if total<=0:return 0
    return sum(f["familyPredBps"][k]*weights[k] for k in FAMS if k!=removed)/total

def swap_debit(c,side,start,end,notional):
    if end<=start:return 0.
    # The current published swap minute, not inferred actual historical debit;
    # deliberately 3x directional current debit per crossing.
    minute=c["swapMinute"]
    t=(start//DAY)*DAY+minute*60000
    if t<=start:t+=DAY
    cycles=0
    while t<=end:
        cycles+=1;t+=DAY
    if cycles==0:return 0.
    if not c["fundingKnown"]:return None
    bps=c["longDailyDebitBps"] if side>0 else c["shortDailyDebitBps"]
    return 3.*bps*notional*cycles/10000.

def evidence_history(views,s,hist,horizon):
    v=views[s]
    end=hist+horizon*60000
    a=v["price"].get(hist);z=v["price"].get(end)
    if not a or not z:return None
    # Observe all available completed hourly marks; the historical
    # path's missing hours are separately counted, never certified.
    hours=v["h"]
    hourly=[(t,hours[t][3]) for t in range(hist+HOUR,end+1,HOUR) if t in hours]
    bps=10000*math.log(z/a)
    return dict(grossBps=bps,markCount=len(hourly),
       hourly=hourly,entry=a,exit=z)

class Book:
    def __init__(self,name):
        self.name=name;self.cash=200.;self.open={}
        self.peak=200.;self.dd=0.;self.netClosed=0.;self.closed=0
        self.peakMargin=0.;self.margin=0.
        self.nativeCalls=0;self.nativeProposed=0;self.nativeAllocations=0
        self.rejected=defaultdict(int);self.knownEquityMarks=0
        self.unknownHoldingMarks=0;self.delayedExits=0
        self.admissions=[];self.closedRows=[]
        self.cashAtPhase={"start":200.};self.freezeOnDD=False
        self.maxOpen=0
    def settle(self,t,views,cost):
        for pid,p in sorted(list(self.open.items())):
            if t<p["due"]:continue
            v=views[p["symbol"]]
            ix=bisect_left(v["observed"],p["due"])
            if ix>=len(v["observed"]) or v["observed"][ix]>t:continue
            at=v["observed"][ix]
            raw=v["price"][at]
            realized=10000*math.log(raw/p["entry"])*p["side"]
            gross=p["units"]*p["notional"]*realized/10000
            charge=swap_debit(cost[p["symbol"]],p["side"],p["clock"],at,
                              p["notional"]*p["units"])
            if charge is None:
                self.rejected["UNKNOWN_OVERNIGHT_FUNDING"]+=1
                continue
            self.cash+=gross-charge
            net=gross-p["friction"]-charge
            self.netClosed+=net;self.closed+=1
            if at>p["due"]:self.delayedExits+=1
            self.closedRows.append(dict(id=pid,symbol=p["symbol"],family=p["family"],
                horizon=p["horizon"],opened=p["clock"],scheduledEnd=p["due"],
                knownCloseAt=at,units=p["units"],modeledGrossEur=round(gross,8),
                conditionalTotalFrictionEur=round(p["friction"],8),
                conditionalFinancingEur=round(charge,8),
                conditionalNetEur=round(net,8),conditionalOnly=True))
            del self.open[pid]
    def mark(self,t,views,cost):
        floating=0.;used=0.
        for p in self.open.values():
            price=views[p["symbol"]]["price"].get(t)
            if not price:
                self.unknownHoldingMarks+=1
                return None
            gross=10000*math.log(price/p["entry"])*p["side"]*p["notional"]*p["units"]/10000
            accrual=swap_debit(cost[p["symbol"]],p["side"],p["clock"],t,p["notional"]*p["units"])
            if accrual is None:
                self.unknownHoldingMarks+=1
                return None
            floating+=gross-accrual;used+=p["margin"]
        eq=self.cash+floating
        self.margin=used;self.peakMargin=max(self.peakMargin,used)
        self.peak=max(self.peak,eq)
        if self.peak>0:self.dd=max(self.dd,1-eq/self.peak)
        self.freezeOnDD=self.freezeOnDD or self.dd>=.30
        self.knownEquityMarks+=1
        return dict(equity=eq,margin=used,freeMargin=eq-used)
    def open_selected(self,t,allocation,lookups,views,cost):
        id=allocation["Id"]
        if id not in lookups:
            self.rejected["NATIVE_UNRECOGNIZED_ALLOCATION"]+=1;return False
        cand=lookups[id]
        s=cand["symbol"];h=cand["horizon"];u=int(allocation["Units"])
        if u<=0 or u>3 or abs(u-float(allocation["Units"]))>1e-9:
            self.rejected["INVALID_MINIMUM_UNITS"]+=1;return False
        if any(x["symbol"]==s for x in self.open.values()):
            self.rejected["EXISTING_SYMBOL_EXPOSURE"]+=1;return False
        point=views[s]["price"].get(t)
        if not point:
            self.rejected["ENTRY_PRICE_NOT_PRESENT"]+=1;return False
        c=cost[s];notional=c["minimumNotionalEur"]
        estimatedFriction=notional*c["adverseBps"]*u/10000
        current=self.mark(t,views,cost)
        if current is None or current["equity"]<=estimatedFriction or (
            current["equity"]-estimatedFriction <= current["margin"]+c["minimumMarginEur"]*u):
            self.rejected["COMMON_CAPITAL_OR_MARK_FAIL"]+=1;return False
        if self.freezeOnDD:
            self.rejected["SAMPLED_DRAWDOWN_REVIEW"]+=1;return False
        self.cash-=estimatedFriction
        self.open[id]=dict(clock=t,due=t+h*60000,symbol=s,side=cand["side"],
            family=cand["family"],horizon=h,units=u,entry=point,
            notional=notional,friction=estimatedFriction,
            margin=c["minimumMarginEur"]*u,forecastEur=cand["predictedBps"]*notional*u/10000)
        self.maxOpen=max(self.maxOpen,len(self.open))
        self.nativeAllocations+=1
        self.admissions.append(dict(id=id,clock=t,symbol=s,horizonMinutes=h,
            units=u,modelledMinimumNotionalEur=notional,
            conditionalExpectedGrossEur=cand["predictedBps"]*notional*u/10000,
            upfrontAdverseFrictionEur=estimatedFriction))
        return True
    def snapshot(self,end,views,cost):
        self.settle(end,views,cost)
        current=self.mark(end,views,cost)
        return dict(endCashEur=round(self.cash,7),
            modelFinalLiquidationEquityEur=round(current["equity"],7) if current else None,
            closedNetEur=round(self.netClosed,7),
            completeRoundTrips=self.closed,
            unresolvedPositions=len(self.open),
            sampledPeakEur=round(self.peak,7),sampledMaxDrawdown=round(self.dd,6),
            maxConcurrentPositions=self.maxOpen,peakModeledMarginEur=round(self.peakMargin,6),
            nativeSelectorCalls=self.nativeCalls,nativeProposals=self.nativeProposed,
            nativeAllocations=self.nativeAllocations,
            rejected=dict(sorted(self.rejected.items())),
            unknownHoldingMarks=self.unknownHoldingMarks,delayedExits=self.delayedExits,
            phaseCashMarks=self.cashAtPhase,modelNotBrokerFills=True,
            actualExecutionNetCertified=False,globallyExposed=True,
            sampleTrades=self.closedRows[:12],totalModeledClosures=len(self.closedRows))

def historical_states(views,s,h,t,side,p):
    # The eight predeclared SAME-clock historical weekly market states
    # preserve cross-asset correlation instead of fabricating independent
    # per-asset best samples. All outcomes matured before the current clock.
    ts=[t-w*WEEK for w in range(8,0,-1)]
    if ts[0]<p["calendar"]["start"]:return None
    ret=[]
    for past in ts:
        z=evidence_history(views,s,past,h)
        if z is None:return None
        ret.append(z)
    return ts,ret

def request_for(book,t,forecasts,views,cost,p,variant):
    mark=book.mark(t,views,cost)
    if mark is None:return None,{}
    history=[t-w*WEEK for w in range(8,0,-1)]
    if history[0]<p["calendar"]["start"]:return None,{}
    latest=max(history)+4320*60000
    if latest>=t:raise ValueError("IPF1_FUTURE_SCENARIO_CLOCK")
    baselineLoss=sum(max(0,-10000*math.log(views[pos["symbol"]]["price"][t]/pos["entry"])*pos["side"]
                       *pos["notional"]*pos["units"]/10000)
                     + max(0,3.*pos["notional"]*cost[pos["symbol"]]["stressBps"]*pos["units"]/10000)
                     for pos in book.open.values())
    baseline=[dict(StateId="IPF1/"+str(state),KnownAt=state+4320*60000,
                   Estimation=True,NetEur=0,LossEur=baselineLoss,
                   PeakEur=max(0,book.peak-mark["equity"]),MarginEur=mark["margin"])
              for state in history]
    opp=[];complete=[];lookup={}
    for f in forecasts:
        s=f["symbol"];h=f["horizon"]
        if any(v["symbol"]==s for v in book.open.values()):continue
        if f["clock"]+h*60000 >= (
            p["calendar"]["developmentEnd"] if f["phase"]=="development" else
            p["calendar"]["selectionEnd"] if f["phase"]=="selection" else
            p["calendar"]["end"]):continue
        c=cost[s]
        if mark["freeMargin"]<c["minimumMarginEur"]:continue
        # Funding support is a genuine monetary admission condition for
        # a multi-day forecast, not a reason to suppress predictive scoring.
        if h>=1440 and not c["fundingKnown"]:
            book.rejected["FUNDING_UNKNOWN_"+s]+=1;continue
        pred=candidate_prediction(f,variant)
        side=1 if pred>0 else -1
        pendingFee=swap_debit(c,side,t,t+h*60000,c["minimumNotionalEur"])
        if pendingFee is None:
            book.rejected["FINANCING_UNKNOWN"]+=1;continue
        forecastNet=(abs(pred)-c["adverseBps"])*c["minimumNotionalEur"]/10000-pendingFee
        if forecastNet<=0:
            book.rejected["FORECAST_BELOW_ADVERSE_COST"]+=1;continue
        hist=historical_states(views,s,h,t,side,p)
        if hist is None:
            book.rejected["HISTORICAL_JOINT_STATE_UNKNOWN"]+=1;continue
        _,trades=hist
        hs=[side*x["grossBps"] for x in trades];mu=sum(hs)/len(hs)
        unit=c["minimumNotionalEur"]
        scenarios=[]
        for past,x,g in zip(history,trades,hs):
            residual=g-mu
            estimatedGross=(abs(pred)+residual)*unit/10000
            loss=max(0,(3*f["scale"]-min(g,0))*unit/10000)+c["stressBps"]*unit/10000
            peak=max(0,max(g,0)*unit/10000)
            scenarios.append(dict(StateId="IPF1/"+str(past),
                KnownAt=past+4320*60000,Estimation=True,
                NetPerUnitEur=estimatedGross-unit*c["adverseBps"]/10000-pendingFee,
                FixedCostEur=0,LossPerUnitEur=loss,PeakPerUnitEur=peak))
        pid="IPF1/"+variant+"/"+s+"/"+str(h)+"/"+str(t)
        min_margin=c["minimumMarginEur"]
        cap=min(3,max(1,int(mark["freeMargin"]//min_margin)))
        grid=dict(EquityEur=mark["equity"],CertifiedPeakEur=0,
           FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
           MaximumUnits=cap,MarginPerUnitEur=min_margin,
           BrokerStopoutEquityToMargin=0,Reconciled=False,
           CompleteJointRiskEvidence=False,EffectiveIndependentBlocks=4,
           UncertaintyMultiplier=1)
        opp.append(dict(Id=pid,Candidate="PREQUENTIAL_FUSION_"+variant,Symbol=s,
            RedundancyKey=s+"/"+str(t),Direction=side,AvailableAt=t,
            CalibratedThrough=latest,Level=1,ExecutionEvidenceComplete=False,
            VolumeGrid=grid,Scenarios=scenarios))
        complete.append(pid)
        lookup[pid]=dict(symbol=s,horizon=h,side=side,phase=f["phase"],
                          family=variant,predictedBps=pred)
    account=dict(EquityEur=mark["equity"],PeakReferenceEur=max(200,book.peak),
        FreeMarginEur=mark["freeMargin"],MinimumUnits=1,StepUnits=1,
        MaximumUnits=3,MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
        EffectiveIndependentBlocks=4,UncertaintyMultiplier=1)
    req=dict(Scope="IPF1_MULTI_HORIZON_CONDITIONAL_RESEARCH_NOT_CERTIFIED",
        CommonHorizonMinutes=0,Clock=t,Account=account,Baseline=baseline,
        Opportunities=opp,LedgerReconciled=not book.freezeOnDD,
        ScenarioCompleteOpportunityIds=complete)
    return req,lookup

def evaluate(views,forecasts,cost,p):
    variants=("FULL",)+tuple("WITHOUT_"+s for s in FAMS)
    books={v:Book(v) for v in variants}
    # Cost/contract scenarios were observed in DEVELOPMENT; no historical
    # book decisions may use those later quotes before that calibration clock.
    # From selection onward the single EUR200 book is continuous through
    # exposed audit, without a later reset or separate per-family capital.
    clocks=sorted(t for t in forecasts if p["calendar"]["developmentEnd"]<=t<p["calendar"]["end"])
    priorPhase=None;callCount=0
    for t in clocks:
        stage=("development" if t<p["calendar"]["developmentEnd"] else
               "selection" if t<p["calendar"]["selectionEnd"] else "exposed_audit")
        if stage!=priorPhase:
            for book in books.values():
                book.cashAtPhase[stage]=round(book.cash,7)
            priorPhase=stage
        requests=[];lookups=[]
        for v,book in books.items():
            book.settle(t,views,cost)
            req,look=request_for(book,t,forecasts[t],views,cost,p,v)
            if req is None:
                book.rejected["COMMON_MARK_OR_HISTORIC_STATE_UNKNOWN"]+=1
                req=dict(Scope="IPF1_MULTI_HORIZON_CONDITIONAL_RESEARCH_NOT_CERTIFIED",
                    CommonHorizonMinutes=0,Clock=t,Account=dict(
                        EquityEur=200,PeakReferenceEur=200,FreeMarginEur=200,
                        MinimumUnits=1,StepUnits=1,MaximumUnits=1,
                        MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
                        EffectiveIndependentBlocks=4,UncertaintyMultiplier=1),
                    Baseline=[dict(StateId="IPF1/empty/"+str(i),KnownAt=t-1,
                         Estimation=True,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0) for i in range(8)],
                    Opportunities=[],LedgerReconciled=False,
                    ScenarioCompleteOpportunityIds=[])
            requests.append(req);lookups.append(look)
        chosen=native(requests,"--estimate-portfolio-opportunities-batch")
        if len(chosen)!=len(variants):raise ValueError("IPF1_NATIVE_BATCH_SHAPE")
        callCount+=1
        for v,allocation,lookup in zip(variants,chosen,lookups):
            book=books[v]
            book.nativeCalls+=1;book.nativeProposed+=len(lookup)
            if allocation.get("Qualified",True):raise ValueError("IPF1_NATIVE_QUALIFICATION_ESCALATION")
            for a in allocation["Allocations"]:
                book.open_selected(t,a,lookup,views,cost)
    return {v:book.snapshot(p["calendar"]["end"],views,cost) for v,book in books.items()}

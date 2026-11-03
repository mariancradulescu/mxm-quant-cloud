"""EPA2 extends the existing selector, valuation and funded ledger in place.
No alternative allocator/accounting engine and no emulated broker liquidations.
"""
import json,hashlib
from decimal import Decimal as D
from dataclasses import replace
from pathlib import Path
from .portfolio_economic_replay import (native,fee,net_quote,day_clock,point_quotes,valued_quote,
    funding_condition,SynchronizedFundedReplay)
from .funded_replay import Contract,Decision,IncompleteEvidence
from .portfolio_economic_source import protocol as epa1_protocol
ZERO=D(0)


def study_clock(b,day):return b['decisionClocks'][day]
def episode_funding(c,clock,horizon):
    minute=(clock//60000)%1440
    return c.get('swapPeriod')==24 and isinstance(c.get('swapTime'),int) and not minute<=c['swapTime']<=minute+horizon


class HoldingReplay(SynchronizedFundedReplay):
    def _mark(self,t):
        try:
            super()._mark(t);self.equity_known=True
        except IncompleteEvidence:
            self.incomplete_marks=True;self.equity_known=False
    def dispatch(self,point,slip,source_hash,entry_deadline=False):
        self.equity_known=not self.open
        self.quote_batch(point,slip,source_hash)
        if entry_deadline:
            for d in list(self.pending):
                if d.action=='OPEN':
                    self.pending.remove(d);self.rejected.append((d.position_id,'ENTRY_ASOF_SOURCE_MISSING_NO_LATE_FILL'))


def holding_input(engine,b,raw,stress,account_leverage=None):
    known=getattr(engine,'equity_known',not engine.open)
    if known:
        try:equity=engine.equity(raw['at'])
        except IncompleteEvidence:known=False;equity=None
    else:equity=None
    return dict(EquityEur=equity,PeakReferenceEur=engine.peak,DataComplete=known,
        Positions=[dict(Id=pid,Symbol=p.request.symbol,Units=p.request.units,EntryMarginPerUnitEur=p.request.contract.margin_eur_per_unit,
                        StressLossEur=stress.get(pid,ZERO)) for pid,p in engine.open.items()],
        SourceSymbols=b['symbols'],RawQuotes=raw['quotes'],
        AccountLeverage=account_leverage if account_leverage is not None else D(b['riskTerms']['leverageInCents'])/100,
        DocumentedReferenceStopoutRatio=D('.5'))


def monitor(engine,b,raw,stress):
    return native(holding_input(engine,b,raw,stress),'--assess-holding-risk')


def calibration(plan,day,s,candidate,valued,horizon,slip,clock=None):
    start=clock if clock is not None else day_clock(day);proposal=plan.get((candidate,s,start));keys=[]
    for minute in range(0,horizon+1,60):
        keys.append(start+minute*60000)
        if minute<horizon:keys.append(start+minute*60000+30000)
    points=[point_quotes(valued,t) for t in keys]
    if proposal is None or any(valued_quote(v,s) is None for v in points):return None
    first=points[0]['Quotes'][s];direction=proposal['Side'];spread=D(str(first['Ask']))-D(str(first['Bid']));slippage=spread*slip
    entry=D(str(first['Ask'] if direction>0 else first['Bid']))+direction*slippage;pnl=[];cash=[]
    for point in points:
        q=point['Quotes'][s];out=D(str(q['Bid'] if direction>0 else q['Ask']))-direction*slippage
        converted=net_quote(q,D(direction)*(out-entry));cash.append(converted)
        pnl.append(converted-D(str(first['FeeLinearEurPerUnit']))-D(str(q['FeeLinearEurPerUnit'])))
    return dict(StateId='EPA2/'+day,KnownAt=points[-1]['At'],Estimation=True,NetPerUnitEur=pnl[-1],
        FixedCostEur=D(str(first['FeeFloorEur']))+max(D(str(x['Quotes'][s]['FeeFloorEur'])) for x in points),
        LossPerUnitEur=max(ZERO,-min(pnl)),PeakPerUnitEur=max(ZERO,max(cash)))


def pre_margin_bounds(b,valued,p):
    bounds={}
    for day in p['replayDays']:
        clock=study_clock(b,day)
        if clock is None:continue
        key=str(clock-20000);point=valued[key];raw=b['snapshots'][key]
        for s in p['universe']:
            if s not in point['Quotes']:continue
            row=b['symbols'][s]
            req=dict(EquityEur=200,PeakReferenceEur=200,DataComplete=True,
                Positions=[dict(Id='QUERY/'+s,Symbol=s,Units=row['maxQueriedUnits'],EntryMarginPerUnitEur=D(row['currentMarginPerUnitBoundEur']),StressLossEur=0)],
                SourceSymbols=b['symbols'],RawQuotes=raw['quotes'],AccountLeverage=D(b['riskTerms']['leverageInCents'])/100,
                DocumentedReferenceStopoutRatio=D('.5'))
            result=native(req,'--assess-holding-risk')
            if result['Positions'] and result['Positions'][0]['MarginEnvelopeEur'] is not None:
                bounds[day,s]=D(str(result['Positions'][0]['MarginEnvelopeEur']))/row['maxQueriedUnits']
    return bounds


def run_case(b,plan,valued,p,horizon,active,slip,bounds,removed=None,retain=True):
    engine=HoldingReplay(max_staleness_ms=1000,financing_schedule_proven=False)
    ledger=[];risk=[];daily=[];decisions=[];stress={};suspend=False;uncertain=False;gaps=[]
    for cohort in p['cohorts']:
        samples={(c,s):[calibration(plan,d,s,c,valued,horizon,slip,study_clock(b,d)) if study_clock(b,d) is not None else None for d in cohort['calibrationDays']] for c in p['families'] for s in p['universe']}
        for day in cohort['replayDays']:
            before=engine.balance;clock=study_clock(b,day)
            if clock is None:
                daily.append(dict(cohort=cohort['id'],day=day,closedNetEur=0,reason='CALENDAR_SOURCE_MISSING_NO_SUBSTITUTE_DATE'));continue
            if engine.open or engine.pending:
                suspend=True;uncertain=True
            if suspend:
                daily.append(dict(cohort=cohort['id'],day=day,closedNetEur=0,reason='FURTHER_ADMISSIONS_SUSPENDED_UNRESOLVED_OR_RISK_LIMIT'))
                continue
            pre=valued[str(clock-20000)]
            if pre['At']>=clock:raise IncompleteEvidence('EPA2_FUTURE_PREDECISION_SOURCE')
            root=dict(EquityEur=engine.balance,PeakReferenceEur=max(engine.balance,engine.peak),FreeMarginEur=engine.balance,
                MinimumUnits=1,StepUnits=1,MaximumUnits=1,MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
                EffectiveIndependentBlocks=len(cohort['calibrationDays']),UncertaintyMultiplier=2)
            through=max((study_clock(b,d)+horizon*60000+11000 for d in cohort['calibrationDays'] if study_clock(b,d) is not None),default=clock-1)
            states=[dict(StateId='EPA2/'+d,KnownAt=(study_clock(b,d) if study_clock(b,d) is not None else day_clock(d))+horizon*60000+11000,Estimation=True,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0) for d in cohort['calibrationDays']]
            proposals=[];complete=[];contracts={};scenarios={}
            for candidate in p['families']:
                for s in p['universe']:
                    name=candidate+'/'+s
                    if name==removed:continue
                    signal=plan.get((candidate,s,clock))
                    if signal is None:
                        ledger.append(dict(day=day,candidate=candidate,symbol=s,units=0,reason='NO_FROZEN_CAUSAL_PROPOSAL'));continue
                    c=b['symbols'][s]['contract'];q=valued_quote(pre,s);minimum=int(c['minVolume'])//100;step=int(c['stepVolume'])//100
                    maximum=b['symbols'][s]['maxQueriedUnits'];margin=bounds.get((day,s),D(b['symbols'][s]['currentMarginPerUnitBoundEur']))
                    pid=name+'/'+str(clock);path=samples[candidate,s]
                    valid=q is not None and (day,s) in bounds and all(x is not None for x in path) and episode_funding(c,clock,horizon) and all(study_clock(b,d) is not None and episode_funding(c,study_clock(b,d),horizon) for d in cohort['calibrationDays']) and b['accountSwapFreeEffective'] is False
                    grid=dict(EquityEur=engine.balance,CertifiedPeakEur=0,FreeMarginEur=engine.balance,MinimumUnits=minimum,StepUnits=step,MaximumUnits=maximum,
                        MarginPerUnitEur=margin,BrokerStopoutEquityToMargin=0,Reconciled=False,CompleteJointRiskEvidence=False,
                        EffectiveIndependentBlocks=len(states),UncertaintyMultiplier=2)
                    proposals.append(dict(Id=pid,Candidate=candidate,Symbol=s,RedundancyKey=s+'/'+str(clock)+'/'+str(signal['Side']),Direction=signal['Side'],
                        AvailableAt=clock,CalibratedThrough=through,Level=1,ExecutionEvidenceComplete=False,VolumeGrid=grid,Scenarios=path if valid else []))
                    if valid:
                        complete.append(pid);scenarios[pid]=path
                        contracts[pid]=Contract(minimum,step,int(c['maxVolume'])//100,margin,fee(q,minimum),fee(q,minimum),
                            (D(str(q['Ask']))-D(str(q['Bid'])))*slip,'CONDITIONAL_QUERIED_AND_REPRICED_MARGIN_ENVELOPE')
            req=dict(Scope='EPA2_CONDITIONAL_RESEARCH_NOT_CERTIFIED',CommonHorizonMinutes=horizon,Clock=clock,Account=root,Baseline=states,
                Opportunities=proposals,LedgerReconciled=True,ScenarioCompleteOpportunityIds=complete)
            selected=native(req,'--estimate-portfolio-opportunities');byid={x['Id']:x for x in proposals}
            decisions.append(dict(day=day,result=selected,requestSha256=hashlib.sha256(json.dumps(req,sort_keys=True,default=str).encode()).hexdigest()))
            for a in selected['Allocations']:
                o=byid[a['Id']];units=int(a['Units']);q=pre['Quotes'][o['Symbol']]
                con=replace(contracts[o['Id']],entry_commission_eur=fee(q,units),exit_commission_eur=fee(q,units))
                stress[o['Id']]=max(D(units)*x['LossPerUnitEur']+x['FixedCostEur'] for x in scenarios[o['Id']])
                engine.decide(Decision(clock,clock,through,o['Id'],o['Symbol'],'OPEN',1000,o['Direction'],units,con))
                ledger.append(dict(day=day,id=o['Id'],candidate=o['Candidate'],symbol=o['Symbol'],side=o['Direction'],units=units,reason=a['Reason'],
                    reservedMarginEur=D(units)*con.margin_eur_per_unit,marginalUtilityLower=a['MarginalUtilityLower']))
            for a in selected['Declined']:
                o=byid[a['Id']];ledger.append(dict(day=day,id=o['Id'],candidate=o['Candidate'],symbol=o['Symbol'],side=o['Direction'],units=0,reason=a['Reason']))
            for minute in range(0,horizon+1,p['replayMarkStepMinutes']):
                nominal=clock+minute*60000
                if minute==horizon:
                    for pid,pos in list(engine.open.items()):
                        if not any(x.position_id==pid and x.action=='CLOSE' for x in engine.pending):
                            engine.decide(Decision(nominal,nominal,through,pid,pos.request.symbol,'CLOSE',1000))
                for offset in (0,30000):
                    # No extra price collection. Response snapshots come from
                    # the same complete tick window and can fill a later exit.
                    key=str(nominal+offset);point=valued[key];raw=b['snapshots'][key]
                    engine.dispatch(point,slip,hashlib.sha256((b['protocolSha256']+key).encode()).hexdigest(),entry_deadline=(minute==0 and offset==0))
                    if engine.open:
                        state=monitor(engine,b,raw,stress)
                        risk.append(dict(day=day,nominal=nominal+offset,observedAt=raw['at'],**state))
                        if state['OutcomeUncertain']:uncertain=True
                        if not getattr(engine,'equity_known',False):gaps.append(dict(day=day,nominal=nominal+offset,reason='OPEN_PORTFOLIO_SOURCE_UNKNOWN'))
                        if state['DocumentedReferenceCrossed']:
                            suspend=True;uncertain=True
                        if active:
                            for pid in state['ExitIds']:
                                if pid in engine.open and not any(x.position_id==pid and x.action=='CLOSE' for x in engine.pending):
                                    pos=engine.open[pid];engine.decide(Decision(raw['at'],raw['at'],through,pid,pos.request.symbol,'CLOSE',1000))
                    if engine.max_sampled_drawdown>=D('.30'):suspend=True
            unresolved=bool(engine.open or engine.pending)
            if unresolved:uncertain=True;suspend=True
            daily.append(dict(cohort=cohort['id'],day=day,closedNetEur=engine.balance-before,openPositions=len(engine.open),pending=len(engine.pending),
                reason='UNRESOLVED_EXPOSURE' if unresolved else 'MODEL_FLAT_CASH_RECONCILED'))
    report=engine.report();ratios=[D(str(x['EquityToMargin'])) for x in risk if x['EquityToMargin'] is not None]
    result=dict(horizonMinutes=horizon,holdingPolicy='ACTIVE_CAPACITY_PROTECTION' if active else 'FIXED_EXIT_REFERENCE',slippageMultiple=slip,
        removedCandidate=removed,ledgerReport=report,dailyLedger=daily,completeFlatLedger=not engine.open and not engine.pending,
        executionOutcomeUncertain=uncertain,accountStopoutThresholdVerified=False,documentedReferenceRatio='0.5',
        referenceThresholdCrossings=sum(x['DocumentedReferenceCrossed'] is True for x in risk),
        minimumSampledEquityToMargin=min(ratios) if ratios else None,
        protectiveExitDecisions=sum(len(x['ExitIds']) for x in risk) if active else 0,
        cohortClosedNetEur={c['id']:sum((D(str(x['closedNetEur'])) for x in daily if x['cohort']==c['id']),ZERO) for c in p['cohorts']},
        sourceGaps=gaps,globalDrawdownCertified=False,economicQualification=False,
        actualBrokerLiquidationsSimulated=False,verifiedProductPathEnabled=False)
    result['unresolvedPositions']=[dict(id=pid,symbol=pos.request.symbol,side=pos.request.side,units=pos.request.units,
        enteredAt=pos.entry_at,paidEntryCommissionEur=pos.request.contract.entry_commission_eur,
        reservedEntryMarginEur=pos.margin,exitOutcome='UNRESOLVED_NOT_ZERO_PNL') for pid,pos in engine.open.items()]
    result['pendingModelActions']=[dict(id=d.position_id,action=d.action,requestedAt=d.t) for d in engine.pending]
    open_fees=sum((pos.request.contract.entry_commission_eur for pos in engine.open.values()),ZERO)
    if abs(D(200)+report['closed_net_eur']-open_fees-engine.balance)>D('1e-20'):
        raise IncompleteEvidence('EPA2_PARTIAL_CASH_ACCOUNTING_MISMATCH')
    if retain:result.update(opportunityLedger=ledger,completedTrades=engine.trades,holdingRiskLedger=risk,nativeDecisionReceipts=decisions)
    return result


def audit_epa1(old,b):
    from .portfolio_economic_source import audit,risk_terms,m,base64
    audit(old) # Original immutable EPA1 protocol, not EPA2 rules.
    oldvalued=native({k:v for k,v in old.items() if k not in ['raw','eventIndices','auditReceipt']},'--value-portfolio-source')['Snapshots']
    original=json.loads(Path('docs/EPA1_AUTHENTIC_PORTFOLIO_RESULT.json').read_text());results=[]
    p=epa1_protocol()
    trader=m.ProtoOATraderRes();trader.ParseFromString(base64.b64decode(old['raw'][0]['protobuf']))
    for case in original['portfolioScenarios']:
        e=HoldingReplay(max_staleness_ms=1000,financing_schedule_proven=False);risks=[];missing=[];slip=D(case['slippageMultipleOfEntrySpreadEachSide'])
        for day in p['replayDays']:
            clock=day_clock(day);pre=oldvalued.get(str(clock-20000))
            fixed=[t for t in case['completedTrades'] if t['id'].endswith('/'+str(clock))]
            for t in fixed:
                row=old['symbols'][t['symbol']];c=row['contract'];q=pre['Quotes'][t['symbol']];u=t['units']
                con=Contract(int(c['minVolume'])//100,int(c['stepVolume'])//100,int(c['maxVolume'])//100,D(row['currentMarginPerUnitBoundEur']),fee(q,u),fee(q,u),
                    (D(str(q['Ask']))-D(str(q['Bid'])))*slip,'ORIGINAL_EPA1_CURRENT_MARGIN_BOUND')
                e.decide(Decision(clock,clock,clock-1,t['id'],t['symbol'],'OPEN',1000,t['side'],u,con))
            for minute in range(0,241,30):
                tm=clock+minute*60000;point=oldvalued.get(str(tm))
                if minute==240:
                    for pid,pos in list(e.open.items()):e.decide(Decision(tm,tm,clock-1,pid,pos.request.symbol,'CLOSE',1000))
                if point is None:
                    if e.open:e.incomplete_marks=True;missing.append(dict(day=day,minute=minute,positionOutcomeBetweenMarks='UNKNOWN'))
                    continue
                e.dispatch(point,slip,'EPA1_FIXED_BOOK_AUDIT',entry_deadline=(minute==0))
                if e.open:
                    observed=monitor(e,b,old['snapshots'][str(tm)],{});eq=e.equity(point['At']);static=sum((pos.margin for pos in e.open.values()),ZERO)
                    risks.append(dict(day=day,nominal=tm,sampledLiquidationEquityEur=eq,originalStaticMarginEur=static,originalStaticEquityToMargin=eq/static if static>0 else None,**observed))
        rep=e.report();delta=rep['closed_net_eur']-D(case['ledgerReport']['closed_net_eur'])
        if abs(delta)>D('1e-20'):raise IncompleteEvidence('ORIGINAL_EPA1_FIXED_BOOK_CASH_MISMATCH')
        ratios=[x['EquityToMargin'] for x in risks if x['EquityToMargin'] is not None]
        # Entry-only original margins separately expose the exact static
        # assumption. Current-rule revaluation remains a scenario sensitivity.
        results.append(dict(uncertaintyMultiplier=case['uncertaintyMultiplier'],slippageMultiple=slip,originalClosedNetUnchanged=True,
            originalClosedNetEur=rep['closed_net_eur'],minimumOriginalStaticEquityToMargin=min((x['originalStaticEquityToMargin'] for x in risks if x['originalStaticEquityToMargin'] is not None),default=None),minimumOriginalSampledEquityEur=min((x['sampledLiquidationEquityEur'] for x in risks),default=None),minimumSampledEquityToMarginEnvelope=min(ratios) if ratios else None,
            referenceThresholdCrossings=sum(x['DocumentedReferenceCrossed'] is True for x in risks),missingHoldingMarks=missing,
            diagnosticProtectiveSignals=sum(bool(x['ExitIds']) for x in risks),
            currentRuleMarginRiskLedger=risks,originalAllocationsReselected=False,originalResultOverwritten=False))
    return dict(cases=results,originalAccountRiskTermsObserved=risk_terms(trader.trader),method='FIXED_ORIGINAL_TRADES_AND_CASH_IDENTITY_ONLY_NO_MODEL_SELECTION_OR_RESCORING',
        currentLeverageRepricingIsConditional=True,actualHistoricalMarginUnknown=True,accountStopoutThresholdVerified=False)


def evaluate(b,original,old,p):
    valuation=native({k:v for k,v in b.items() if k not in ['raw','eventIndices','auditReceipt']},'--value-portfolio-source')
    valued=valuation['Snapshots'];base={k:v for k,v in original.items() if k not in ['raw','traderRaw','csharpReceipt']}
    plan={(x['Candidate'],x['Symbol'],x['Clock']):x for x in native(base,'--economic-portfolio-plan')}
    context=native(dict(source=base,clocks=[study_clock(b,d) for d in p['replayDays'] if study_clock(b,d) is not None]),'--holding-market-context')
    previous=audit_epa1(old,b);print('EPA2_EPA1_FIXED_BOOK_AUDIT_COMPLETE',flush=True)
    bounds=pre_margin_bounds(b,valued,p);results=[]
    for h in p['commonHorizonMinutes']:
        for active in [False,True]:
            for slip in map(D,p['slippageMultiplesOfObservedEntrySpreadEachSide']):
                r=run_case(b,plan,valued,p,h,active,slip,bounds);results.append(r)
                print('EPA2_CASE '+json.dumps(dict(h=h,active=active,slip=str(slip),net=str(r['ledgerReport']['closed_net_eur']),trades=r['ledgerReport']['complete_round_trips'],uncertain=r['executionOutcomeUncertain']),sort_keys=True),flush=True)
    primary=next(r for r in results if r['horizonMinutes']==240 and r['holdingPolicy']=='ACTIVE_CAPACITY_PROTECTION' and r['slippageMultiple']==1)
    ablations=[]
    for family in p['families']:
        for symbol in p['universe']:
            name=family+'/'+symbol;r=run_case(b,plan,valued,p,240,True,D(1),bounds,name,False)
            ablations.append(dict(removedCandidate=name,closedNetEur=r['ledgerReport']['closed_net_eur'],completeFlatLedger=r['completeFlatLedger'],
                differenceFromFullEur=primary['ledgerReport']['closed_net_eur']-r['ledgerReport']['closed_net_eur'],outcomeUncertain=r['executionOutcomeUncertain'],
                cohortClosedNetEur=r['cohortClosedNetEur'],meaning='DESCRIPTIVE_EXPOSED_DEVELOPMENT_INTERACTION_NOT_CONFIRMED_MARGINAL_ALPHA'))
    return dict(schema='mxm-epa2-holding-executability-economics-v1',protocol=p,epa1ExecutionAudit=previous,portfolioCases=results,leaveOneOut=ablations,
        accountRiskTermsObserved=b['riskTerms'],decisionClocks=b['decisionClocks'],causalMarketContext=context,currentMarginGrid={s:dict(minMarginEur=x['currentMinMarginEur'],perUnitGridBoundEur=x['currentMarginPerUnitBoundEur'],maxQueriedUnits=x['maxQueriedUnits'],tiers=x['dynamicLeverage']) for s,x in b['symbols'].items()},
        brokerAccountStopoutThreshold=None,documentedReferenceRatio='0.5',actualFills=False,liquidityDepthObserved=False,
        historicalMarginAndTariffsVerified=False,independentConfirmation=False,globalDrawdownCertified=False,hard21Proven=False,economicQualification=False,
        ordersSubmitted=0,cloudActivated=False,originalEpa1ResultsFrozen=True,
        conditionalContinuation='Model exits and resumption are conditional quote fills, not proof of broker order/stopout outcomes; uncertainty flags are retained',
        marginInterpretation='Conservative maximum of queried entry bound and full-notional current minimum-touched-tier leverage repricing; not historical actual used margin')

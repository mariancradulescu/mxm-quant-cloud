"""SQP1 prospective economics; reuses native allocation/risk and the funded ledger."""
import hashlib,json
from decimal import Decimal as D
from dataclasses import replace
from .causal_observation import first_observation
from .portfolio_economic_source import partial_snapshot
from .portfolio_economic_replay import native,fee,net_quote
from .portfolio_holding_replay import HoldingReplay,monitor
from .funded_replay import Contract,Decision,IncompleteEvidence
from .decode import need
from .sequence_portfolio_source import window_events,clock

ZERO=D(0)


def groups(p):
    return [(f+"/"+tf,s) for f in p["families"] for tf in p["timeframes"] for s in p["universe"]]


def route(b,symbols):
    r=set(symbols)|{'EURUSD'}
    for s in list(r):
        q=b['symbols'][s]['quoteAsset']
        if q=='JPY':r.add('USDJPY')
        elif q=='CAD':r.add('USDCAD')
    return sorted(r)


class Book:
    def __init__(self,b,p):self.b=b;self.p=p;self.events={};self.cache={};self.margins={};self.parity=0
    def raw_events(self,nominal):
        if nominal not in self.events:self.events[nominal]=window_events(self.b,nominal,self.p)
        return self.events[nominal]
    def get(self,nominal,symbols,decision=None,all_available=False):
        requested=tuple(route(self.b,symbols));start=nominal if decision is None else decision
        key=nominal,requested,start,all_available
        if key in self.cache:return self.cache[key]
        events,complete=self.raw_events(nominal)
        search=min(self.p['searchMs'],nominal+self.p['requestToOffsetMs']-start-self.p['latencyMs'])
        if search<0:self.cache[key]=None;return None
        w=dict(Nominal=start,LatencyMs=self.p['latencyMs'],SearchMs=search,MaximumAgeMs=self.p['maximumSideAgeMs'],
               Route=list(requested),Events=[x for x in events if x['Symbol'] in requested],Complete=all(complete[s] for s in requested))
        answer=native([w],'--causal-observation-windows')[0]
        need(answer==first_observation(w),'SQP1_NATIVE_CLOCK_PARITY');self.parity+=1
        if answer['At'] is None:self.cache[key]=None;return None
        at=answer['At']
        if all_available:
            sides={s:[[ [x['At'],x['Price']] for x in events if x['Symbol']==s and x['Side']==k]
                       if complete[s] else None for k in (0,1)] for s in self.p['universe']}
            raw=partial_snapshot(sides,at,self.p['universe'],self.p['maximumSideAgeMs'])
        else:raw=dict(at=at,quotes={q['Symbol']:dict(bid=q['Bid'],ask=q['Ask'],bidAt=q['BidAt'],askAt=q['AskAt']) for q in answer['Quotes']})
        source=dict(schema=self.b['schema'],readOnly=True,depositCurrency='EUR',symbols=self.b['symbols'],snapshots={str(start):raw})
        valued=native(source,'--value-portfolio-source')['Snapshots'][str(start)]
        self.cache[key]=(valued,raw);return self.cache[key]
    def anchor(self,day):return self.get(clock(self.p,day),['EURUSD'],all_available=True)
    def entry(self,day,s):
        a=self.anchor(day)
        return self.get(clock(self.p,day),[s],a[0]['At']) if a and s in a[0]['Quotes'] else None
    def margin(self,s,units,point):
        valued,raw=point;key=s,units,raw['at']
        if key not in self.margins:
            row=self.b['symbols'][s]
            req=dict(EquityEur=200,PeakReferenceEur=200,DataComplete=True,
                Positions=[dict(Id=s,Symbol=s,Units=units,EntryMarginPerUnitEur=D(row['currentMarginPerUnitBoundEur']),StressLossEur=0)],
                SourceSymbols=self.b['symbols'],RawQuotes=raw['quotes'],AccountLeverage=D(self.b['riskTerms']['leverageInCents'])/100,
                TierLeverageDivisor=100,DocumentedReferenceStopoutRatio=D('.5'))
            result=native(req,'--assess-holding-risk');self.margins[key]=result['UsedMarginEnvelopeEur']
        return self.margins[key]
    def path(self,day,s):
        first=self.entry(day,s)
        if first is None:return None
        at=clock(self.p,day);points=[first]
        for minute in range(0,61,15):
            for offset in ((30000,) if minute==0 else (0,) if minute==60 else (0,30000)):
                point=self.get(at+minute*60000,[s],at+minute*60000+offset)
                if point is None or s not in point[0]['Quotes']:return None
                if point[0]['At']>points[-1][0]['At']:points.append(point)
        return points


def funding(b,p,day,s):
    c=b['symbols'][s]['contract'];start=clock(p,day);end=start+60*60000+58000
    day0=start//86400000*86400000
    return b['accountSwapFreeEffective'] is False and c.get('swapPeriod')==24 and isinstance(c.get('swapTime'),int) and not any(
        start<=day0+i*86400000+c['swapTime']*60000<=end for i in (0,1))


def preflight(b,p,count=None):
    book=Book(b,p);days=b['completedDays'][:count or p['pilotDays']]
    forecasts=native([x for x in b['featureBlocks'] if x['Day'] in days],'--sequence-portfolio-forecasts')
    rows=[]
    for day in days:
        ready=sum(x['Day']==day for x in forecasts);complete=[];financed=[]
        for s in p['universe']:
            path=book.path(day,s)
            if path is None or not funding(b,p,day,s):continue
            complete.append(s);minimum=b['symbols'][s]['contract']['minVolume']//100
            q=path[0][0]['Quotes'][s];margin=book.margin(s,minimum,path[0]);spread=D(q['Ask'])-D(q['Bid'])
            friction=2*fee(q,minimum)+3*spread*minimum*D(q['EurDebitPerQuote'])
            if margin is not None and margin+friction<200:financed.append(s)
        rows.append(dict(day=day,readyForecasts=ready,completeRoutePaths=complete,minimumVolumeCapacityAssets=financed))
    return dict(passed=len(rows)==p['pilotDays'] and all(r['readyForecasts']>=16 and len(r['completeRoutePaths'])>=4 and len(r['minimumVolumeCapacityAssets'])>=3 for r in rows),
                days=rows,netScoresComputed=False,independentConfirmation=False,plannedCalibrationBlocks=8,plannedReplayBlocks=8)


def sample(book,p,forecast,slip):
    day=forecast['Day'];s=forecast['Symbol'];points=book.path(day,s)
    if points is None or not funding(book.b,p,day,s):return None
    side=forecast['Side'];quotes=[x[0]['Quotes'][s] for x in points];first=quotes[0]
    slippage=(D(first['Ask'])-D(first['Bid']))*slip
    entry=D(first['Ask'] if side>0 else first['Bid'])+side*slippage
    cash=[];net=[]
    for q in quotes:
        out=D(q['Bid'] if side>0 else q['Ask'])-side*slippage
        value=net_quote(q,D(side)*(out-entry));cash.append(value)
        net.append(value-D(first['FeeLinearEurPerUnit'])-D(q['FeeLinearEurPerUnit']) if side else ZERO)
    return dict(StateId='SQP1/'+day,KnownAt=points[-1][0]['At'],Estimation=True,
        NetPerUnitEur=net[-1],FixedCostEur=(D(first['FeeFloorEur'])+max(D(q['FeeFloorEur']) for q in quotes)) if side else ZERO,
        LossPerUnitEur=max(ZERO,-min(net)),PeakPerUnitEur=max(ZERO,max(cash)))


def standalone(book,p,forecasts,slip):
    rows=[]
    bykey={(x['Day'],x['Candidate'],x['Symbol']):x for x in forecasts}
    scheduled=[(d,c,s) for d in p['replayDays'] for c,s in groups(p)]
    for day,candidate,symbol in scheduled:
        f=bykey.get((day,candidate,symbol))
        if f is None:
            rows.append(dict(day=day,symbol=symbol,candidate=candidate,side=None,conditionalMinimumVolumeNetEur=None,reason='MATURE_FEATURE_SOURCE_ABSENT',fundedPortfolioTrade=False));continue
        day=f['Day'];s=f['Symbol'];path=book.path(day,s)
        row=dict(day=day,symbol=s,candidate=f['Candidate'],side=f['Side'],probabilityUp=f['ProbabilityUp'],
                 conditionalMinimumVolumeNetEur=None,fundedPortfolioTrade=False)
        if path and funding(book.b,p,day,s):
            first=path[0][0]['Quotes'][s];last=path[-1][0]['Quotes'][s];units=book.b['symbols'][s]['contract']['minVolume']//100;side=f['Side']
            spread=D(first['Ask'])-D(first['Bid']);slippage=spread*slip
            entry=D(first['Ask'] if side>0 else first['Bid'])+side*slippage;out=D(last['Bid'] if side>0 else last['Ask'])-side*slippage
            net=net_quote(last,D(side*units)*(out-entry))-fee(first,units)-fee(last,units) if side else ZERO
            target=int(D(last['Ask'])+D(last['Bid'])>D(first['Ask'])+D(first['Bid']))
            margin=book.margin(s,units,path[0]);cost=2*fee(first,units)+(1+2*slip)*spread*units*D(first['EurDebitPerQuote'])
            row.update(conditionalMinimumVolumeNetEur=net,midpointDirectionBrier=(D(str(f['ProbabilityUp']))-target)**2,
                minimumVolumeCapacityScenario=margin is not None and margin+cost<200,
                outcomeKnownAt=path[-1][0]['At'],sampledPathComplete=True)
        rows.append(row)
    return rows


def run_case(b,p,book,plan,calibrations,z,slip,removed=None,retain=True):
    engine=HoldingReplay(max_staleness_ms=1000,financing_schedule_proven=False)
    # Neutral metadata for future reuse; frozen SQP1 original labels are retained.
    engine.modeled_exit_reason='SQP1_MODEL_CLOSE_REQUEST_AT_OBSERVED_QUOTE'
    ledger=[];risk=[];daily=[];decisions=[];stress={};gaps=[];suspend=False;uncertain=False;maximum_positions=0
    through=max(clock(p,d)+60*60000+58000 for d in p['calibrationDays'])
    for day in p['replayDays']:
        nominal=clock(p,day);before=engine.balance;anchor=book.anchor(day)
        unresolved_before=bool(engine.open or engine.pending)
        if not suspend and not unresolved_before and anchor is not None:
            pre,rawpre=anchor;decision=pre['At'];states=[dict(StateId='SQP1/'+d,KnownAt=clock(p,d)+60*60000+58000,
                Estimation=True,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0) for d in p['calibrationDays']]
            account=dict(EquityEur=engine.balance,PeakReferenceEur=max(engine.peak,engine.balance),FreeMarginEur=engine.balance,
                MinimumUnits=1,StepUnits=1,MaximumUnits=1,MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
                EffectiveIndependentBlocks=8,UncertaintyMultiplier=z)
            opportunities=[];valid=[];contracts={};scenarios={}
            for candidate,s in groups(p):
                name=candidate+'/'+s
                if name==removed:continue
                f=plan.get((day,candidate,s));q=pre['Quotes'].get(s);c=b['symbols'][s]['contract'];minimum=c['minVolume']//100;step=c['stepVolume']//100
                samples=calibrations[candidate,s];gridmax=b['symbols'][s]['maxQueriedUnits']
                margin=book.margin(s,gridmax,anchor) if q is not None else None
                perunit=D(margin)/gridmax if margin is not None else D(b['symbols'][s]['currentMarginPerUnitBoundEur'])
                complete=f is not None and f['Side']!=0 and q is not None and margin is not None and all(x is not None for x in samples) and funding(b,p,day,s)
                if f is None or f['Side']==0:
                    ledger.append(dict(day=day,candidate=candidate,symbol=s,units=0,reason='NO_MATURE_NONNEUTRAL_FORECAST'));continue
                pid=name+'/'+day
                grid=dict(EquityEur=engine.balance,CertifiedPeakEur=0,FreeMarginEur=engine.balance,
                    MinimumUnits=minimum,StepUnits=step,MaximumUnits=gridmax,MarginPerUnitEur=perunit,
                    BrokerStopoutEquityToMargin=0,Reconciled=False,CompleteJointRiskEvidence=False,EffectiveIndependentBlocks=8,UncertaintyMultiplier=z)
                opportunities.append(dict(Id=pid,Candidate=candidate,Symbol=s,RedundancyKey=s+'/'+str(f['Side']),Direction=f['Side'],
                    AvailableAt=f['AvailableAt'],CalibratedThrough=through,Level=1,ExecutionEvidenceComplete=False,VolumeGrid=grid,Scenarios=samples if complete else []))
                if complete:
                    valid.append(pid);scenarios[pid]=samples
                    contracts[pid]=Contract(minimum,step,c['maxVolume']//100,perunit,fee(q,minimum),fee(q,minimum),
                        (D(q['Ask'])-D(q['Bid']))*slip,'SQP1_CURRENT_TARIFF_MARGIN_CONDITIONAL')
            request=dict(Scope='SQP1_CONDITIONAL_RESEARCH_NOT_CERTIFIED',CommonHorizonMinutes=60,Clock=decision,Account=account,
                Baseline=states,Opportunities=opportunities,LedgerReconciled=True,ScenarioCompleteOpportunityIds=valid)
            selection=native(request,'--estimate-portfolio-opportunities');byid={o['Id']:o for o in opportunities}
            decisions.append(dict(day=day,clock=decision,result=selection,requestSha256=hashlib.sha256(json.dumps(request,sort_keys=True,default=str).encode()).hexdigest()))
            for a in selection['Declined']:
                o=byid[a['Id']];ledger.append(dict(day=day,id=o['Id'],candidate=o['Candidate'],symbol=o['Symbol'],units=0,reason=a['Reason']))
            for a in selection['Allocations']:
                o=byid[a['Id']];units=int(a['Units']);q=pre['Quotes'][o['Symbol']]
                con=replace(contracts[o['Id']],entry_commission_eur=fee(q,units),exit_commission_eur=fee(q,units))
                engine.decide(Decision(decision,nominal,through,o['Id'],o['Symbol'],'OPEN',1000,o['Direction'],units,con))
                stress[o['Id']]=max(D(units)*x['LossPerUnitEur']+x['FixedCostEur'] for x in scenarios[o['Id']])
                ledger.append(dict(day=day,id=o['Id'],candidate=o['Candidate'],symbol=o['Symbol'],side=o['Direction'],units=units,reason=a['Reason'],marginalUtilityLower=a['MarginalUtilityLower']))
            if engine.pending:
                point=book.get(nominal,[d.symbol for d in engine.pending],decision)
                if point is None:
                    uncertain=True;gaps.append(dict(day=day,reason='SELECTED_ENTRY_WINDOW_UNKNOWN_NOT_ACTUAL_ZERO_PNL'))
                    engine.rejected.extend((d.position_id,'SQP1_ENTRY_WINDOW_UNOBSERVED') for d in engine.pending);engine.pending=[]
                else:
                    changed=[]
                    for d in engine.pending:
                        bound=book.margin(d.symbol,d.units,point)
                        if bound is None:
                            uncertain=True;engine.rejected.append((d.position_id,'SQP1_ENTRY_MARGIN_UNKNOWN'))
                        else:changed.append(replace(d,contract=replace(d.contract,margin_eur_per_unit=D(bound)/d.units)))
                    engine.pending=changed;engine.dispatch(point[0],slip,b['protocolSha256'])
                    maximum_positions=max(maximum_positions,len(engine.open))
                    if engine.open:
                        state=monitor(engine,b,point[1],stress);risk.append(dict(day=day,at=point[0]['At'],**state))
                        uncertain |= state['OutcomeUncertain']
                        if state['DocumentedReferenceCrossed']:suspend=True
                        for pid in state['ExitIds']:
                            pos=engine.open[pid];engine.decide(Decision(point[0]['At'],point[0]['At'],through,pid,pos.request.symbol,'CLOSE',1000))
        elif anchor is None:gaps.append(dict(day=day,reason='NO_CAUSAL_DECISION_ANCHOR'))
        for minute in range(0,61,15):
            t=nominal+minute*60000
            if minute==60:
                for pid,pos in list(engine.open.items()):
                    if not any(d.position_id==pid and d.action=='CLOSE' for d in engine.pending):
                        engine.decide(Decision(t,t,through,pid,pos.request.symbol,'CLOSE',1000))
            for offset in ((30000,) if minute==0 and not unresolved_before else (0,30000)):
                if not engine.open and not engine.pending:continue
                names={pos.request.symbol for pos in engine.open.values()}|{d.symbol for d in engine.pending}
                trigger=max(t+offset,engine.clock)
                point=book.get(t,names,trigger)
                if point is None:
                    engine.incomplete_marks=True;uncertain=True;gaps.append(dict(day=day,nominal=t+offset,reason='OPEN_EXPOSURE_OBSERVATION_UNKNOWN'))
                    failure_at=max(engine.clock,t+offset+21000)
                    for pid,pos in list(engine.open.items()):
                        if not any(d.position_id==pid and d.action=='CLOSE' for d in engine.pending):
                            engine.decide(Decision(failure_at,failure_at,through,pid,pos.request.symbol,'CLOSE',1000))
                    continue
                valued,raw=point
                def observe():
                    nonlocal suspend,uncertain
                    state=monitor(engine,b,raw,stress);risk.append(dict(day=day,at=valued['At'],**state))
                    uncertain |= state['OutcomeUncertain']
                    if state['DocumentedReferenceCrossed']:suspend=True
                    for pid in state['ExitIds']:
                        if pid in engine.open and not any(d.position_id==pid and d.action=='CLOSE' for d in engine.pending):
                            pos=engine.open[pid];engine.decide(Decision(valued['At'],valued['At'],through,pid,pos.request.symbol,'CLOSE',1000))
                engine.risk_observer=observe;engine.dispatch(valued,slip,b['protocolSha256'])
                maximum_positions=max(maximum_positions,len(engine.open))
                if engine.max_sampled_drawdown>=D('.30'):suspend=True
        daily.append(dict(day=day,closedNetCashChangeEur=engine.balance-before,openPositions=len(engine.open),pending=len(engine.pending),
            status='FLAT_RECONCILED' if not engine.open and not engine.pending else 'UNRESOLVED_NOT_ZERO_OUTCOME'))
    report=engine.report();open_fees=sum((pos.request.contract.entry_commission_eur for pos in engine.open.values()),ZERO)
    need(abs(D(200)+report['closed_net_eur']-open_fees-engine.balance)<D('1e-20'),'SQP1_CASH_RECONCILIATION')
    result=dict(uncertaintyMultiplier=z,slippageMultiple=slip,removedCandidate=removed,ledgerReport=report,
        dailyLedger=daily,completeFlatLedger=not engine.open and not engine.pending,maximumSimultaneousPositions=maximum_positions,
        executionOutcomeUncertain=uncertain,sourceGaps=gaps,globalDrawdownCertified=False,accountStopoutThresholdVerified=False,
        independentConfirmation=False,economicQualification=False)
    if retain:result.update(opportunityLedger=ledger,completedTrades=engine.trades,nativeDecisions=decisions,holdingRiskLedger=risk,
        rejectedModelActions=engine.rejected,unresolvedPositions=[dict(id=k,symbol=v.request.symbol,units=v.request.units,entryAt=v.entry_at) for k,v in engine.open.items()])
    return result


def evaluate(b,p):
    if not b['pilotPassed']:
        return dict(schema='mxm-sqp1-authentic-economic-result-v1',protocol=p,verdict='PILOT_INFORMATIONAL_OR_CAPITAL_SUPPORT_FAILED_NO_EXPANSION',
            pilot=b['pilotSupport'],economicQualification=False,ordersSubmitted=0,cloudActivated=False)
    book=Book(b,p);forecasts=native(b['featureBlocks'],'--sequence-portfolio-forecasts')
    plan={(x['Day'],x['Candidate'],x['Symbol']):x for x in forecasts};candidate_groups=groups(p)
    cases=[];ablations=[];standalones={}
    for slip in map(D,p['slippageMultiples']):
        standalones[str(slip)]=standalone(book,p,forecasts,slip)
        calibrations={(c,s):[sample(book,p,plan[day,c,s],slip) if (day,c,s) in plan else None for day in p['calibrationDays']] for c,s in candidate_groups}
        for z in map(D,p['uncertaintyMultipliers']):
            result=run_case(b,p,book,plan,calibrations,z,slip);cases.append(result)
            print('SQP1_PORTFOLIO_CASE '+json.dumps(dict(z=str(z),slip=str(slip),roundTrips=result['ledgerReport']['complete_round_trips'],net=str(result['ledgerReport']['closed_net_eur']),flat=result['completeFlatLedger']),sort_keys=True),flush=True)
            if z==2 and slip==1:
                for candidate,s in candidate_groups:
                    removed=candidate+'/'+s;other=run_case(b,p,book,plan,calibrations,z,slip,removed,False)
                    ablations.append(dict(removedCandidate=removed,fullConditionalNetEur=result['ledgerReport']['closed_net_eur'],
                        withoutConditionalNetEur=other['ledgerReport']['closed_net_eur'],incrementalConditionalNetEur=(result['ledgerReport']['closed_net_eur']-other['ledgerReport']['closed_net_eur']) if result['completeFlatLedger'] and other['completeFlatLedger'] else None,
                        fullOutcomeUncertain=result['executionOutcomeUncertain'],withoutOutcomeUncertain=other['executionOutcomeUncertain'],
                        fullFlat=result['completeFlatLedger'],withoutFlat=other['completeFlatLedger'],withoutRoundTrips=other['ledgerReport']['complete_round_trips'],
                        independentMarginalEdge=False))
    group_summaries={}
    for sl,rows in standalones.items():
        summaries=[]
        for candidate,symbol in candidate_groups:
            scheduled=[r for r in rows if r['candidate']==candidate and r['symbol']==symbol]
            observed=[r for r in scheduled if r['conditionalMinimumVolumeNetEur'] is not None]
            values=[r['conditionalMinimumVolumeNetEur'] for r in observed]
            mean=sum(values,ZERO)/len(values) if values else None
            se=(sum(((v-mean)**2 for v in values),ZERO)/(len(values)-1)/len(values)).sqrt() if len(values)>1 else None
            summaries.append(dict(candidate=candidate,symbol=symbol,scheduledDays=len(scheduled),completePaths=len(observed),
                activeForecasts=sum(r['side'] in (-1,1) for r in observed),
                completeCalendarUnfundedCounterfactualNetEur=sum(values,ZERO) if len(observed)==len(p['replayDays']) else None,
                observedPathsOnlyNetSumEur=sum(values,ZERO),descriptiveDailyMeanEur=mean,descriptiveDailyStandardErrorEur=se,
                meanBrier=sum((r['midpointDirectionBrier'] for r in observed),ZERO)/len(observed) if observed else None,
                capacitySupportedPaths=sum(r['minimumVolumeCapacityScenario'] for r in observed),
                multiplicityAdjustedQualification=False))
        group_summaries[sl]=summaries
    primary=next(x for x in cases if x['uncertaintyMultiplier']==2 and x['slippageMultiple']==1)
    return dict(schema='mxm-sqp1-authentic-economic-result-v1',protocol=p,pilot=b['pilotSupport'],portfolioCases=cases,
        standaloneUnfundedMinimumVolumeCounterfactuals=standalones,standaloneGroupSummaries=group_summaries,leaveOneCandidateOut=ablations,
        forecastCount=len(forecasts),predeclaredCandidateGroups=len(candidate_groups),missingForecasts=len(b['completedDays'])*len(candidate_groups)-len(forecasts),nativeClockWindowsChecked=book.parity,allCasesAndAblationsDisclosed=True,
        verdict=('CLOSED_EXACT_NONPOSITIVE_PRIMARY_CONFIGURATION_NO_RETUNING' if primary['ledgerReport']['closed_net_eur']<=0 else 'FROZEN_POSITIVE_DEVELOPMENT_RESULT_UNQUALIFIED_NO_RETUNING'),
        primaryConditionalNetEur=primary['ledgerReport']['closed_net_eur'],independentConfirmation=False,
        economicQualification=False,hard21Proven=False,globalDrawdownCertified=False,historicalTariffsConfirmed=False,
        actualFills=False,historicalMarginConfirmed=False,ordersSubmitted=0,cloudActivated=False,
        statisticalLimit='EIGHT_SHARED_CALIBRATION_AND_EIGHT_REPLAY_DAYS;24_CANDIDATE_GROUPS_AND4_CASES_ARE_NOT_INDEPENDENT;NO_INFERENTIAL_EDGE_CLAIM',
        nativeLimit='FORECAST_CLOCK_VALUATION_ALLOCATION_HOLDING_RISK_NATIVE;FUNDED_LEDGER_STILL_PYTHON_NOT_FULL_CLOUD_EQUIVALENCE')

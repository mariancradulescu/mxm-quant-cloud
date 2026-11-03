"""EPA1 conditional economic replay using the native selector and existing ledger.
No independent Python allocator; accounting/fills inherit FundedReplay unchanged.
"""
import hashlib,json,os,subprocess,tempfile,math
from pathlib import Path
from dataclasses import replace
from decimal import Decimal as D
from .funded_replay import FundedReplay,Quote,Contract,Decision,IncompleteEvidence
from .portfolio_economic_source import protocol,day_clock

DLL='src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll'
ZERO=D(0)


def native(data,mode):
    with tempfile.TemporaryDirectory(prefix='mxm-epa1-private-') as tmp:
        inp,out=Path(tmp)/'input.json',Path(tmp)/'output.json'
        inp.write_text(json.dumps(data,sort_keys=True,default=str));inp.chmod(0o600)
        env={k:v for k,v in os.environ.items() if not k.startswith(('R3_','CTRADER_','MXM_V4_'))}
        subprocess.run(['dotnet',DLL,str(inp),str(out),mode],check=True,env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return json.loads(out.read_text(),parse_float=D)


def fee(q,units):return max(D(str(q['FeeLinearEurPerUnit']))*D(units),D(str(q['FeeFloorEur'])))
def net_quote(q,amount):return amount*D(str(q['EurCreditPerQuote'] if amount>=0 else q['EurDebitPerQuote']))
def point_quotes(valued,t):return valued.get(str(t))
def valued_quote(point,s):return point['Quotes'].get(s) if point else None


class SynchronizedFundedReplay(FundedReplay):
    """Only an atomic dispatcher; _entry/_exit/_mark and accounting are shared.

    Stops/targets are deliberately unsupported here: EPA1 uses fixed clock exits.
    No interpolation, fabricated tick path, new fill model or continuous DD proof.
    """
    def _floating(self,p,q):
        value=super()._floating(p,q)
        current=self._mark_valuations.get(q.symbol)
        if current is None or self._valuation_clock!=q.t:raise IncompleteEvidence('CURRENT_EXIT_FEE_MARK_MISSING')
        return value+p.request.contract.exit_commission_eur-fee(current,p.request.units)

    def quote_batch(self,point,slip_multiple,source_hash):
        at=point['At'];new={s:Quote(at,s,D(str(v['Bid'])),D(str(v['Ask'])),
            D(str(v['EurCreditPerQuote'])),D(str(v['EurDebitPerQuote'])),source_hash)
            for s,v in point['Quotes'].items()}
        if any(p.request.stop is not None or p.request.target is not None for p in self.open.values()):
            raise IncompleteEvidence('EPA1_FIXED_EXIT_DISPATCH_ONLY')
        for q in new.values():
            q.check()
            if q.symbol in self.quotes and self.quotes[q.symbol].t>=at:raise IncompleteEvidence('EPA1_REPEATED_BATCH')
        self._clock(at);self.quotes.update(new);self.source_ids.add(source_hash)
        self._mark_valuations=point['Quotes'];self._valuation_clock=at
        rest=[]
        for d in self.pending:
            q=new.get(d.symbol)
            if q is None or at<d.t+d.latency_ms:rest.append(d);continue
            if d.action=='OPEN':
                v=point['Quotes'][d.symbol]
                contract=replace(d.contract,entry_commission_eur=fee(v,d.units),
                    slippage_price_each_side=(q.ask-q.bid)*slip_multiple)
                self._entry(replace(d,contract=contract),q)
            elif d.position_id in self.open:
                self._exit(d.position_id,q,'EPA1_FIXED_CLOCK_OBSERVED_QUOTE',fee(point['Quotes'][d.symbol],self.open[d.position_id].request.units))
        self.pending=rest;self._mark(at)


def funding_condition(contract):
    return (contract.get('swapPeriod')==24 and isinstance(contract.get('swapTime'),int) and
            0<=contract['swapTime']<1440 and not 540<=contract['swapTime']<=780)


def calibration_scenario(plan,day,symbol,candidate,valued,slip):
    start=day_clock(day);p=plan.get((candidate,symbol,start))
    points=[point_quotes(valued,start+i*3600000) for i in range(5)]
    if p is None or any(valued_quote(v,symbol) is None for v in points):return None
    first=points[0]['Quotes'][symbol];direction=p['Side']
    spread=D(str(first['Ask']))-D(str(first['Bid']));slippage=spread*slip
    entry=D(str(first['Ask'] if direction>0 else first['Bid']))+direction*slippage
    pnl=[];cash=[]
    for point in points:
        q=point['Quotes'][symbol]
        out=D(str(q['Bid'] if direction>0 else q['Ask']))-direction*slippage
        converted=net_quote(q,D(direction)*(out-entry));cash.append(converted)
        # Fee slope + floor is a conservative bound on max(slope*units,floor).
        pnl.append(converted-D(str(first['FeeLinearEurPerUnit']))-D(str(q['FeeLinearEurPerUnit'])))
    return dict(StateId='EPA1/'+day,KnownAt=points[-1]['At'],Estimation=True,
        NetPerUnitEur=pnl[-1],FixedCostEur=D(str(first['FeeFloorEur']))+max(D(str(point['Quotes'][symbol]['FeeFloorEur'])) for point in points),
        LossPerUnitEur=max(ZERO,-min(pnl)),PeakPerUnitEur=max(ZERO,max(cash)))


def run_replay(b,plan,valued,p,z,slip,removed=None,keep_ledger=True):
    replay=SynchronizedFundedReplay(max_staleness_ms=1000,financing_schedule_proven=False)
    ledger=[];decisions=[];gaps=[];changes=[];last_units={};all_cal={}
    for candidate in p['families']:
        for s in p['universe']:
            all_cal[candidate,s]=[calibration_scenario(plan,d,s,candidate,valued,slip) for d in p['calibrationDays']]
    # Data-only availability rule fixed before retrieval; calibration source is
    # entirely earlier than the replay. No future outcome determines admission.
    cal_days=[d for i,d in enumerate(p['calibrationDays']) if all(point_quotes(valued,day_clock(d)+j*3600000) is not None for j in range(5))]
    completed_day_nets=[]
    for day in p['replayDays']:
        clock=day_clock(day);before=replay.balance
        pre=point_quotes(valued,clock-p['preDecisionQuoteSeconds']*1000)
        if replay.open or replay.pending:
            gaps.append(dict(day=day,reason='UNRESOLVED_EXPOSURE_ENTRIES_SUSPENDED'));break
        if pre is None:
            gaps.append(dict(day=day,reason='PREDECISION_SYNCHRONIZED_QUOTES_MISSING'))
            completed_day_nets.append(dict(day=day,netEur='0',status='NO_PREDECISION_SOURCE_NO_ADMISSION'))
            continue
        if pre['At']>=clock:raise IncompleteEvidence('FUTURE_PREDECISION_QUOTE')
        # Flat at each daily boundary; this is a sampled peak reference only.
        account=dict(EquityEur=replay.balance,PeakReferenceEur=max(replay.peak,replay.balance),FreeMarginEur=replay.balance,
            MinimumUnits=1,StepUnits=1,MaximumUnits=1,MarginPerUnitEur=1,MarginCoverageScenarioRatio=1,
            EffectiveIndependentBlocks=max(2,len(cal_days)),UncertaintyMultiplier=z)
        states=[dict(StateId='EPA1/'+d,KnownAt=point_quotes(valued,day_clock(d)+4*3600000)['At'],Estimation=True,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0) for d in cal_days]
        opportunities=[];complete=[];executions={};research_rows={}
        for candidate in p['families']:
            for s in p['universe']:
                name=candidate+'/'+s
                if name==removed:continue
                proposal=plan.get((candidate,s,clock))
                if proposal is None:
                    ledger.append(dict(day=day,candidate=candidate,symbol=s,reason='FROZEN_CAUSAL_FEATURE_WARMUP_OR_SOURCE_MISSING',units=0));continue
                terms=b['symbols'][s];c=terms['contract'];q=valued_quote(pre,s)
                minimum=int(c['minVolume'])//100;step=int(c['stepVolume'])//100;maximum=int(c['maxVolume'])//100
                if minimum<=0 or step<=0 or int(c['minVolume'])%100 or int(c['stepVolume'])%100:raise IncompleteEvidence('VOLUME_ENCODING')
                margin=D(terms['currentMarginPerUnitBoundEur'])
                financial_max=min(maximum,terms['maxQueriedUnits'],minimum+max(0,int((replay.balance/margin-minimum)//step))*step)
                scenarios=[all_cal[candidate,s][p['calibrationDays'].index(d)] for d in cal_days]
                valid=(len(cal_days)>=p['minimumCompleteCalibrationBlocks'] and q is not None and all(v is not None for v in scenarios) and funding_condition(c))
                pid=name+'/'+str(clock)
                grid=dict(EquityEur=replay.balance,CertifiedPeakEur=0,FreeMarginEur=replay.balance,MinimumUnits=minimum,StepUnits=step,MaximumUnits=financial_max,
                    MarginPerUnitEur=margin,BrokerStopoutEquityToMargin=0,Reconciled=False,CompleteJointRiskEvidence=False,
                    EffectiveIndependentBlocks=max(2,len(cal_days)),UncertaintyMultiplier=z)
                through=max((v['KnownAt'] for v in scenarios if v is not None),default=clock-1)
                opportunities.append(dict(Id=pid,Candidate=candidate,Symbol=s,RedundancyKey=s+'/'+str(clock)+'/'+str(proposal['Side']),Direction=proposal['Side'],
                    AvailableAt=clock,CalibratedThrough=through,Level=1,ExecutionEvidenceComplete=False,VolumeGrid=grid,Scenarios=scenarios if valid else []))
                if valid:
                    complete.append(pid)
                    estimates=[D(minimum)*v['NetPerUnitEur']-v['FixedCostEur'] for v in scenarios]
                    mean=sum(estimates,ZERO)/len(estimates)
                    se=(sum(((v-mean)**2 for v in estimates),ZERO)/(len(estimates)-1)/len(estimates)).sqrt()
                    research_rows[pid]=dict(estimatedMinimumVolumeNetEur=mean,estimatedMeanStandardErrorEur=se,calibrationBlocks=len(estimates))
                    executions[pid]=Contract(minimum,step,maximum,margin,fee(q,minimum),fee(q,minimum),
                        (D(str(q['Ask']))-D(str(q['Bid'])))*slip,'CONDITIONAL_CURRENT_BROKER_TARIFF_MARGIN_SCENARIO')
                else:research_rows[pid]=dict(inputGap='CALIBRATION_COST_VOLUME_OR_CURRENT_FUNDING_EVIDENCE_INCOMPLETE')
        if len(states)<2:
            gaps.append(dict(day=day,reason='CALIBRATION_JOINT_STATES_INCOMPLETE'));break
        request=dict(Scope='EPA1_CONDITIONAL_RESEARCH_NOT_CERTIFIED',CommonHorizonMinutes=240,Clock=clock,Account=account,
            Baseline=states,Opportunities=opportunities,LedgerReconciled=True,ScenarioCompleteOpportunityIds=complete)
        choice=native(request,'--estimate-portfolio-opportunities')
        decisions.append(dict(day=day,requestSha256=hashlib.sha256(json.dumps(request,sort_keys=True,default=str).encode()).hexdigest(),result=choice))
        by_id={o['Id']:o for o in opportunities}
        selected={x['Id']:x for x in choice['Allocations']}
        reasons={x['Id']:x['Reason'] for x in choice['Declined']}
        for o in opportunities:
            a=selected.get(o['Id']);units=int(a['Units']) if a else 0
            row=dict(day=day,id=o['Id'],candidate=o['Candidate'],symbol=o['Symbol'],side=o['Direction'],units=units,
                reason=a['Reason'] if a else reasons[o['Id']],marginalUtilityLower=a['MarginalUtilityLower'] if a else None,**research_rows[o['Id']])
            ledger.append(row)
            if units:
                old=last_units.get((o['Candidate'],o['Symbol']),0)
                changes.append(dict(day=day,candidate=o['Candidate'],symbol=o['Symbol'],previousUnits=old,selectedUnits=units))
                last_units[o['Candidate'],o['Symbol']]=units
                con=replace(executions[o['Id']],entry_commission_eur=fee(pre['Quotes'][o['Symbol']],units),exit_commission_eur=fee(pre['Quotes'][o['Symbol']],units))
                replay.decide(Decision(clock,clock,o['CalibratedThrough'],o['Id'],o['Symbol'],'OPEN',1000,o['Direction'],units,con))
        for key,old in list(last_units.items()):
            pid=key[0]+'/'+key[1]+'/'+str(clock)
            if old and pid not in selected:
                changes.append(dict(day=day,candidate=key[0],symbol=key[1],previousUnits=old,selectedUnits=0));last_units[key]=0
        for minute in range(0,241,p['replayMarkStepMinutes']):
            nominal=clock+minute*60000;point=point_quotes(valued,nominal)
            if minute==240:
                for pid,pos in list(replay.open.items()):replay.decide(Decision(nominal,nominal,pos.request.calibrated_through,pid,pos.request.symbol,'CLOSE',1000))
            if point is None:
                if replay.open:replay.incomplete_marks=True
                if minute==0:
                    for d in replay.pending:replay.rejected.append((d.position_id,'NO_SYNCHRONIZED_ENTRY_SOURCE_WITHIN_WINDOW'))
                    replay.pending=[]
                gaps.append(dict(day=day,minute=minute,reason='SYNCHRONIZED_EXECUTION_OR_HOLDING_SOURCE_MISSING'))
                continue
            replay.quote_batch(point,slip,hashlib.sha256((b['protocolSha256']+str(nominal)+str(point['At'])).encode()).hexdigest())
        completed_day_nets.append(dict(day=day,netEur=replay.balance-before,status='FLAT_RECONCILED' if not replay.open and not replay.pending else 'EXPOSURE_UNRESOLVED'))
    # Rejected opportunity outcomes are separate, minimum-volume, unfunded
    # counterfactuals. They are NEVER summed into portfolio capital or selected.
    for row in ledger:
        if row.get('units') or 'id' not in row:continue
        day=row['day'];s=row['symbol'];first=point_quotes(valued,day_clock(day));last=point_quotes(valued,day_clock(day)+4*3600000)
        a=valued_quote(first,s);zq=valued_quote(last,s)
        if a is None or zq is None or not funding_condition(b['symbols'][s]['contract']):row['unfundedMinimumVolumeCounterfactualNetEur']=None;continue
        units=int(b['symbols'][s]['contract']['minVolume'])//100;side=row['side'];sp=(D(str(a['Ask']))-D(str(a['Bid'])))*slip
        entry=D(str(a['Ask'] if side>0 else a['Bid']))+side*sp;exit=D(str(zq['Bid'] if side>0 else zq['Ask']))-side*sp
        row['unfundedMinimumVolumeCounterfactualNetEur']=net_quote(zq,D(side*units)*(exit-entry))-fee(a,units)-fee(zq,units)
    report=replay.report()
    complete_flat=not replay.open and not replay.pending
    result=dict(uncertaintyMultiplier=z,slippageMultipleOfEntrySpreadEachSide=slip,removedCandidate=removed,
        policyRole='PRIMARY_UNCERTAINTY_SCREENED_CONDITIONAL_RESEARCH' if z==2 else 'PREDECLARED_CENTRAL_SENSITIVITY_NOT_ACCEPTANCE',
        estimationStatus='CONDITIONAL_CURRENT_TARIFF_MARGIN_FINANCING_AND_SLIPPAGE_SCENARIOS',
        ledgerReport=report,completeFlatLedger=complete_flat,dailyLedger=completed_day_nets,
        jointCalibrationDaysUsed=cal_days,sourceGaps=gaps,allocationChanges=changes,
        peakReferenceBasis='SAMPLED_ONLY_NOT_CERTIFIED',historicalFinancingVerified=False,
        brokerStopoutRatioKnown=False,marginCoverageScenarioRatio=1,
        verifiedSelectorEvidenceFlagsRemainFalse=True,finalTradingQualification=False)
    if keep_ledger:result.update(opportunityLedger=ledger,completedTrades=replay.trades,nativeDecisionReceipts=decisions)
    return result


def evaluate(b,original):
    p=protocol()
    native_source={k:v for k,v in b.items() if k not in ['raw','eventIndices','auditReceipt']}
    valued=native(native_source,'--value-portfolio-source')['Snapshots']
    print('EPA1_NATIVE_EUR_VALUATION_COMPLETE '+str(len(valued)),flush=True)
    baseline={k:v for k,v in original.items() if k not in ['raw','traderRaw','csharpReceipt']}
    planned=native(baseline,'--economic-portfolio-plan')
    print('EPA1_FROZEN_CAUSAL_PLAN_BOUND',flush=True)
    plan={(x['Candidate'],x['Symbol'],x['Clock']):x for x in planned}
    results=[];ablations=[]
    for z in map(D,p['uncertaintyMultipliers']):
        for slip in map(D,p['slippageMultiplesOfObservedEntrySpreadEachSide']):
            results.append(run_replay(b,plan,valued,p,z,slip))
            latest=results[-1]
            print('EPA1_CONDITIONAL_SCENARIO '+json.dumps(dict(uncertainty=str(z),slippage=str(slip),trades=latest['ledgerReport']['complete_round_trips'],netEur=str(latest['ledgerReport']['closed_net_eur']),flat=latest['completeFlatLedger']),sort_keys=True),flush=True)
        full=next(x for x in results if x['uncertaintyMultiplier']==z and x['slippageMultipleOfEntrySpreadEachSide']==D('0.5'))
        for family in p['families']:
            for symbol in p['universe']:
                removed=family+'/'+symbol
                smaller=run_replay(b,plan,valued,p,z,D('0.5'),removed,False)
                ablations.append(dict(uncertaintyMultiplier=z,removedCandidate=removed,
                    fullPortfolioConditionalNetEur=full['ledgerReport']['closed_net_eur'],
                    withoutCandidateConditionalNetEur=smaller['ledgerReport']['closed_net_eur'],
                    descriptiveIncrementalDifferenceEur=full['ledgerReport']['closed_net_eur']-smaller['ledgerReport']['closed_net_eur'],
                    withoutCandidateRoundTrips=smaller['ledgerReport']['complete_round_trips'],
                    completeFlatLedger=smaller['completeFlatLedger'],interpretation='EXPOSED_DEVELOPMENT_ABLATION_NOT_INDEPENDENT_ALPHA_OR_MODEL_SELECTION'))
    return dict(schema='mxm-epa1-authentic-conditional-portfolio-economics-v1',protocol=p,portfolioScenarios=results,
        nativeValuationCoverage={k:dict(valuedAssets=len(v['Quotes']),missing=v['Missing']) for k,v in valued.items()},
        contractFieldAvailability={s:{k:c['contract'].get(k) is not None for k in ['preciseTradingCommissionRate','preciseMinCommission','pnlConversionFeeRate','swapPeriod','swapTime']} for s,c in b['symbols'].items()},
        leaveOneCandidateOut=ablations,allPredeclaredScenariosReported=True,
        economicQualification=False,independentConfirmation=False,hard21Proven=False,globalDrawdownCertified=False,
        actualFills=False,historicalTariffsConfirmed=False,ordersSubmitted=0,cloudActivated=False,
        risk='Sampled joint calibration paths and sampled replay marks do not bound unseen peaks/troughs, gaps or liquidation slippage',
        fees='Native current-tariff adverse-notional/conversion bound; entry/exit fees recomputed from observed quotes, not certified historical charges',
        financing='Zero only as a current observed daily-schedule-outside-holding assumption; historical schedule unverified',
        researchAdmission='Explicit conditional endpoint; verified execution/certificate pathway remains protective',
        unit='One EUR200 capital ledger per predeclared research scenario; scenario/ablation capital never pooled')

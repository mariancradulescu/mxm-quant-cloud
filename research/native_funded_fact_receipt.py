"""Native accounting receipt on FROZEN modeled fill/mark facts, never SQP1 replay.

No forecast, selector, allocation or exit policy is called. Original intent/fill
clocks, quantities and marks are read as immutable facts; no new verdict is made.
"""
import hashlib,json,os
from pathlib import Path
from decimal import Decimal as D
from .custody import unseal_new
from .decode import need
from .portfolio_economic_replay import native,fee
from .portfolio_economic_source import partial_snapshot
from .sequence_portfolio_source import audit,window_events,clock


def receive():
    p=json.loads(Path('research/sequence_portfolio_protocol.json').read_text())
    frozen_path=Path('docs/SQP1_AUTHENTIC_RESULT.json');frozen=json.loads(frozen_path.read_text())
    data=Path('native-fact-source/source.envelope.json').read_bytes()
    need(hashlib.sha256(data).hexdigest()==frozen['sourceCiphertextSha256'],'NATIVE_FACT_ORIGINAL_SOURCE_HASH')
    b=json.loads(unseal_new(data,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),str(frozen['sourceRunId'])))
    need(audit(b,p)==b['auditReceipt'],'NATIVE_FACT_SOURCE_RAW_RECONCILIATION')
    times={x['at'] for c in frozen['portfolioCases'] for x in c['holdingRiskLedger']}
    times.update(t[k] for c in frozen['portfolioCases'] for t in c['completedTrades'] for k in ('opened_at','closed_at'))
    snapshots={}
    for at in sorted(times):
        nominal=at//900000*900000;events,complete=window_events(b,nominal,p)
        sides={s:[[[x['At'],x['Price']] for x in events if x['Symbol']==s and x['Side']==side] if complete[s] else None for side in (0,1)] for s in p['universe']}
        snapshots[str(at)]=partial_snapshot(sides,at,p['universe'],p['maximumSideAgeMs'])
    valued=native(dict(schema='mxm-frozen-observed-facts-v1',readOnly=True,depositCurrency='EUR',symbols=b['symbols'],snapshots=snapshots),'--value-portfolio-source')['Snapshots']
    cases=[]
    for case in frozen['portfolioCases']:
        trades={t['id']:t for t in case['completedTrades']};risk_by_at={r['at']:r for r in case['holdingRiskLedger']}
        events=[];slip=D(case['slippageMultiple'])
        def event(at,kind,t=None,**kw):
            row=dict(EventId=f"FACT/{case['uncertaintyMultiplier']}/{case['slippageMultiple']}/{len(events)}",At=at,Kind=kind,
                PositionId=t['id'] if t else '',Symbol=t['symbol'] if t else '',Side=t['side'] if t else 0,
                Units=t['units'] if t else 0,ExecutionPrice=0,FeeEur=0,MarginPerUnit=0,SlippagePerSide=0,
                AvailableAt=at,CalibratedThrough=at,LatencyMs=1000,Reason='FROZEN_MODELED_FACT',EvidenceHash=frozen['sourceCiphertextSha256'],Quotes=[])
            row.update(kw);events.append(row)
        def quotes(at,positions):
            result=[]
            for pos in positions:
                t=trades[pos['Id']];s=t['symbol'];q=valued[str(at)]['Quotes'][s]
                result.append(dict(Symbol=s,At=at,Bid=q['Bid'],Ask=q['Ask'],EurCredit=q['EurCreditPerQuote'],EurDebit=q['EurDebitPerQuote'],
                    ExitFeePerUnit=q['FeeLinearEurPerUnit'],ExitFeeFloor=q['FeeFloorEur'],MarginPerUnit=D(pos['MarginEnvelopeEur'])/t['units']))
            return result
        for t in trades.values():
            day=t['id'].split('/')[-1];nominal=clock(p,day);decision=next(d for d in case['nativeDecisions'] if d['day']==day)
            selected=next(a for a in decision['result']['Allocations'] if a['Id']==t['id'])
            need(D(selected['Units'])==t['units'],'NATIVE_FACT_FROZEN_QUANTITY')
            event(decision['clock'],'REQUEST_OPEN',t,AvailableAt=nominal,CalibratedThrough=max(clock(p,d)+3658000 for d in p['calibrationDays']))
            opening=risk_by_at[t['opened_at']];position=next(x for x in opening['Positions'] if x['Id']==t['id'])
            q=valued[str(t['opened_at'])]['Quotes'][t['symbol']];spread=D(q['Ask'])-D(q['Bid']);slippage=spread*slip
            entry=D(q['Ask'] if t['side']>0 else q['Bid'])+t['side']*slippage
            event(t['opened_at'],'OPEN_FILL',t,ExecutionPrice=entry,FeeEur=fee(q,t['units']),MarginPerUnit=D(position['EntryMarginEur'])/t['units'],SlippagePerSide=slippage,
                Quotes=quotes(t['opened_at'],opening['Positions']))
            early=[x['at'] for x in case['holdingRiskLedger'] if t['id'] in x['ExitIds'] and x['at']+1000<=t['closed_at']]
            requested=min(early) if t['closed_at']<nominal+3600000 else nominal+3600000
            event(requested,'REQUEST_CLOSE',t,Reason='FROZEN_CAPACITY_PROTECTION' if early and t['closed_at']<nominal+3600000 else 'FROZEN_SCHEDULED_CLOSE')
            q=valued[str(t['closed_at'])]['Quotes'][t['symbol']]
            exit_price=D(q['Bid'] if t['side']>0 else q['Ask'])-t['side']*slippage
            event(t['closed_at'],'CLOSE_FILL',t,ExecutionPrice=exit_price,FeeEur=fee(q,t['units']),Quotes=quotes(t['closed_at'],risk_by_at[t['closed_at']]['Positions']),Reason=t['exit_reason'])
        for row in case['holdingRiskLedger']:event(row['at'],'MARK',Quotes=quotes(row['at'],row['Positions']))
        order={'REQUEST_OPEN':0,'REQUEST_CLOSE':1,'OPEN_FILL':2,'MARK':3,'CLOSE_FILL':4}
        events.sort(key=lambda x:(x['At'],order[x['Kind']],x['EventId']))
        received=native(events,'--native-funded-facts');summary=received['Summary'];original=case['ledgerReport']
        tolerance=D('1e-18')
        need(abs(D(summary['CashEur'])-D(original['balance_eur']))<tolerance and abs(D(summary['ClosedNetEur'])-D(original['closed_net_eur']))<tolerance,
             'NATIVE_FACT_CASH_AND_NET_EQUIVALENCE')
        need(summary['CompleteRoundTrips']==original['complete_round_trips'] and summary['OpenPositions']==0 and summary['PendingIntents']==0,'NATIVE_FACT_POSITION_EQUIVALENCE')
        need(abs(D(summary['MaximumSampledDrawdown'])-D(original['sampled_max_drawdown']))<tolerance,'NATIVE_FACT_FLOATING_EQUITY_DRAWDOWN_EQUIVALENCE')
        for old,new in zip(case['completedTrades'],received['Trades']):
            need(old['id']==new['PositionId'],'NATIVE_FACT_TRADE_ORDER')
            for left,right in [('gross_eur','GrossEur'),('spread_eur','SpreadEur'),('slippage_eur','SlippageEur'),('conversion_eur','ConversionEur'),('commissions_eur','CommissionsEur'),('net_eur','NetEur')]:
                need(abs(D(old[left])-D(new[right]))<tolerance,'NATIVE_FACT_COST_COMPONENT_EQUIVALENCE')
        cases.append(dict(uncertaintyMultiplier=case['uncertaintyMultiplier'],slippageMultiple=case['slippageMultiple'],events=len(events),
            frozenCashNetAndCostComponentsMatched=True,floatingDrawdownMatched=True,**received))
    result=dict(schema='mxm-native-funded-frozen-fact-receipt-v1',sourceRunId=frozen['sourceRunId'],executionRunId=int(os.environ['GITHUB_RUN_ID']),
        frozenResultSha256=hashlib.sha256(frozen_path.read_bytes()).hexdigest(),sourceCiphertextSha256=frozen['sourceCiphertextSha256'],
        cases=cases,forecastOrAllocatorOrExitPolicyRerun=False,newBrokerRequests=0,originalResultsChanged=False,
        liveBrokerFillRecoveryProven=False,globalDrawdownCertified=False,independentEconomicEdge=False,ordersSubmitted=0,cloudActivated=False)
    Path('native-funded-facts.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    print('NATIVE_FUNDED_FACT_RECEIPT '+json.dumps(result,sort_keys=True,default=str),flush=True)


if __name__=='__main__':
    try:receive()
    except Exception as error:
        import traceback
        print('NATIVE_FACT_FAILED_CLOSED '+type(error).__name__+' '+','.join(f.name+':'+str(f.lineno) for f in traceback.extract_tb(error.__traceback__)),flush=True)
        raise SystemExit(1)

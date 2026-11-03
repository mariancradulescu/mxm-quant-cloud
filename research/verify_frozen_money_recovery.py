"""Verify NEW native monetary-import path using frozen public settlements only.
No strategy, forecast, allocator, quote clock, model exit or broker request is run.
Synthetic identity namespaces are explicitly MODELED, never broker execution IDs.
"""
import hashlib,json,time
from decimal import Decimal as D
from pathlib import Path
from .portfolio_economic_replay import native

PATH=Path('docs/NATIVE_FUNDED_FACT_CONFIRMATION.json')
def verify():
    frozen=PATH.read_bytes();sha=hashlib.sha256(frozen).hexdigest()
    registry=json.loads(Path('research/evidence_registry.json').read_text())
    need=registry['nativeFundedFactReception']['confirmationSha256'];assert sha==need
    source=json.loads(frozen,parse_float=D);known=int(time.time()*1000);cases=[];expected=[]
    for old in source['cases']:
        key=str(old['uncertaintyMultiplier'])+'/'+str(old['slippageMultiple']);account='FROZEN_MODELED_CASE/'+key
        fills=[];intents=[];batches=[];cash=D(200);previous=D(200)
        entries=[]
        for point in old['Receipts']:
            after=D(point['CashEur'])
            if point['OpenPositions']==1 and point['PendingIntents']==0 and after<previous and (not entries or entries[-1]['cashAfter']!=after):
                # Opening transitions only; mark receipts never change cash.
                # Closing changes are excluded by OpenPositions==0 in this fixed book.
                entries.append(dict(fee=previous-after,cashAfter=after))
            previous=after
        assert len(entries)==len(old['Trades'])
        def leg(value,at):return dict(Amount=str(value),Currency='EUR',EurPerUnit='1',RateAt=at,EvidenceHash=sha)
        def batch():
            nonlocal batches
            orders=[];deals=[];positions={}
            for f in fills:
                closing=f['Kind']=='CLOSE';i=next(i for i in intents if i['OrderId']==f['OrderId'])
                orders.append(dict(OrderId=f['OrderId'],ClientIntentId=i['IntentId'],PositionId=f['PositionId'],Symbol=f['Symbol'],Side=f['Side'],RequestedUnits=f['Units'],ExecutedUnits=f['Units'],Closing=closing,Status='FILLED',UpdatedAt=f['At']))
                deals.append(dict(DealId=f['DealId'],OrderId=f['OrderId'],PositionId=f['PositionId'],Symbol=f['Symbol'],Side=f['Side'],Units=f['Units'],Closing=closing,At=f['At']))
                if closing:positions.pop(f['PositionId'])
                else:positions[f['PositionId']]=dict(PositionId=f['PositionId'],Symbol=f['Symbol'],Side=f['Side'],Units=f['Units'])
            snapshot=dict(AccountBinding=account,At=known,HistoryFrom=0,HistoryThrough=known,InventoryStable=True,OrdersComplete=True,DealsComplete=True,Orders=orders,Deals=deals,Positions=list(positions.values()))
            batches.append(dict(AccountBinding=account,Domain='FROZEN_MODELED_SETTLEMENT',Snapshot=snapshot,Facts=list(fills),BrokerCashEur=str(cash),InitialCapital200Proven=True,CashflowHistoryComplete=True,FinancingHistoryComplete=True,AdditionalExternalCashflowDetected=False,FundingRecords=[]))
        for ix,(trade,entry) in enumerate(zip(old['Trades'],entries)):
            # Price is NOT published in the frozen receipt: retain unknown.
            pid='MODELED_POSITION/'+trade['PositionId'];local='MODELED_LOCAL/'+trade['PositionId'];side=next(t['side'] for c in json.loads(Path('docs/SQP1_AUTHENTIC_RESULT.json').read_text())['portfolioCases'] if c['uncertaintyMultiplier']==str(old['uncertaintyMultiplier']) and c['slippageMultiple']==str(old['slippageMultiple']) for t in c['completedTrades'] if t['id']==trade['PositionId'])
            for closing in [False,True]:
                at=trade['ClosedAt'] if closing else trade['OpenedAt'];deal='MODELED_DEAL/'+str(ix)+('/close' if closing else '/open');order='MODELED_ORDER/'+deal
                # SubmittedAt is a modeled financial-record bound, NOT a claimed
                # broker request timestamp. No order submission proof is made.
                intents.append(dict(IntentId='MODELED_INTENT/'+deal,OrderId=order,PositionId=pid,Symbol=trade['Symbol'],Side=-side if closing else side,RequestedUnits=trade['Units'],Closing=closing,SubmittedAt=at,LedgerPositionId=local))
                assert D(trade['FinancingEur'])==0 # explicit frozen modeled conditional value
                commission=D(trade['CommissionsEur'])-entry['fee'] if closing else entry['fee']
                gross=D(trade['GrossEur'])-D(trade['SpreadEur'])-D(trade['SlippageEur']) if closing else D(0)
                conversion=D(trade['ConversionEur']) if closing else D(0)
                fills.append(dict(AccountBinding=account,Domain='FROZEN_MODELED_SETTLEMENT',Kind='CLOSE' if closing else 'OPEN',EventId='deal/'+deal,DealId=deal,OrderId=order,PositionId=pid,LedgerPositionId=local,Symbol=trade['Symbol'],Side=-side if closing else side,Units=trade['Units'],At=at,AvailableAt=known,Sequence=len(fills),ExecutionPrice=None,Gross=leg(gross,at),Commission=leg(commission,at),ConversionFee=leg(conversion,at),Financing=None,EvidenceHash=sha))
                cash+=gross-commission-conversion;batch()
        if not batches:batch()
        cases.append(dict(Id=key,AccountBinding=account,Intents=intents,Batches=batches));expected.append(old)
    result=native(cases,'--native-frozen-money-recovery')
    for old,new in zip(expected,result):
        assert abs(D(new['Summary']['CashEur'])-D(old['Summary']['CashEur']))<D('1e-18')
        assert abs(D(new['Summary']['ClosedNetEur'])-D(old['Summary']['ClosedNetEur']))<D('1e-18')
        assert new['Summary']['CompleteRoundTrips']==old['Summary']['CompleteRoundTrips']
        for receipt in new['Receipts']:assert receipt['Adopted'] and abs(D(receipt['RetainedLedger']['CashEur'])-D(receipt['ReconstructedCashEur']))<D('1e-18')
        assert not new['ActualBrokerRecoveryProven']
    receipt=dict(schema='mxm-native-monetary-recovery-frozen-receipt-v1',sourceFile=str(PATH),sourceSha256=sha,sourceOriginalStudyRunId=41706496201,
        newBrokerRequests=0,originalStudyRerun=False,originalResultsChanged=False,sourceIsModeledSettlementNotBrokerExecution=True,pricesRemainUnknown=True,
        monetaryToleranceEur='1e-18',cases=result,realBrokerFillRecoveryProven=False,cloudPersistenceProven=False,ordersSubmitted=0,cloudActivated=False)
    Path('native-monetary-recovery.public.json').write_text(json.dumps(receipt,sort_keys=True,indent=2,default=str)+'\n')
    print('PASS frozen settlement native monetary recovery; no study rerun, broker requests, orders or broker recovery certification')
if __name__=='__main__':verify()

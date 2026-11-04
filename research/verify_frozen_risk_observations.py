"""New monitor receives immutable MODELED holding valuations; no old policy rerun."""
import hashlib,json,time
from decimal import Decimal as D
from pathlib import Path
from .portfolio_economic_replay import native
SOURCE=Path('docs/SQP1_AUTHENTIC_RESULT.json')
def verify():
    raw=SOURCE.read_bytes();sha=hashlib.sha256(raw).hexdigest();p=json.loads(raw);r=json.load(open('research/evidence_registry.json'))
    assert r['frozenFileSha256'][str(SOURCE)]==sha
    now=int(time.time()*1000);inputs=[]
    for c in p['portfolioCases']:
        account='FROZEN_MODELED_HOLDING/'+str(c['uncertaintyMultiplier'])+'/'+str(c['slippageMultiple']);marks=[]
        start=min(x['clock'] for x in c['nativeDecisions'])
        def mark(at,equity,margin,stress,positions):
            return dict(AccountBinding=account,Domain='FROZEN_MODELED_HOLDING',EquityBasis='CONDITIONAL_LIQUIDATION_ESTIMATE',At=at,AvailableAt=now,
                CashEur=None,EquityEur=str(equity),MarginEur=str(margin),FreeMarginEur=str(equity-margin),CreditEur=None,
                InventoryStable=True,ComponentsIndependent=False,Positions=positions,AdditionalExitCostBoundEur='0',StressLossEur=str(stress),
                PlatformReportedStopoutRatio=None,RoundingToleranceEur='0.000000000000000001',EvidenceHash=hashlib.sha256((sha+str(at)).encode()).hexdigest())
        marks.append(mark(start,D(200),D(0),D(0),[])) # explicit original modeled initial state
        trades={t['id']:t for t in c['completedTrades']}
        for row in c['holdingRiskLedger']:
            assert not row['OutcomeUncertain']
            stress=sum((D(x['StressLossEur']) for x in row['Positions']),D(0));equity=D(row['StressEquityEur'])+stress
            positions=[dict(PositionId=x['Id'],Symbol=trades[x['Id']]['symbol'],Side=trades[x['Id']]['side'],Units=trades[x['Id']]['units'],NetPnlEur=None) for x in row['Positions']]
            marks.append(mark(row['at'],equity,D(row['UsedMarginEnvelopeEur']),stress,positions))
        assert len({x['At'] for x in marks})==len(marks)
        inputs.append(marks)
    outputs=native(inputs,'--native-risk-observations');summary=[]
    for c,o in zip(p['portfolioCases'],outputs):
        dd=o['State']['WorstSampledDrawdown'];expected=D(c['ledgerReport']['sampled_max_drawdown'])
        if c['holdingRiskLedger']:assert abs(D(dd)-expected)<D('1e-18')
        else:assert dd is None and o['State']['ValidSamples']==1
        assert o['RestartMatched'] and all(not x['ContinuousDrawdownCertified'] and not x['OrdersEnabled'] for x in o['Reports'])
        summary.append(dict(uncertainty=c['uncertaintyMultiplier'],slippage=c['slippageMultiple'],observations=o['State']['ValidSamples'],sampledDrawdown=dd,
            originalSampledDrawdown=str(expected),noHoldingMarksMeansNoMeasuredDrawdown=not c['holdingRiskLedger'],**o))
    result=dict(schema='mxm-frozen-holding-observation-receipt-v1',sourceFile=str(SOURCE),sourceSha256=sha,cases=summary,
        sourceIsConditionalModeledHoldingNotBrokerEquity=True,newEconomicNetEvidence=False,newBrokerRequests=0,
        originalStudyOrExitPolicyRerun=False,originalTradesChanged=False,protectionReviewsNotExecuted=True,
        realBrokerRiskRecoveryProven=False,continuousDrawdownCertified=False,cloudPersistenceProven=False,ordersSubmitted=0)
    Path('native-risk-observation.public.json').write_text(json.dumps(result,sort_keys=True,indent=2,default=str)+'\n')
    print('PASS immutable holding marks, nullable drawdown without observations and restored native risk monitor; no study replay')
if __name__=='__main__':verify()

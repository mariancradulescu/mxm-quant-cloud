"""Verify preserved EPA2 public cash/risk receipts without source access or rescoring."""
import hashlib,json
from pathlib import Path
from decimal import Decimal as D


def close(a,b):assert abs(D(str(a))-D(str(b)))<D('1e-18'),(a,b)
def total(rows,key):return sum((D(str(x[key])) for x in rows),D(0))


def verify():
    r=json.loads(Path('docs/EPA2_AUTHENTIC_HOLDING_RESULT.json').read_text())
    protocol=Path('research/portfolio_holding_protocol.json')
    assert r['protocol']==json.loads(protocol.read_text())
    assert r['sourceAudit']['protocolSha256']==hashlib.sha256(protocol.read_bytes()).hexdigest()
    assert r['rawCustodyReadbackMatched'] and r['originalEpa1ResultsFrozen']
    for k in ['actualFills','liquidityDepthObserved','historicalMarginAndTariffsVerified','independentConfirmation','globalDrawdownCertified','hard21Proven','economicQualification','ordersSubmitted','cloudActivated']:assert not r[k]
    assert r['brokerAccountStopoutThreshold'] is None
    cases=r['portfolioCases'];assert len(cases)==8 and len(r['leaveOneOut'])==12
    assert {(c['horizonMinutes'],c['holdingPolicy'],c['slippageMultiple']) for c in cases}=={(h,p,s) for h in [120,240] for p in ['FIXED_EXIT_REFERENCE','ACTIVE_CAPACITY_PROTECTION'] for s in ['0.5','1']}
    for c in cases:
        q=c['ledgerReport'];trades=c['completedTrades'];unresolved=c['unresolvedPositions']
        assert D(q['initial_eur'])==200 and q['complete_round_trips']==len(trades)
        assert q['open_positions']==len(unresolved) and q['pending_actions']==len(c['pendingModelActions'])
        assert c['completeFlatLedger']==(not unresolved and not c['pendingModelActions'])
        assert not q['global_drawdown_certified'] and not c['economicQualification']
        close(total(trades,'net_eur'),q['closed_net_eur'])
        close(D(200)+D(q['closed_net_eur'])-total(unresolved,'paidEntryCommissionEur'),q['balance_eur'])
        close(total(c['dailyLedger'],'closedNetEur'),D(q['balance_eur'])-200)
        close(sum(map(D,c['cohortClosedNetEur'].values())),D(q['balance_eur'])-200)
        allocations={a['Id']:a for d in c['nativeDecisionReceipts'] for a in d['result']['Allocations']}
        assert all(not d['result']['Qualified'] for d in c['nativeDecisionReceipts'])
        assert len({t['id'] for t in trades})==len(trades)
        for t in trades:
            assert allocations[t['id']]['Units']==t['units'] and t['opened_at']<t['closed_at']
            close(D(t['gross_eur'])-sum((D(t[k]) for k in ['spread_eur','slippage_eur','conversion_eur','commissions_eur','financing_eur']),D(0)),t['net_eur'])
        for t in unresolved:assert allocations[t['id']]['Units']==t['units']
        for m in c['holdingRiskLedger']:
            assert not m['AccountStopoutThresholdVerified'] and not m['GlobalDrawdownCertified']
            if m['UsedMarginEnvelopeEur'] is not None:
                close(total(m['Positions'],'MarginEnvelopeEur'),m['UsedMarginEnvelopeEur'])
                assert all(D(p['MarginEnvelopeEur'])>=max(D(p['EntryMarginEur']),D(p['RepricedMarginEur'])) for p in m['Positions'])
    primary=next(c for c in cases if c['horizonMinutes']==240 and c['holdingPolicy']=='ACTIVE_CAPACITY_PROTECTION' and c['slippageMultiple']=='1')
    for a in r['leaveOneOut']:close(D(primary['ledgerReport']['closed_net_eur'])-D(a['closedNetEur']),a['differenceFromFullEur'])
    original=json.loads(Path('docs/EPA1_AUTHENTIC_PORTFOLIO_RESULT.json').read_text())
    old={(c['uncertaintyMultiplier'],c['slippageMultipleOfEntrySpreadEachSide']):c for c in original['portfolioScenarios']}
    assert len(r['epa1ExecutionAudit']['cases'])==6
    for c in r['epa1ExecutionAudit']['cases']:
        assert c['originalClosedNetUnchanged'] and not c['originalAllocationsReselected'] and not c['originalResultOverwritten']
        close(c['originalClosedNetEur'],old[c['uncertaintyMultiplier'],c['slippageMultiple']]['ledgerReport']['closed_net_eur'])
    print('PASS EPA2 public cash, allocation and risk receipts plus unchanged EPA1 cash; no model rerun or qualification')


if __name__=='__main__':verify()

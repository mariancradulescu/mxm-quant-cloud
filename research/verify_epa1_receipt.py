"""Reconcile the frozen public economic ledger without source access or rescoring."""
import hashlib,json
from pathlib import Path
from decimal import Decimal as D


def verify():
    p=Path('docs/EPA1_AUTHENTIC_PORTFOLIO_RESULT.json')
    r=json.loads(p.read_text());protocol=json.loads(Path('research/portfolio_economic_protocol.json').read_text())
    assert r['protocol']==protocol
    assert r['sourceAudit']['protocolSha256']==hashlib.sha256(Path('research/portfolio_economic_protocol.json').read_bytes()).hexdigest()
    assert len(r['portfolioScenarios'])==6 and len(r['leaveOneCandidateOut'])==24
    assert {(s['uncertaintyMultiplier'],s['slippageMultipleOfEntrySpreadEachSide']) for s in r['portfolioScenarios']}=={(z,k) for z in ['0','2'] for k in ['0','0.5','1']}
    assert not r['economicQualification'] and not r['independentConfirmation'] and not r['actualFills'] and not r['ordersSubmitted']
    tolerance=D('1e-20')
    for scenario in r['portfolioScenarios']:
        ledger=scenario['ledgerReport'];trades=scenario['completedTrades']
        assert ledger['initial_eur']=='200' and scenario['completeFlatLedger']
        assert not ledger['global_drawdown_certified'] and not ledger['financing_schedule_declared']
        assert ledger['complete_round_trips']==len(trades) and ledger['open_positions']==ledger['pending_actions']==0
        assert len({t['id'] for t in trades})==len(trades)
        booked=sum((D(t['net_eur']) for t in trades),D(0))
        assert abs(booked-D(ledger['closed_net_eur']))<tolerance
        assert abs(D(200)+booked-D(ledger['balance_eur']))<tolerance
        assert abs(sum((D(d['netEur']) for d in scenario['dailyLedger']),D(0))-booked)<tolerance
        for trade in trades:
            net=D(trade['gross_eur'])-sum((D(trade[k]) for k in ['spread_eur','slippage_eur','conversion_eur','commissions_eur','financing_eur']),D(0))
            assert abs(net-D(trade['net_eur']))<tolerance
        allocations={a['Id']:a for d in scenario['nativeDecisionReceipts'] for a in d['result']['Allocations']}
        assert set(allocations)=={t['id'] for t in trades}
        assert all(allocations[t['id']]['Units']==t['units'] for t in trades)
        for decision in scenario['nativeDecisionReceipts']:assert not decision['result']['Qualified']
    for a in r['leaveOneCandidateOut']:
        assert a['completeFlatLedger']
        assert abs(D(a['fullPortfolioConditionalNetEur'])-D(a['withoutCandidateConditionalNetEur'])-D(a['descriptiveIncrementalDifferenceEur']))<tolerance
    print('PASS EPA1 original public-ledger arithmetic, all scenarios and ablations; no model rerun or qualification')


if __name__=='__main__':verify()

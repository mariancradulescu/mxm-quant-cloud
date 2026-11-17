"""Read-only arithmetic audit of an existing original LPM1 public receipt.
Does not access broker credentials, source prices, models or research execution.
"""
import hashlib,json,sys,math
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path

def audit(path):
    raw=Path(path).read_bytes();r=json.loads(raw,parse_float=D)
    assert r['Study']=='LPM1' and r['IndependentConfirmation'] is False and r['Qualified'] is False
    reports={}
    for name,b in r['Books'].items():
        ts=b['Trades'];sc=b['Scorecard'];ledger=b['Ledger'];n=len(ts)
        assert all(t['CompletesRoundTrip'] for t in ts)
        net=sum((D(t['NetEur']) for t in ts),D(0))
        assert abs(net-D(ledger['ClosedNetEur']))<D('0.00000001')
        if b['FullSettlementKnown']:
            assert abs(D(ledger['CashEur'])-300-net)<D('0.00000001')
            assert abs(D(sc['NetEur'])-net)<D('0.00000001')
            assert ledger['PendingIntents']==ledger['OpenPositions']==0
        assert sc['CompletedRoundTrips']==n
        counts=Counter(datetime.fromtimestamp(t['ClosedAt']/1000,timezone.utc).strftime('%G-W%V') for t in ts)
        assert all(counts.get(w,0)==v for w,v in sc['FundedCompletionsByIsoWeek'].items())
        assert len(sc['FundedCompletionsByIsoWeek'])==3
        assert list(b['NetDistribution']['Values'])==[t['NetEur'] for t in ts]
        assert len(b['Admissions'])==n or not b['FullSettlementKnown']
        rs=[]
        for t,a in zip(ts,b['Admissions']):
            assert a['At']<t['OpenedAt']<t['ClosedAt']
            rs.append(D(t['NetEur'])/D(a['InitialRiskEur']))
        assert all(abs(a-D(z))<D('0.00000001') for a,z in zip(rs,b['RDistribution']['Values']))
        wins=sum((D(t['NetEur']) for t in ts if t['NetEur']>0),D(0))
        losses=-sum((D(t['NetEur']) for t in ts if t['NetEur']<0),D(0))
        weeks={w:sum((D(t['NetEur']) for t in ts if datetime.fromtimestamp(t['ClosedAt']/1000,timezone.utc).strftime('%G-W%V')==w),D(0)) for w in sc['FundedCompletionsByIsoWeek']}
        vals=list(weeks.values());mean=sum(vals)/3
        se=(sum((v-mean)**2 for v in vals)/2/3).sqrt()
        reports[name]=dict(Trades=n,NetEur=net if b['FullSettlementKnown'] else None,ClosedNetEur=net,
            FinalCash=ledger['CashEur'],WeeklyTrips=sc['FundedCompletionsByIsoWeek'],WeeklyNet=weeks,
            WeeklyMeanMinus2SE=mean-2*se,WinRate=D(sum(t['NetEur']>0 for t in ts))/n if n else None,
            Expectancy=net/n if n else None,ProfitFactor=wins/losses if losses else None,
            WorstTrade=min((t['NetEur'] for t in ts),default=None),MeanR=sum(rs)/n if n else None,
            SampledDd=b['SampledFloatingDrawdown'],PeakMargin=sc['PeakMarginEur'],
            UncertainTrades=b['UncertainTrades'],UnknownLifecycles=b['UnknownLifecycleCount'],
            FullSettlementKnown=b['FullSettlementKnown'],Hard21=sc['Hard21AllEligibleWeeks'])
    comparisons={}
    for s in ('central','adverse'):
        c,p,cash=[reports[n+'_'+s] for n in ('CONTEXT','POOLED','CASH')]
        comparisons[s]=dict(ContextMinusPooled=None if c['NetEur'] is None or p['NetEur'] is None else c['NetEur']-p['NetEur'],
            ContextMinusCash=None if c['NetEur'] is None or cash['NetEur'] is None else c['NetEur']-cash['NetEur'])
    return dict(OriginalPublicReceiptSha256=hashlib.sha256(raw).hexdigest(),ArithmeticChecksPassed=True,
        ReexecutedResearch=False,Books=reports,IncrementalComparisons=comparisons,
        IndependentConfirmation=False,Qualified=False,
        Limit='Public arithmetic only; original encrypted tick source is required to audit fills, features and floating marks.')
if __name__=='__main__':
    result=audit(sys.argv[1])
    text=json.dumps(result,indent=2,default=str)+'\n'
    if len(sys.argv)>2:Path(sys.argv[2]).write_text(text)
    else:print(text)

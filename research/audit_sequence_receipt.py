"""Read-only arithmetic/causal audit of frozen SQP1 output. Never reruns models."""
import hashlib,json
from pathlib import Path
from decimal import Decimal as D
from collections import Counter,defaultdict
from datetime import datetime,timezone


def clock(p,day):
    return int(datetime.fromisoformat(day).replace(hour=p["nominalHourUtc"],tzinfo=timezone.utc).timestamp()*1000)


def audit():
    path=Path('docs/SQP1_AUTHENTIC_RESULT.json');r=json.loads(path.read_text());p=r['protocol']
    assert r['sourceRunId']==41706496201 and r['rawReadbackMatched']
    assert r['sourceAudit']['originalAccountBindingRechecked'] and r['sourceAudit']['evidenceRequests']==1173
    assert r['sourceAudit']['protocolSha256']==hashlib.sha256(Path('research/sequence_portfolio_protocol.json').read_bytes()).hexdigest()
    assert len(r['portfolioCases'])==4 and len(r['leaveOneCandidateOut'])==24
    assert len(r['standaloneGroupSummaries']['1'])==24
    output=[]
    for case in r['portfolioCases']:
        trades=case['completedTrades'];net=sum((D(t['net_eur']) for t in trades),D(0))
        report=case['ledgerReport']
        assert case['completeFlatLedger'] and not case['unresolvedPositions']
        assert net==D(report['closed_net_eur']) and abs(D(200)+net-D(report['balance_eur']))<D('1e-20')
        assert len({t['id'] for t in trades})==len(trades)==report['complete_round_trips']
        totals={k:sum((D(t[k]) for t in trades),D(0)) for k in ('gross_eur','spread_eur','slippage_eur','conversion_eur','commissions_eur','financing_eur','net_eur')}
        assert abs(totals['gross_eur']-sum((totals[k] for k in ('spread_eur','slippage_eur','conversion_eur','commissions_eur','financing_eur')),D(0))-net)<D('1e-20')
        attribution=defaultdict(lambda:dict(trades=0,netEur=D(0)))
        early=[]
        for t in trades:
            day=t['id'].split('/')[-1];nominal=clock(p,day)
            assert nominal+1000<=t['opened_at']<t['closed_at']<=nominal+3600000+58000
            assert D(t['financing_eur'])==0 # actual modeled duration never crosses into next day
            key='/'.join(t['id'].split('/')[:-1]);attribution[key]['trades']+=1;attribution[key]['netEur']+=D(t['net_eur'])
            if t['closed_at']<nominal+3600000:
                triggers=[x for x in case['holdingRiskLedger'] if x['day']==day and t['id'] in x['ExitIds'] and x['at']+1000<=t['closed_at']]
                assert triggers
                early.append(dict(id=t['id'],firstProtectiveSignalAt=min(x['at'] for x in triggers),closedAt=t['closed_at'],
                    legacyExitLabel=t['exit_reason'],interpretedCause='MODEL_CAPACITY_PROTECTION_NOT_BROKER_LIQUIDATION'))
        output.append(dict(uncertaintyMultiplier=case['uncertaintyMultiplier'],slippageMultiple=case['slippageMultiple'],
            accounting=totals,endingCashEur=report['balance_eur'],roundTrips=len(trades),
            maximumSimultaneousPositions=case['maximumSimultaneousPositions'],sampledDrawdown=report['sampled_max_drawdown'],
            candidateFixedBookAttribution=dict(attribution),attributionIsNotMarginalReallocation=True,
            protectiveExitsConfirmedFromClockAndRiskLedger=early,
            holdingSourceGapCount=len(case['sourceGaps']),executionOutcomeUncertain=case['executionOutcomeUncertain']))
    primary=next(c for c in r['portfolioCases'] if c['uncertaintyMultiplier']=='2' and c['slippageMultiple']=='1')
    assert not primary['completedTrades']
    for x in r['leaveOneCandidateOut']:
        assert x['fullFlat'] and x['withoutFlat'] and D(x['incrementalConditionalNetEur'])==0
    result=dict(schema='mxm-sqp1-frozen-public-receipt-audit-v1',sourceRunId=r['sourceRunId'],executionCommitSha='626a9baaca98f0b0bb018b521cba83f9836add06',
        originalResultSha256=hashlib.sha256(path.read_bytes()).hexdigest(),modelOrAllocationRerun=False,brokerRequests=0,
        cases=output,primaryDeclineReasons=dict(Counter(x['reason'] for x in primary['opportunityLedger'])),
        scheduledStandaloneReplayRowsPerSensitivity=192,
        completeStandaloneReplayRowsPerSensitivity={sl:sum(x['conditionalMinimumVolumeNetEur'] is not None for x in rows) for sl,rows in r['standaloneUnfundedMinimumVolumeCounterfactuals'].items()},
        primaryAblationsAllZeroFromAbstention=True,independentMarginalContributionDemonstrated=False,
        originalLegacyExitLabelsPreserved=True,globalDrawdownCertified=False,independentConfirmation=False,economicQualification=False)
    return result


if __name__=='__main__':
    output=audit();Path('docs/SQP1_FROZEN_RECEIPT_AUDIT.json').write_text(json.dumps(output,sort_keys=True,indent=2,default=str)+'\n')
    print('PASS SQP1 frozen accounting, actual modeled holding clocks, protective exit linkage and attribution; no model rerun')

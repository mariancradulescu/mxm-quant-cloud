"""Frozen-receipt arithmetic only. No source, model, allocator or quote calls."""
from collections import Counter
from decimal import Decimal as D
import gzip
import hashlib
import json
from pathlib import Path
import statistics
import sys

P=Path('docs/MSP1_AUTHENTIC_CONDITIONAL_RESULT.json.gz')
OUTPUT=Path('docs/MSP1_RECEIPT_AUDIT.json')
ORIGINAL_SHA='7eecc3f8c8fce1fc1d55cf238faebe93dd538686af76a36c086ee8d39edf8d7f'


def build():
    raw=gzip.decompress(P.read_bytes())
    assert hashlib.sha256(raw).hexdigest()==ORIGINAL_SHA,'ORIGINAL_MSP1_RECEIPT_CHANGED'
    r=json.loads(raw);p=r['Protocol'];groups=r['Groups'];n=lambda x:D(str(x))
    variants=['PRIMARY_ALL','REMOVE_PERSISTENT','REMOVE_TRANSITORY']
    expected={(s,m,h*m,v) for s in p['universe'] for m in p['minutes'] for h in p['horizonBars'] for v in variants}
    actual={(g['Symbol'],g['Minutes'],g['HorizonMinutes'],g['Variant']) for g in groups}
    assert actual==expected and len(groups)==len(expected)==288,'MSP1_GROUP_DISCLOSURE'
    followup=[]
    for g in groups:
        for phase in ['Selection','ExposedAudit']:
            assert len(g[phase])==3
            for row in g[phase]:
                assert row['FullWeeks']==13 and len(row['Weekly'])==13
                assert sum(w['Proposals'] for w in row['Weekly'])==row['Proposals']
                assert sum(w['Missing'] for w in row['Weekly'])==row['MissingOutcomes']
                assert row['KnownOutcomes']+row['MissingOutcomes']==row['Proposals']
                assert abs(sum(n(w['KnownOnlyConditionalNetBps']) for w in row['Weekly'])-n(row['KnownOnlyNetBpsSum']))<D('1e-7')
                assert (row['ConditionalNetBpsSum'] is None)==(row['MissingOutcomes']>0)
        a=g['Selection'][1]
        supported=(g['Variant']=='PRIMARY_ALL' and a['Proposals']>=30 and a['ActiveWeeks']>=8 and
                   a['MissingOutcomes']==0 and a['WeeklyDescriptive90LowerBps'] is not None and n(a['WeeklyDescriptive90LowerBps'])>0)
        assert supported==g['ExecutionPricingFollowupSupported']
        if supported:followup.append(g['Id'])
    assert followup==r['PrimaryFollowupCandidateIds']==[]
    primary=[g for g in groups if g['Variant']=='PRIMARY_ALL'];counts=[]
    for phase in ['Selection','ExposedAudit']:
        for case in range(3):
            rows=[g[phase][case] for g in primary];complete=[x for x in rows if x['MissingOutcomes']==0 and x['Proposals']>0]
            counts.append(dict(Phase=phase,CostCase=r['CostScenarios'][case],PrimaryGroups=len(rows),
                Proposals=sum(x['Proposals'] for x in rows),MissingTargets=sum(x['MissingOutcomes'] for x in rows),
                CompleteActiveGroups=len(complete),PositiveCompleteGroups=sum(n(x['ConditionalNetBpsSum'])>0 for x in complete),
                IncompleteGroups=sum(x['MissingOutcomes']>0 for x in rows),ZeroProposalGroups=sum(x['Proposals']==0 for x in rows),
                IncompleteForwardPaths=sum(x['IncompleteForwardPaths'] for x in rows),
                UnknownFundingForecasts=sum(x['UnpricedFundingForecasts'] for x in rows)))
    variant_counts=[]
    for variant in variants:
        for phase in ['Selection','ExposedAudit']:
            for case in range(3):
                rows=[g[phase][case] for g in groups if g['Variant']==variant]
                variant_counts.append(dict(Variant=variant,Phase=phase,CostCase=r['CostScenarios'][case],
                    Proposals=sum(x['Proposals'] for x in rows),
                    CompletePositiveGroups=sum(x['MissingOutcomes']==0 and x['Proposals']>0 and n(x['ConditionalNetBpsSum'])>0 for x in rows),
                    PositiveDescriptive90LowerGroups=sum(x['WeeklyDescriptive90LowerBps'] is not None and n(x['WeeklyDescriptive90LowerBps'])>0 for x in rows)))
    predictive=[]
    for phase in ['SelectionPredictive','ExposedAuditPredictive']:
        for variant in variants:
            rows=[g[phase] for g in groups if g['Variant']==variant and g[phase]['KnownForecasts']]
            predictive.append(dict(Phase=phase,Variant=variant,Groups=len(rows),
                KnownForecasts=sum(x['KnownForecasts'] for x in rows),
                GroupsBrierBelowNeutral=sum(n(x['Brier'])<D('.25') for x in rows),
                MedianBrier=str(statistics.median(n(x['Brier']) for x in rows)),NeutralBrier='.25'))
    amplitude=[]
    for m in p['minutes']:
        for h in p['horizonBars']:
            rows=[a for a in r['Amplitude'] if a['Minutes']==m and a['HorizonMinutes']==h*m and a['MedianAbsMoveBps'] is not None]
            amplitude.append(dict(Minutes=m,HorizonMinutes=h*m,Assets=len(rows),
                MinAssetMedianAbsMoveBps=str(min(n(a['MedianAbsMoveBps']) for a in rows)),
                MaxAssetMedianAbsMoveBps=str(max(n(a['MedianAbsMoveBps']) for a in rows)),
                IsPredictability=False))
    cells=Counter()
    for g in primary:cells.update(g['Selection'][1]['CostCells'])
    return dict(Schema='mxm-msp1-frozen-receipt-audit-v1',OriginalJsonSha256=ORIGINAL_SHA,
        ExecutionRunId=r['ExecutionRunId'],SourceBars=sum(sum(s['rawBars'].values()) for s in r['SourceAudit']),
        OriginalCostObservationCount=r['OriginalCostObservationCount'],CostCalibrationDatesMin=min(c['DistinctDates'] for c in r['CostModel']),
        CostCalibrationDatesMax=max(c['DistinctDates'] for c in r['CostModel']),AllGroups=288,PrimaryGroups=96,
        PrimaryCostCaseCounts=counts,AllVariantCostCounts=variant_counts,Predictive=predictive,DevelopmentAmplitudeRanges=amplitude,
        PrimaryAdverseSelectionCostCellCounts=dict(cells),FollowupCandidates=followup,
        CostModel=r['CostModel'],ConditionalCostClass='CONDITIONAL_COST_MODEL',
        CountsAreOverlappingDiagnosticsNotIndependentTrades=True,CostCasesCanAdmitDifferentProposalBooks=True,
        FundedNetEur=None,Hard21Proven=False,IndependentConfirmation=False,OrdersSubmitted=0,
        ModelRerun=False,ClosedExactMsp1WithoutRetuning=True)


def main():
    data=(json.dumps(build(),sort_keys=True,indent=2)+'\n').encode()
    if sys.argv[1:]==['--write']:OUTPUT.write_bytes(data)
    else:assert OUTPUT.read_bytes()==data,'MSP1_AUDIT_NOT_REPRODUCIBLE'
    print('PASS MSP1 original receipt arithmetic, missingness and fixed selection decision; no model rerun')


if __name__=='__main__':main()

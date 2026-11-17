"""Read-only reconciliation of preserved SDP2 receipts; never rescores source."""
from pathlib import Path
from collections import Counter
from decimal import Decimal
from statistics import mean
import argparse, hashlib, json, math, zipfile


def sha(b):return hashlib.sha256(b).hexdigest()
def audit(archive):
    rawzip=Path(archive).read_bytes()
    with zipfile.ZipFile(archive) as z:raw=z.read('sdp2-original-public.json')
    p=json.loads(raw);money=json.loads(raw,parse_float=Decimal)
    assert p['executionRunId']=='44038569445' and p['spotwareIntegerPriceDivisor']==100000
    for key,file in [('protocolSha256','research/SDP2_SYSTEMATIC_ACTION_VALUE_PROTOCOL_20261117.md'),
                     ('codeSha256','research/sdp2_systematic_action_value.py'),
                     ('nativeCodeSha256','src/Mxm.Replay/Sdp2ActionValueResearch.cs')]:
        assert p[key]==sha(Path(file).read_bytes()),key
    assert not p['qualified'] and not p['independentConfirmation'] and p['orders']==0
    assert p['sourceBars']==836087 and len(p['universe'])==12
    assert p['nativeModelParity']=={'Cases':104,'MaximumAbsoluteError':0,'Passed':True}
    tables=[];zero=[]
    for h in (1,4):
        for w in range(27,53):
            m=[x for x in p['metrics'] if x['week']==w and x['horizonHours']==h]
            assert len(m)==5 and len({(x['featureKnown'],x['labelKnown'],x['futureUnknown']) for x in m})==1
        for name in ('FULL','NO_PEERS','NO_ACTIVITY','OWN_PRICE','PRIOR'):
            m=[x for x in p['metrics'] if x['horizonHours']==h and x['variant']==name]
            n=sum(x['labelKnown'] for x in m)
            def avg(key):return sum(mean(x[key][2:])*x['labelKnown'] for x in m)/n
            tables.append(dict(horizonHours=h,variant=name,labelKnown=n,futureUnknown=sum(x['futureUnknown'] for x in m),
                mse=avg('normalizedMse'),zeroMoveCostMse=avg('knownCostZeroMoveNormalizedMse'),
                brier=avg('brier'),eurMae=avg('eurMae'),actualPositiveRateLong=sum(x['positivePayoffRate'][2]*x['labelKnown'] for x in m)/n,
                actualPositiveRateShort=sum(x['positivePayoffRate'][3]*x['labelKnown'] for x in m)/n))
            if name=='FULL':
                diff=[mean(x['knownCostZeroMoveNormalizedMse'][2:])-mean(x['normalizedMse'][2:]) for x in m]
                zero.append(dict(horizonHours=h,positiveWeeks=sum(x>0 for x in diff),meanBenefit=mean(diff),
                    first13=mean(diff[:13]),last13=mean(diff[13:]),weekBenefits=diff))
    financial=[]
    for scenario in ('central','adverse'):
        for name,b in money['native_'+scenario].items():
            f=b['Final']
            assert sum((x['NetEur'] for x in b['Trades']),Decimal(0))==f['ClosedNetEur']
            assert sum(b['WeeklyCompletions'].values())==f['CompleteRoundTrips'] and len(b['WeeklyCompletions'])==26
            assert f['CashEur']==300+f['ClosedNetEur'] and f['OpenPositions']==0 and f['PendingIntents']==0
            assert not b['Qualified'] and not f['OrdersEnabled']
            financial.append(dict(scenario=scenario,variant=name,cashEur=str(f['CashEur']),netEur=str(f['ClosedNetEur']),
              completeRoundTrips=f['CompleteRoundTrips'],nativeCalls=b['NativeCalls'],maxSampledDd=str(f['MaximumSampledDrawdown']),
              hard21EveryWeek=b['Hard21EveryWeek'],eventChainSha256=f['EventChainHash']))
    counts=Counter();bounds=[];peerEquality=[]
    for m in p['models']:
        if m['variant']!='FULL':continue
        other=next(x for x in p['models'] if x['week']==m['week'] and x['variant']=='NO_PEERS')
        def executable(tree):
            return {**{k:tree[k] for k in ('left','right','feature','threshold')},
                    'leafValues':[v for i,v in enumerate(tree['value']) if tree['left'][i]<0]}
        peerEquality.append([executable(t) for t in m['trees']]==[executable(t) for t in other['trees']]
            and m['initial']==other['initial'] and m['cuts'][:39]==other['cuts'])
        upper=list(m['initial'])
        for t in m['trees']:
            for f in t['feature']:
                if f>=0:counts[p['featureColumns'][m['columns'][f]]]+=1
            leaves=[v for i,v in enumerate(t['value']) if t['left'][i]<0]
            for a in range(4):upper[a]+=.1*max(v[a] for v in leaves)
        bounds.append(dict(week=m['week'],upperBoundNormalizedAdverseLong=upper[2],upperBoundNormalizedAdverseShort=upper[3]))
    assert all(peerEquality) and not any(k.startswith('PEER_') for k in counts)
    assert all(x['upperBoundNormalizedAdverseLong']<0 and x['upperBoundNormalizedAdverseShort']<0 for x in bounds)
    denominator=[]
    for a,b in [(1,26),(27,52)]:
        census=[x for x in p['sourceCensus'] if a<=x['week']<=b]
        labels=[x for x in p['labelCensus'] if a<=x['week']<=b]
        scheduled=sum(x['count'] for x in census if x['state']=='scheduled')
        feature=sum(x['featureKnown'] for x in labels);known=sum(x['labelKnown'] for x in labels)
        denominator.append(dict(weeks=[a,b],scheduled=scheduled,featureKnown=feature,featureUnknown=scheduled-feature,labelKnown=known,futureUnknown=feature-known))
    return dict(kind='DIRECTOR_READ_ONLY_ORIGINAL_RECEIPT_RECONCILIATION_NOT_INDEPENDENT_AUDIT',
        verdict='SDP2_F1_EXPOSED_ACTION_VALUE_NO_VALUE_VS_KNOWN_COST_BASELINE_NO_PROMOTION',
        originalRun=44038569445,originalArtifact=14308483122,zipSha256=sha(rawzip),jsonSha256=sha(raw),
        protocolSha256=p['protocolSha256'],codeSha256=p['codeSha256'],nativeCodeSha256=p['nativeCodeSha256'],
        sourceBars=p['sourceBars'],universe=p['universe'],originalCostSamples=p['originalCostSamples'],
        originalSources=p['sourceAudit'],denominators=denominator,predictive=tables,fullVsKnownCostZeroMove=zero,
        fullTreeFeatureUse=dict(counts),fullAndNoPeerExecutableTreesIdenticalEveryWeek=all(peerEquality),
        fittedFullUpperBounds=bounds,financial=financial,matchedDenominatorsVerified=True,
        cashAndRoundTripIdentityVerified=True,closedModelsRerun=False,independentConfirmation=False,qualified=False)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('original_zip');parser.add_argument('output')
    args=parser.parse_args();out=audit(args.original_zip)
    Path(args.output).write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps({k:out[k] for k in ('verdict','zipSha256','jsonSha256','matchedDenominatorsVerified','cashAndRoundTripIdentityVerified')}))

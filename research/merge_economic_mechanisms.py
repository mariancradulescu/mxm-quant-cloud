"""Bind partitions and report all mechanisms, including losing and CASH controls."""
import json
from pathlib import Path
import sys
from .merge_eur_adaptive import collect
from .merge_eur_scenarios import exact_json,read,require

def merge(protocol,paths):
    result=collect(protocol,paths)
    originals=[read(p)['Summary']['Results'][0] for p in paths]
    for scenario in result['Summary']['Results']:
        children=[r for r in originals if r['SpreadMultiplier']==scenario['SpreadMultiplier']]
        require(all(r['PreventiveFunding']==children[0]['PreventiveFunding'] for r in children),'MECHANISM_FUNDING_PARTITIONS')
        scenario['PreventiveFunding']=children[0]['PreventiveFunding']
        scenario['MechanismEvidence']=[e for r in children for e in r['MechanismEvidence']]
        require({r['Id'] for r in scenario['MechanismEvidence']}=={t['Id'] for t in scenario['Trials']},'MECHANISM_EVIDENCE_COMPLETENESS')
    return result

def comparison(report):
    rows=[];pairs=[]
    for s in report['Summary']['Results']:
        by={t['Id']:t['Result'] for t in s['Trials']}
        for t in s['Trials']:
            r=t['Result'];net=r['ClosedNetEur']
            rows.append(dict(Stress=s['SpreadMultiplier'],Id=t['Id'],Closed=r['Closed'],GrossEur=r['ClosedGrossEur'],
                NetEur=net,TerminalNetEur=r['AllTerminalNetEur'],SampledDrawdown=r['SampledDrawdown'],
                UnknownEquityClocks=r['UnknownEquityClocks'],UnknownFundingWindows=r['UnknownFundingWindows'],
                Hard21=r['Hard21AllFullRegisteredWeeks'],PositiveWeeks=sum(w['NetEur'] is not None and w['NetEur']>0 for w in r['Weeks']),
                EligibleWeeks=len(r['Weeks']),OpenPositions=r['OpenPositions'],PendingIntents=r['PendingIntents']))
            if t['Id'].endswith('__TRANSITION_VALUE'):
                base=t['Id'].replace('__TRANSITION_VALUE','__BRACKET');a=by[base]
                pairs.append(dict(Stress=s['SpreadMultiplier'],Trial=t['Id'],Control=base,
                    GrossDifferenceEur=r['ClosedGrossEur']-a['ClosedGrossEur'],
                    NetDifferenceEur=net-a['ClosedNetEur'] if net is not None and a['ClosedNetEur'] is not None else None,
                    TerminalBothFlat=r['OpenPositions']==a['OpenPositions']==r['PendingIntents']==a['PendingIntents']==0,
                    CausalManagementAblation=True))
    return dict(Study=report['Summary']['Study'],Results=rows,ManagementComparisons=pairs,
        EconomicPromotionCertified=False,IndependentConfirmationMonths=0,ContinuousDrawdownCertified=False,
        Selection='ALL_REGISTERED_TRIALS_REPORTED_NO_EX_POST_WINNER_CERTIFICATION',Orders=0,CloudActivated=False)

if __name__=='__main__':
    root=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir()
    protocols=sorted(root.glob('*/materialized-protocol.json'));require(bool(protocols),'MECHANISM_PARTITIONS_MISSING')
    for p in protocols:
        require(p.read_bytes()==protocols[0].read_bytes(),'MECHANISM_PROTOCOL_BYTES')
        require((p.parent/'mechanism-source.json').read_bytes()==(protocols[0].parent/'mechanism-source.json').read_bytes(),'MECHANISM_SOURCE_BYTES')
    paths=sorted(root.glob('*/scenario-*.json'));result=merge(protocols[0],paths)
    (out/'economic.json').write_text(exact_json(result)+'\n')
    (out/'comparison.json').write_text(exact_json(comparison(result))+'\n')
    (out/'materialized-protocol.json').write_bytes(protocols[0].read_bytes())
    (out/'mechanism-source.json').write_bytes((protocols[0].parent/'mechanism-source.json').read_bytes())

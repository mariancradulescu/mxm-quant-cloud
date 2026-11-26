"""New cost-context, capital headroom, geometry and management comparisons.
No original policies rerun. Reuse exact normalized source and verified
financial prefix registry from the separately reconciled frozen study.
"""
import argparse,os,subprocess,time
from pathlib import Path
from decimal import Decimal
from . import owner_lifecycle_estimation as parent
from .owner_eur_recent_archive import download_archive
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import seal_files,sha
from .custody_new import derive_recipient
from .decode import need
from . import source_history_universe as src

STUDY='MONETARY_COST_CONTEXT_GEOMETRY_1'
REGISTRY=Path('research/cost_context_geometry_1.json')
TARGETS={('GOOG.US-24','BID',1795644000000),('AAPL.US','BID',1793743200000)}|{
    ('EURUSD',side,at) for side in ('BID','ASK') for at in (1794088800000,1794175200000)}

def write(path,value):Path(path).write_text(exact_json(value)+'\n')

def variants():
    base=next(v['Profile'] for v in parent.variants() if v['Id']=='TRANSFER_SUPPORT_SENSITIVITY')
    base=dict(base,ReserveMarginForStopRisk=True)
    cost=dict(base,LifecycleEstimator='CENTERED_COST_CONTEXT')
    rows=[
        ('STOP_ADJUSTED_BASE',base),
        ('COST_CONTEXT_H1',cost),
        ('COST_CONTEXT_TARGET3',dict(cost,DistributionTargetRanges=3)),
        ('COST_CONTEXT_STRUCTURE',dict(cost,DistributionTargetRanges=Decimal('2.5'),
            AnchorEconomicGeometryToClosedStructure=True,EconomicStructureLookbackBars=6)),
        ('COST_CONTEXT_STRUCTURE_CONFIRM',dict(cost,DistributionTargetRanges=Decimal('2.5'),
            AnchorEconomicGeometryToClosedStructure=True,EconomicStructureLookbackBars=6,
            ConfirmEconomicEntryOnM5=True,Pav1CompetitiveForecast='CORROBORATED')),
        ('COST_CONTEXT_CAPTURE',dict(cost,DistributionTargetRanges=Decimal('2.5'),
            EconomicManagement='CAPTURE_VALUE',EconomicManagementTimeframe='M15')),
        ('COST_CONTEXT_REDUCE',dict(cost,DistributionTargetRanges=Decimal('2.5'),
            EconomicManagement='MONETARY_REDUCE'))]
    return [dict(Id=id,UniverseCount=29,Profile=profile) for id,profile in rows]

def apply_registry(source,registry):
    need(registry['SourceSha256']==parent.SOURCE and registry['Study']=='LIFECYCLE_FUNDING_RECOVERY_1'
         and registry['Orders']==0 and not registry['CloudActivated'],'COST_CONTEXT_PREFIX_PARENT')
    rows=registry['Rows'];seen=set();filled=0;retained=0;unresolved=0
    tapes={t['Name']:t for t in source['Tapes']}
    for row in rows:
        t=row['Target'];key=(t['Symbol'],t['Side'],t['At']);w=row['Witness']
        need(key in TARGETS and key not in seen,'COST_CONTEXT_PREFIX_SCOPE');seen.add(key)
        if w['Status']!='AUTHENTIC_LATEST_PREFIX':unresolved+=1;continue
        symbol,side,at=key
        need(w['SearchThrough']==at and w['SearchFrom']==at-345600000 and
             0<w['At']<=at and at-w['At']<=345600000 and Decimal(w['Price'])>0 and
             w['PrefixNewestFirst'] and w['LeadingTimestampComplete'],'COST_CONTEXT_PREFIX_VALID')
        quotes=tapes[symbol]['FundingQuotes'];matching=[q for q in quotes if q['At']==at]
        need(len(matching)<=1,'COST_CONTEXT_DUPLICATE_FUNDING')
        if matching:q=matching[0]
        else:
            q=dict(At=at,RequestedCoverage=False,BidAt=None,AskAt=None,Bid=None,Ask=None);quotes.append(q)
        name='Bid' if side=='BID' else 'Ask';field='Latest'+name+'Prefix'
        if q.get(field) is not None:
            need(q[field]==w,'COST_CONTEXT_PREFIX_CONFLICT');retained+=1;continue
        stamp=q.get(name+'At');value=q.get(name)
        valid=q.get('RequestedCoverage',False) and value is not None and Decimal(str(value))>0 and stamp is not None and 0<stamp<=at and at-stamp<=7200000
        if valid:
            need(stamp!=w['At'] or Decimal(str(value))==Decimal(w['Price']),'COST_CONTEXT_SAME_TIMESTAMP_CONFLICT')
            retained+=1;continue
        q[field]=w;filled+=1
        quotes.sort(key=lambda x:x['At'])
    need(seen==TARGETS,'COST_CONTEXT_PREFIX_COMPLETE_SCOPE')
    return dict(Filled=filled,Retained=retained,Unresolved=unresolved)

def prepare(work):
    start=time.monotonic()
    p=read(REGISTRY)
    need(p['Study']==STUDY and p['OriginalSourceSha256']==parent.SOURCE and
         p['Orders']==0 and not p['CloudActivated'],'COST_CONTEXT_REGISTRATION')
    parent.restore(work)
    original=Path('cost-context-funding-parent')
    download_archive(p['FundingArtifact'],p['FundingRun'],p['FundingArchiveSha256'],original)
    witness=original/'verified-prefix-registry.json';registry=read(witness)
    need(sha(witness)==p['FundingRegistrySha256'] and registry['NewRunId']==str(p['FundingRun']),
         'COST_CONTEXT_REGISTRY_IDENTITY')
    source=read(work/'source.json');plan=read(work/'pav-market-protocol.json')
    overlay=apply_registry(source,registry)
    plan.update(Study=STUDY,Variants=variants())
    proof=dict(ParentSource=parent.SOURCE,ParentReceipt=read(Path('estimator-report/source-receipt.json')),
        Registry=p,Overlay=overlay,SourceBrokerRequests=0,OriginalPolicyReruns=0)
    registration=src.digest(exact_json(plan).encode());evidence=src.digest(exact_json(proof).encode())
    source.update(ProtocolSha256=registration,EvidenceManifestSha256=evidence,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=registration,EvidenceManifestSha256=evidence)
    write(work/'cost-source.json',source);write(work/'cost-plan.json',plan)
    report=Path('cost-context-report');report.mkdir()
    (report/'registered-plan.json').write_bytes((work/'cost-plan.json').read_bytes())
    write(report/'source-receipt.json',dict(Study=STUDY,SourceSha256=sha(work/'cost-source.json'),
        ProtocolSha256=sha(work/'cost-plan.json'),Proof=proof,
        PreparationSeconds=round(time.monotonic()-start,3),Orders=0,CloudActivated=False))

def evaluate(work):
    report=Path('cost-context-report');receipt=read(report/'source-receipt.json')
    need(sha(work/'cost-source.json')==receipt['SourceSha256'] and sha(work/'cost-plan.json')==receipt['ProtocolSha256'],
         'COST_CONTEXT_SOURCE_BINDING')
    results=[];start=time.monotonic()
    for i,stress in enumerate(STRESSES):
        out=Path('cost-context-partitions')/('S'+str(i));out.mkdir(parents=True)
        subprocess.run(['dotnet',REPLAY,'--owner-lifecycle-estimation',str(work/'cost-plan.json'),
                        str(work/'cost-source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==8 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256'] and
             result['Orders']==0 and not result['CloudActivated'],'COST_CONTEXT_RESULT_BINDING')
        results.append(result);(report/('S'+str(i)+'.json')).write_bytes((out/'result.json').read_bytes())
        print('COST_CONTEXT_SCENARIO_COMPLETE',i,flush=True)
    rows=[r for result in results for r in result['Selection']]
    write(report/'summary.json',dict(Study=STUDY,SharedPortfolioEvaluations=24,
        Selection=parent.corrected_selection(rows,Decimal('2.83')),SelectionMultiplicity=21,
        SelectionPenalty=Decimal('2.83'),EvaluationSeconds=round(time.monotonic()-start,3),
        SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve(work):
    root=Path('cost-context-partitions');files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:return
    receipt=read(Path('cost-context-report/source-receipt.json'))
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(p,str(p.relative_to(root))) for p in files],'cost-context-sealed-books',public,
        os.environ['GITHUB_RUN_ID'],STUDY,receipt['SourceSha256'],
        complete=Path('cost-context-report/summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','prepare','evaluate','conserve'))
    p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':
        v=variants();need(len(v)==7 and len({x['Id'] for x in v})==7 and
            all(x['Profile']['ReserveMarginForStopRisk'] for x in v),'COST_CONTEXT_VARIANTS')
        print('COST_CONTEXT_VARIANTS_REGISTERED',len(v))
    elif a.stage=='prepare':prepare(a.work)
    elif a.stage=='evaluate':evaluate(a.work)
    else:conserve(a.work)
if __name__=='__main__':main()

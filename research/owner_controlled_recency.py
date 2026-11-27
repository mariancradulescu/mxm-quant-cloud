"""Distinct cross-context economic development; original policies are never replayed."""
import argparse,os,subprocess
from decimal import Decimal
from pathlib import Path
from . import owner_boundary_lifecycle as boundary
from . import owner_native_funding_recovery_2 as recovery
from . import owner_cost_context_geometry as geometry
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_pav1_market_time import restore_checkpoint
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need
from . import source_history_universe as src

STUDY='MONETARY_CONTROLLED_RECENCY_1'
REGISTRY=Path('research/controlled_recency_1.json')
REPORT=Path('controlled-recency-report')

def write(p,value):Path(p).write_text(exact_json(value)+'\n')

def variants(n):
    base=dict(geometry.variants()[0]['Profile'],LifecycleEstimator='CENTERED_COST_CONTEXT',
        CaptureLifecycleRecencyEvidence=True,EconomicManagementTimeframe='M15',EconomicGeometryTimeframe='M15',
        EconomicManagement='CAPTURE_VALUE',DistributionTargetRanges=Decimal('2.5'),
        AnchorEconomicGeometryToClosedStructure=True,EconomicStructureLookbackBars=6)
    return [dict(Id=f'MEMORY_{d}',UniverseCount=n,Profile=dict(base,LifecycleRecencyHalfLifeDays=d)) for d in (0,14,28)]

def check():
    p=read(REGISTRY)
    need(p['Study']==STUDY and p['Scopes']==['earlier','recent'] and p['VariantsPerScope']==3
        and p['Evaluations']==24 and p['FundingHorizonMs']==1800000 and p['SelectionMultiplicity']==18
        and p['Orders']==0 and not p['CloudActivated'],'CONTROLLED_RECENCY_REGISTRATION')
    for n in (7,29):
        rows=variants(n);profiles=[dict(x['Profile']) for x in rows]
        need([x.pop('LifecycleRecencyHalfLifeDays') for x in profiles]==[0,14,28]
            and profiles[0]==profiles[1]==profiles[2] and profiles[0]['ReserveMarginForStopRisk'],
            'CONTROLLED_RECENCY_PARITY')
    return p

def prepare(work,scope):
    p=check()
    if scope=='recent':
        boundary.prepare(work) # evidence restoration only; no original policy execution
        source=read(work/'boundary-source.json');plan=read(work/'boundary-plan.json')
        parent=read(boundary.REPORT/'source-receipt.json')
        parent_hash=sha(work/'boundary-source.json')
    else:
        pre=recovery.pre
        verified_download(*pre.EARLIER,Path('earlier-closed-original'))
        parent=read(Path('earlier-closed-original/summary.json'))
        verified_download(*pre.CACHE,Path('earlier-source-cipher'))
        restore_checkpoint(Path('earlier-source-cipher'),work,os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),
            str(pre.CACHE[1]),parent['SourceSha256'],source_only=True)
        need(sha(work/'source.json')==parent['SourceSha256'] and
             sha(work/'pav-market-protocol.json')==parent['ProtocolSha256'],'NET_HORIZON_EARLIER_PARENT')
        parent_hash=sha(work/'source.json')
        source=read(work/'source.json');plan=read(work/'pav-market-protocol.json')
        reg=read(boundary.REGISTRY)
        verified_download(reg['FundingArtifact'],reg['FundingRun'],reg['FundingArchiveSha256'],Path('controlled-recency-funding'))
        witness=Path('controlled-recency-funding/verified-prefix-registry.json')
        need(sha(witness)==reg['FundingRegistrySha256'],'NET_HORIZON_EARLIER_FUNDING')
        overlay=recovery.apply_recovered_registry(source,read(witness),parent_hash)
        parent=dict(OriginalReceipt=parent,FundingOverlay=overlay,FundingRegistrySha256=sha(witness))
    n=7 if scope=='earlier' else 29
    need(len(source['Markets'])==n,'NET_HORIZON_MARKET_SCOPE')
    plan.update(Study=STUDY,Variants=variants(n))
    proof=dict(ParentSourceSha256=parent_hash,Parent=parent,Scope=scope,FundingForecastHorizonMs=p['FundingHorizonMs'],
        RemainingPreventive=recovery.pre.preflight(source,recovery.safe_mark),OriginalPolicyReruns=0,SourceBrokerRequests=0)
    protocol=src.digest(exact_json(plan).encode());evidence=src.digest(exact_json(proof).encode())
    source.update(ProtocolSha256=protocol,EvidenceManifestSha256=evidence,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=evidence)
    write(work/'net-source.json',source);write(work/'net-plan.json',plan)
    REPORT.mkdir()
    write(REPORT/'registered-plan.json',plan)
    write(REPORT/'source-receipt.json',dict(Study=STUDY,Scope=scope,SourceSha256=sha(work/'net-source.json'),
        ProtocolSha256=sha(work/'net-plan.json'),Proof=proof,Orders=0,CloudActivated=False))

def evaluate(work):
    receipt=read(REPORT/'source-receipt.json')
    need(sha(work/'net-source.json')==receipt['SourceSha256'] and sha(work/'net-plan.json')==receipt['ProtocolSha256'],
        'NET_HORIZON_SOURCE_BINDING')
    results=[]
    for i,stress in enumerate(STRESSES):
        out=Path('controlled-recency-partitions')/('S'+str(i));out.mkdir(parents=True)
        subprocess.run(['dotnet',REPLAY,'--owner-controlled-recency',str(work/'net-plan.json'),
            str(work/'net-source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==4 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256']
             and result['Orders']==0 and not result['CloudActivated'],'NET_HORIZON_RESULT_BINDING')
        results.append(result)
        for name in ('result.json','holding-valuation-gaps.json','held-mark-evidence-counts.json'):
            (REPORT/f'S{i}-{name}').write_bytes((out/name).read_bytes())
        print('NET_HORIZON_SCENARIO_COMPLETE',receipt['Scope'],i,flush=True)
    rows=[r for result in results for r in result['Selection']]
    write(REPORT/'summary.json',dict(Study=STUDY,Scope=receipt['Scope'],SharedPortfolioEvaluations=12,
        Selection=boundary.parent.corrected_selection(rows,Decimal('3.0')),SelectionMultiplicity=18,
        SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    root=Path('controlled-recency-partitions');files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:return
    receipt=read(REPORT/'source-receipt.json')
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(p,str(p.relative_to(root))) for p in files],'controlled-recency-sealed-books',public,
        os.environ['GITHUB_RUN_ID'],STUDY,receipt['SourceSha256'],complete=(REPORT/'summary.json').exists(),
        protocol_sha=receipt['ProtocolSha256'])

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','prepare','evaluate','conserve'))
    p.add_argument('--scope',choices=('earlier','recent'));p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':check()
    elif a.stage=='prepare':
        need(a.scope is not None,'NET_HORIZON_SCOPE');prepare(a.work,a.scope)
    elif a.stage=='evaluate':evaluate(a.work)
    else:conserve()
if __name__=='__main__':main()

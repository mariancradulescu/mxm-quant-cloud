"""Registered boundary management ablations on one authentically recovered source.
All portfolios use the same contracts, carry horizon, capital and protection.
Exposed development only; no closed original policy is executed.
"""
import argparse,os,subprocess,time
from decimal import Decimal
from pathlib import Path
from . import owner_lifecycle_estimation as parent
from . import owner_cost_context_geometry as geometry
from . import owner_native_funding_recovery_2 as recovery
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import seal_files,sha
from .custody_new import derive_recipient
from .decode import need
from . import source_history_universe as src

STUDY='MONETARY_BOUNDARY_LIFECYCLE_1'
REGISTRY=Path('research/boundary_lifecycle_1.json')
REPORT=Path('boundary-report')

def write(path,value):Path(path).write_text(exact_json(value)+'\n')

def variants():
    base=dict(geometry.variants()[0]['Profile'],EconomicManagementTimeframe='M5')
    boundary=dict(base,EconomicManagement='BOUNDARY_VALUE',BoundaryMinimumSamples=8,BoundaryMinimumDays=1)
    rows=[
        ('CONTROL_TRANSITION',base),
        ('CONTROL_MONETARY_REDUCE',dict(base,EconomicManagement='MONETARY_REDUCE')),
        ('CONTROL_TARGET25_DIRECT_PAV1',dict(base,DistributionTargetRanges=Decimal('2.5'),Pav1CompetitiveForecast='DIRECT')),
        ('CONTROL_TARGET25_DIRECT_REDUCE',dict(base,DistributionTargetRanges=Decimal('2.5'),
            Pav1CompetitiveForecast='DIRECT',EconomicManagement='MONETARY_REDUCE')),
        ('BOUNDARY_M5_SUPPORT8',boundary),
        ('BOUNDARY_M5_SUPPORT4',dict(boundary,BoundaryMinimumSamples=4)),
        ('BOUNDARY_M5_SUPPORT16',dict(boundary,BoundaryMinimumSamples=16)),
        ('BOUNDARY_M15_SUPPORT8',dict(boundary,EconomicManagementTimeframe='M15')),
        ('BOUNDARY_UNSCALED',dict(boundary,UseUnscaledBoundaryPaths=True)),
        ('BOUNDARY_ENTRY_ABLATION',dict(boundary,RequireEconomicBoundaryEdge=True)),
        ('BOUNDARY_REDUCE',dict(boundary,EconomicManagement='BOUNDARY_VALUE_REDUCE')),
        ('BOUNDARY_STOP_TARGET',dict(boundary,EconomicStopRanges=1,DistributionTargetRanges=3)),
        ('BOUNDARY_MINIMUM_VOLUME',dict(boundary,MinimumContractVolumeOnly=True,OptimizeEconomicOpportunityVolume=False))]
    return [dict(Id=name,UniverseCount=29,Profile=profile) for name,profile in rows]

def prepare(work):
    started=time.monotonic();p=read(REGISTRY)
    need(p['Study']==STUDY and p['OriginalSourceSha256']==parent.SOURCE and p['RegisteredVariants']==13
         and p['RegisteredEvaluations']==42 and p['Orders']==0 and not p['CloudActivated'],
         'BOUNDARY_REGISTRATION')
    parent.restore(work)
    source=read(work/'source.json');plan=read(work/'pav-market-protocol.json')
    need(sha(work/'source.json')==parent.SOURCE,'BOUNDARY_BASE_SOURCE')
    old=read(geometry.REGISTRY);older=Path('boundary-earlier-funding')
    verified_download(old['FundingArtifact'],old['FundingRun'],old['FundingArchiveSha256'],older)
    older_file=older/'verified-prefix-registry.json'
    need(sha(older_file)==old['FundingRegistrySha256'],'BOUNDARY_LEGACY_REGISTRY')
    old_overlay=geometry.apply_registry(source,read(older_file))
    new=Path('boundary-preventive-funding')
    verified_download(p['FundingArtifact'],p['FundingRun'],p['FundingArchiveSha256'],new)
    new_file=new/'verified-prefix-registry.json'
    need(sha(new_file)==p['FundingRegistrySha256'],'BOUNDARY_PREVENTIVE_REGISTRY')
    registry=read(new_file)
    need(registry['RunId']==str(p['FundingRun']),'BOUNDARY_FUNDING_RUN')
    overlay=recovery.apply_recovered_registry(source,registry,parent.SOURCE)
    preventive=recovery.pre.preflight(source,recovery.safe_mark)
    plan.update(Study=STUDY,Variants=variants())
    proof=dict(OriginalSourceSha256=parent.SOURCE,ParentReceipt=read(Path('estimator-report/source-receipt.json')),
        Registry=p,LegacyOverlay=old_overlay,PreventiveOverlay=overlay,RemainingPreventive=preventive,
        FundingForecastHorizonMs=900000,SourceBrokerRequests=0,OriginalPolicyReruns=0)
    protocol=src.digest(exact_json(plan).encode());evidence=src.digest(exact_json(proof).encode())
    source.update(ProtocolSha256=protocol,EvidenceManifestSha256=evidence,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=evidence)
    write(work/'boundary-source.json',source);write(work/'boundary-plan.json',plan)
    REPORT.mkdir();write(REPORT/'registered-plan.json',plan)
    write(work/'preventive-remaining.json',preventive)
    subprocess.run(['dotnet',REPLAY,'--owner-funding-coverage',str(work/'boundary-source.json'),
        str(work/'verified-protection'),str(work/'preventive-remaining.json'),str(REPORT/'native-funding-coverage.json')],check=True)
    write(REPORT/'source-receipt.json',dict(Study=STUDY,SourceSha256=sha(work/'boundary-source.json'),
        ProtocolSha256=sha(work/'boundary-plan.json'),Proof=proof,PreparationSeconds=round(time.monotonic()-started,3),
        NativeFundingCoverageSha256=sha(REPORT/'native-funding-coverage.json'),
        Orders=0,CloudActivated=False))

def evaluate(work):
    receipt=read(REPORT/'source-receipt.json')
    need(sha(work/'boundary-source.json')==receipt['SourceSha256'] and
         sha(work/'boundary-plan.json')==receipt['ProtocolSha256'],'BOUNDARY_SOURCE_BINDING')
    started=time.monotonic();results=[]
    for i,stress in enumerate(STRESSES):
        out=Path('boundary-partitions')/('S'+str(i));out.mkdir(parents=True)
        subprocess.run(['dotnet',REPLAY,'--owner-boundary-lifecycle',str(work/'boundary-plan.json'),
            str(work/'boundary-source.json'),str(out),str(work/'verified-protection'),stress],check=True)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==14 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256']
             and result['Orders']==0 and not result['CloudActivated'],'BOUNDARY_RESULT_BINDING')
        results.append(result);(REPORT/f'S{i}.json').write_bytes((out/'result.json').read_bytes())
        (REPORT/f'S{i}-forecasts.json').write_bytes((out/'boundary-forecast-diagnostics.json').read_bytes())
        print('BOUNDARY_SCENARIO_COMPLETE',i,flush=True)
    rows=[r for result in results for r in result['Selection']]
    write(REPORT/'summary.json',dict(Study=STUDY,SharedPortfolioEvaluations=42,
        Selection=parent.corrected_selection(rows,Decimal('3.03')),SelectionMultiplicity=39,
        SelectionPenalty=Decimal('3.03'),SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
        EvaluationSeconds=round(time.monotonic()-started,3),Orders=0,CloudActivated=False,
        DevelopmentOnly=True,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))

def conserve():
    root=Path('boundary-partitions');files=sorted(root.glob('*/checkpoints/**/*.json'))
    if not files:return
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    receipt=read(REPORT/'source-receipt.json')
    seal_files([(p,str(p.relative_to(root))) for p in files],'boundary-sealed-books',public,
        os.environ['GITHUB_RUN_ID'],STUDY,receipt['SourceSha256'],complete=(REPORT/'summary.json').exists(),
        protocol_sha=receipt['ProtocolSha256'])

def main():
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('check','prepare','evaluate','conserve'))
    p.add_argument('--work',type=Path);a=p.parse_args()
    if a.stage=='check':
        rows=variants();need(len(rows)==13 and len({r['Id'] for r in rows})==13,'BOUNDARY_VARIANTS')
        need(all(r['Profile']['ReserveMarginForStopRisk'] and r['Profile']['CompeteEconomicFamilies']
             for r in rows),'BOUNDARY_COMMON_PROTECTIONS')
        print('BOUNDARY_REGISTERED',len(rows),'VARIANTS; 42 COMMON BOOKS; ZERO ORDERS')
    elif a.stage=='prepare':prepare(a.work)
    elif a.stage=='evaluate':evaluate(a.work)
    else:conserve()

if __name__=='__main__':main()

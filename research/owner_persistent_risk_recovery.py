"""New exposed risk/geometry research; preserve completed factorial and all original books."""
import argparse,gc,hashlib,json,os,shutil,subprocess,time
from decimal import Decimal
from pathlib import Path
from . import owner_controlled_recency as parent
from . import owner_path_distribution_economic as original
from . import owner_lifecycle_estimation as selection
from .owner_management_factorial import restore_registry,write
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need
STUDY='MONETARY_PERSISTENT_RISK_RECOVERY_1'
REGISTRATION=Path('research/persistent_risk_recovery_1.json')
REPORT=Path('persistent-risk-recovery-report')
PARTS=Path('persistent-risk-recovery-parts')

def variants(n):
    base=dict(original.variants(n)[0]['Profile'],UseWitnessedPortfolioDrawdownGuard=True,PersistWitnessedPortfolioCloseUntilExecutable=True)
    rows=[
      ('CENTERED_GUARD','CENTERED_COST_CONTEXT',False,None,'2.5'),
      ('CENTERED_MANAGEMENT_GUARD','CENTERED_COST_CONTEXT',True,None,'2.5'),
      ('DISTRIBUTION_GUARD','DISTRIBUTION_CONTEXT',False,None,'2.5'),
      ('DISTRIBUTION_MANAGEMENT_GUARD','DISTRIBUTION_CONTEXT',True,None,'2.5'),
      ('PAV1_DIRECT_GUARD','CENTERED_COST_CONTEXT',False,'DIRECT','2.5'),
      ('PAV1_DIRECT_MANAGEMENT_GUARD','CENTERED_COST_CONTEXT',True,'DIRECT','2.5'),
      ('DISTRIBUTION_MANAGEMENT_TARGET_15','DISTRIBUTION_CONTEXT',True,None,'1.5'),
      ('PAV1_DIRECT_MANAGEMENT_TARGET_15','CENTERED_COST_CONTEXT',True,'DIRECT','1.5')]
    return [dict(Id=name,UniverseCount=n,Profile=dict(base,LifecycleEstimator=estimator,
        RequirePathTailCapacity=False,UsePathDistributionManagement=management,ReservePreventiveDrawdownHeadroom=management,
        Pav1CompetitiveForecast=pav,DistributionTargetRanges=Decimal(target)))
        for name,estimator,management,pav,target in rows]

def check():
    p=read(REGISTRATION)
    need(p['Study']==STUDY and p['Scopes']==['earlier','recent'] and
         p['Models']==[v['Id'] for v in variants(29)] and p['CommonBookEvaluations']==54 and
         p['SelectionMultiplicity']==48 and Decimal(p['SelectionPenalty'])==Decimal('3.2') and
         p['SourceBrokerRequests']==p['OriginalPoliciesReplayed']==p['Orders']==0 and
         not p['CloudActivated'] and not p['IndependentConfirmationCertified'],'WITNESSED_RISK_REGISTRATION')
    return p

def prepare(work,scope):
    started=time.monotonic();p=check();parent.prepare(work,scope)
    source=read(work/'net-source.json');plan=read(work/'net-plan.json')
    parent_receipt=read(parent.REPORT/'source-receipt.json')
    registry=restore_registry(work,p);registry_sha=sha(registry)
    plan.update(Study=STUDY,Variants=variants(len(source['Markets'])))
    proof=dict(Parent=parent_receipt,Registration=p,RegistrySha256=registry_sha,
        SourceBrokerRequests=0,OriginalPoliciesReplayed=0,FundingHorizonMs=3600000)
    protocol=hashlib.sha256(exact_json(plan).encode()).hexdigest()
    evidence=hashlib.sha256(exact_json(proof).encode()).hexdigest()
    source.update(ProtocolSha256=protocol,EvidenceManifestSha256=evidence,EngineRevision=os.environ['GITHUB_SHA'])
    plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=evidence)
    source_path=work/'risk-geometry-source.json';plan_path=work/'risk-geometry-plan.json'
    write(source_path,source);write(plan_path,plan);REPORT.mkdir()
    del source;gc.collect()
    write(REPORT/'registered-plan.json',plan)
    write(REPORT/'source-receipt.json',dict(Study=STUDY,Scope=scope,SourceSha256=sha(source_path),
        ProtocolSha256=sha(plan_path),RegistrySha256=registry_sha,Proof=proof,
        PreparationSeconds=round(time.monotonic()-started,3),Orders=0,CloudActivated=False))
    return source_path,plan_path,registry

def run_native(work,source,plan,registry,out,stress,compact,log_path):
    env=dict(os.environ,MXM_ECONOMIC_BOUNDED_NEIGHBORS='1',MXM_ECONOMIC_PAIRED_DISTRIBUTION='1',
             MXM_ECONOMIC_PROFILE='1',MXM_ECONOMIC_COMPACT_REGISTRY='1',MXM_ECONOMIC_COMPACT_PATH='1',MXM_ECONOMIC_STREAM_REGISTRY=compact)
    env.pop('MXM_FACTORIAL_STOP_AFTER_PHASE',None);env.pop('MXM_FACTORIAL_RESUME_FROM',None)
    started=time.monotonic()
    with log_path.open('w') as log:
        process=subprocess.Popen(['dotnet',REPLAY,'--owner-path-distribution',str(plan),str(source),str(out),
            str(work/'verified-protection'),stress,str(registry)],env=env,stdout=subprocess.PIPE,text=True)
        for line in process.stdout:
            if line.startswith(('MXM_ECONOMIC_PROGRESS ','MXM_ECONOMIC_PROFILE ','COMPETITIVE_FAMILIES_')):
                print(line.rstrip(),flush=True);log.write(line);log.flush()
        need(process.wait()==0,'WITNESSED_RISK_NATIVE_EXECUTION')
    return round(time.monotonic()-started,3)

def measure(log):
    lines=log.read_text().splitlines()
    progress=[json.loads(x.split(' ',1)[1]) for x in lines if x.startswith('MXM_ECONOMIC_PROGRESS ')]
    profile=[json.loads(x.split(' ',1)[1]) for x in lines if x.startswith('MXM_ECONOMIC_PROFILE ')]
    need(progress and profile,'RISK_GEOMETRY_PROFILE')
    return dict(PeakWorkingSetBytes=max(x['peakWorkingSetBytes'] for x in progress),Profile=profile[-1])

def evaluate(work,scope):
    source,plan,registry=prepare(work,scope);receipt=read(REPORT/'source-receipt.json')
    results=[];timings=[]
    for i,stress in enumerate(STRESSES):
        out=PARTS/f'S{i}';out.mkdir(parents=True)
        log=REPORT/f'S{i}-progress.log'
        seconds=run_native(work,source,plan,registry,out,stress,'1',log)
        if scope=='recent' and i==0:
            baseline=work/'technical-full-baseline';baseline.mkdir()
            baseline_log=REPORT/'full-baseline-progress.log'
            baseline_seconds=run_native(work,source,plan,registry,baseline,stress,'0',baseline_log)
            a,b=sha(baseline/'result.json'),sha(out/'result.json')
            ga,gb=sha(baseline/'holding-valuation-gaps.json'),sha(out/'holding-valuation-gaps.json')
            need(a==b and ga==gb,'WITNESSED_RISK_FULL_ENGINE_EXACT_PARITY')
            write(REPORT/'full-engine-benchmark.json',dict(Scope=scope,Scenario=i,Markets=29,Books=9,
                SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
                BaselineSeconds=baseline_seconds,OptimizedSeconds=seconds,
                Speedup=Decimal(str(baseline_seconds))/max(Decimal(str(seconds)),Decimal('.001')),
                Baseline=measure(baseline_log),Optimized=measure(log),
                ExactResultSha256=a,ExactGapsSha256=ga,ProfileEnabledBoth=True,
                OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))
            shutil.rmtree(baseline)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==9 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256'] and
             result['Orders']==0 and not result['CloudActivated'],'WITNESSED_RISK_NATIVE_RESULT')
        results.append(result);timings.append(seconds)
        for name in ('result.json','holding-valuation-gaps.json'):
            (REPORT/f'S{i}-{name}').write_bytes((out/name).read_bytes())
        print('WITNESSED_RISK_SCENARIO_COMPLETE',scope,i+1,3,seconds,flush=True)
    write(REPORT/'summary.json',dict(Study=STUDY,Scope=scope,CommonBookEvaluations=27,
        SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
        RegistrySha256=receipt['RegistrySha256'],ScenarioSeconds=timings,
        Selection=selection.corrected_selection([x for r in results for x in r['Selection']],Decimal('3.2')),
        SelectionMultiplicity=48,OriginalPoliciesReplayed=0,SourceBrokerRequests=0,Orders=0,
        CloudActivated=False,IndependentConfirmationCertified=False,EconomicPromotionCertified=False))
def conserve():
    files=sorted(PARTS.glob('*/checkpoints/**/*.json'))
    if not files:return
    receipt=read(REPORT/'source-receipt.json')
    public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
    seal_files([(p,str(p.relative_to(PARTS))) for p in files],'persistent-risk-recovery-sealed',public,
        os.environ['GITHUB_RUN_ID'],STUDY,receipt['SourceSha256'],
        complete=(REPORT/'summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])

def main():
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['check','evaluate','conserve'])
    parser.add_argument('--scope',choices=['earlier','recent']);parser.add_argument('--work',type=Path)
    args=parser.parse_args()
    if args.stage=='check':check()
    elif args.stage=='conserve':conserve()
    else:evaluate(args.work,args.scope)
if __name__=='__main__':main()

"""New exposed-development experiment; no original policy is replayed."""
import argparse,collections,gc,hashlib,os,subprocess,time
from decimal import Decimal
from pathlib import Path
from . import owner_controlled_recency as parent
from . import owner_path_distribution_economic as original
from . import owner_lifecycle_estimation as selection
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need

STUDY='MONETARY_MANAGEMENT_FACTORIAL_1'
REGISTRATION=Path('research/management_factorial_1.json')
REPORT=Path('management-factorial-report')
PARTS=Path('management-factorial-parts')

def write(path,value):Path(path).write_text(exact_json(value)+'\n')

def variants(n):
    base=original.variants(n)[0]['Profile']
    rows=[
      ('CENTERED_CONTROL','CENTERED_COST_CONTEXT',False,False,None),
      ('CENTERED_MANAGEMENT','CENTERED_COST_CONTEXT',False,True,None),
      ('DISTRIBUTION_CONTEXT','DISTRIBUTION_CONTEXT',False,False,None),
      ('DISTRIBUTION_MANAGEMENT','DISTRIBUTION_CONTEXT',False,True,None),
      ('DISTRIBUTION_TAIL','DISTRIBUTION_CONTEXT',True,False,None),
      ('DISTRIBUTION_TAIL_MANAGEMENT','DISTRIBUTION_CONTEXT',True,True,None),
      ('PAV1_DIRECT_CONTROL','CENTERED_COST_CONTEXT',False,False,'DIRECT'),
      ('PAV1_DIRECT_MANAGEMENT','CENTERED_COST_CONTEXT',False,True,'DIRECT')]
    return [dict(Id=name,UniverseCount=n,Profile=dict(base,LifecycleEstimator=estimator,
       RequirePathTailCapacity=tail,UsePathDistributionManagement=management,
       Pav1CompetitiveForecast=pav)) for name,estimator,tail,management,pav in rows]

def check():
    p=read(REGISTRATION)
    need(p['Study']==STUDY and p['Scopes']==['earlier','recent'] and
         p['Models']==[v['Id'] for v in variants(29)] and p['CommonBookEvaluations']==54 and
         p['SelectionMultiplicity']==48 and Decimal(p['SelectionPenalty'])==Decimal('3.2') and
         p['SourceBrokerRequests']==p['OriginalPoliciesReplayed']==p['Orders']==0 and
         not p['CloudActivated'] and not p['IndependentConfirmationCertified'],'FACTORIAL_REGISTRATION')
    return p

def restore_registry(work,p):
    bundle=read(Path(p['RegistryBundle']))
    need(bundle['CombinedRows']==p['RegistryRows'] and bundle['Orders']==0 and
         not bundle['CloudActivated'],'FACTORIAL_BUNDLE_BINDING')
    target=work/'factorial-registry.json';count=0
    with target.open('w') as output:
        output.write('{"Rows":[')
        for i,spec in enumerate([bundle['Base']]+bundle['Deltas']):
            folder=work/f'registry-part-{i}'
            verified_download(spec['Artifact'],spec['Run'],spec['ArchiveSha256'],folder)
            path=folder/spec['File']
            if 'FileSha256' in spec:need(sha(path)==spec['FileSha256'],'FACTORIAL_REGISTRY_FILE_SHA')
            raw=read(path)
            need(raw['Orders']==0 and not raw['CloudActivated'] and len(raw['Rows'])==spec['Rows'],
                 'FACTORIAL_REGISTRY_PART')
            for row in raw['Rows']:
                if count:output.write(',')
                output.write(exact_json(row));count+=1
            del raw;gc.collect()
        output.write(']}\n')
    need(count==p['RegistryRows'],'FACTORIAL_REGISTRY_COUNT')
    print('FACTORIAL_REGISTRY_COMPLETE',count,flush=True)
    return target

def terminal_diagnosis(work,scope,p,source,tape,registry):
    receipt=read(Path(p['OriginalEconomicReceipt']))
    bound=next(x for x in receipt['Scopes'] if x['Summary']['Scope']==scope)
    folder=work/'original-economic-public'
    verified_download(bound['Artifact'],bound['Run'],bound['ArchiveSha256'],folder)
    positions=[];demands=collections.defaultdict(set)
    for i in range(3):
        report=read(folder/f'S{i}-result.json')
        need(report['SourceSha256']==bound['Summary']['SourceSha256'] and
             report['ProtocolSha256']==bound['Summary']['ProtocolSha256'] and
             report['Orders']==0 and not report['CloudActivated'],'FACTORIAL_ORIGINAL_REPORT_BINDING')
        for row in bound['Rows']:
            if row['Stress']!=i or row['TerminalNet'] is not None:continue
            book=next(b for b in report['CommonBooks'] if b['Id']==row['Id'])
            details=book['Details'];point=details['EquityPath'][-1]
            closed={e['PositionId'] for e in details['Episodes'] if e['CloseAt']<=point['At']}
            active=[a for a in details['Admissions'] if a['FillAt'] is not None and
                    a['FillAt']<=point['At'] and a['PositionId'] not in closed]
            need(len(active)==row['Open']==point['Held'],'FACTORIAL_TERMINAL_HELD_PARITY')
            for a in active:
                positions.append(dict(Book=row['Id'],Stress=i,PositionId=a['PositionId'],Symbol=a['Symbol'],
                     Side=a['Side'],At=point['At'],OriginalCashEur=point['CashEur']))
                demands[a['Symbol'],point['At']].add(row['Id'])
    need(len(positions)==(1 if scope=='earlier' else 16),'FACTORIAL_TERMINAL_POSITION_COUNT')
    request=work/'terminal-demands.json'
    write(request,[dict(Symbol=s,At=t,Studies=sorted(v)) for (s,t),v in sorted(demands.items())])
    native=REPORT/'terminal-native-assessments.json'
    subprocess.run(['dotnet',REPLAY,'--owner-held-residual-plan',str(source),str(tape),str(request),
                    str(registry),str(native)],check=True)
    result=read(native)
    need(result['RegistrySha256']==sha(registry) and result['DistinctSymbolClocks']==len(demands) and
         result['OriginalPoliciesReplayed']==result['Orders']==0,'FACTORIAL_TERMINAL_NATIVE_BINDING')
    # Mark assessments are diagnostic; no original position or cash is changed.
    # The restored market source is not asserted to be the original source digest.
    write(REPORT/'terminal-position-diagnosis.json',dict(Scope=scope,Positions=positions,
        OriginalReportBinding=bound['ArchiveSha256'],RestoredSourceSha256=sha(source),
        StatusCounts=dict(collections.Counter(a['Status'] for a in result['Assessments'])),
        DistinctSymbolClocks=len(demands),ValuableSymbolClocks=result['ResolvedBefore'],
        OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False,TerminalNetRestated=False))

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
    source_path=work/'factorial-source.json';plan_path=work/'factorial-plan.json'
    write(source_path,source);write(plan_path,plan);REPORT.mkdir()
    del source;gc.collect()
    write(REPORT/'registered-plan.json',plan)
    write(REPORT/'source-receipt.json',dict(Study=STUDY,Scope=scope,SourceSha256=sha(source_path),
        ProtocolSha256=sha(plan_path),RegistrySha256=registry_sha,Proof=proof,
        PreparationSeconds=round(time.monotonic()-started,3),Orders=0,CloudActivated=False))
    terminal_diagnosis(work,scope,p,source_path,work/'verified-protection',registry)
    return source_path,plan_path,registry

def run_native(work,source,plan,registry,out,stress,enabled,log_path):
    env=dict(os.environ,MXM_ECONOMIC_BOUNDED_NEIGHBORS=enabled,
             MXM_ECONOMIC_PAIRED_DISTRIBUTION=enabled,MXM_ECONOMIC_PROFILE='1')
    started=time.monotonic()
    with log_path.open('w') as log:
        process=subprocess.Popen(['dotnet',REPLAY,'--owner-path-distribution',str(plan),str(source),
            str(out),str(work/'verified-protection'),stress,str(registry)],
            env=env,stdout=subprocess.PIPE,text=True)
        for line in process.stdout:
            if line.startswith(('MXM_ECONOMIC_PROGRESS ','MXM_ECONOMIC_PROFILE ','COMPETITIVE_FAMILIES_')):
                print(line.rstrip(),flush=True);log.write(line);log.flush()
        need(process.wait()==0,'FACTORIAL_NATIVE_EXECUTION')
    return round(time.monotonic()-started,3)

def evaluate(work,scope):
    source,plan,registry=prepare(work,scope);receipt=read(REPORT/'source-receipt.json')
    results=[];timings=[]
    for i,stress in enumerate(STRESSES):
        out=PARTS/f'S{i}';out.mkdir(parents=True)
        seconds=run_native(work,source,plan,registry,out,stress,'1',REPORT/f'S{i}-progress.log')
        if scope=='earlier' and i==0:
            # Entire new 7-market S0 portfolio run, same input bytes, same
            # runner and instrumentation. Baseline is a technical comparison,
            # not an additional selected candidate or a closed study rerun.
            baseline=work/'technical-full-baseline';baseline.mkdir()
            baseline_seconds=run_native(work,source,plan,registry,baseline,stress,'0',REPORT/'full-baseline-progress.log')
            baseline_sha=sha(baseline/'result.json');optimized_sha=sha(out/'result.json')
            need(baseline_sha==optimized_sha,'FACTORIAL_FULL_ENGINE_EXACT_PARITY')
            write(REPORT/'full-engine-benchmark.json',dict(Scope=scope,Scenario=i,Markets=7,
                Books=9,SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
                BaselineSeconds=baseline_seconds,OptimizedSeconds=seconds,
                Speedup=Decimal(str(baseline_seconds))/max(Decimal(str(seconds)),Decimal('0.001')),
                ExactResultSha256=baseline_sha,ProfileEnabledBoth=True,OriginalPoliciesReplayed=0,
                Orders=0,CloudActivated=False))
            import shutil
            shutil.rmtree(baseline)
        result=read(out/'result.json')
        need(result['Study']==STUDY and result['SharedPortfolioEvaluations']==9 and
             result['SourceSha256']==receipt['SourceSha256'] and result['ProtocolSha256']==receipt['ProtocolSha256'] and
             result['Orders']==0 and not result['CloudActivated'],'FACTORIAL_NATIVE_RESULT')
        results.append(result);timings.append(seconds)
        for name in ('result.json','holding-valuation-gaps.json'):
            (REPORT/f'S{i}-{name}').write_bytes((out/name).read_bytes())
        print('FACTORIAL_SCENARIO_COMPLETE',scope,i+1,3,timings[-1],flush=True)
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
    seal_files([(p,str(p.relative_to(PARTS))) for p in files],'management-factorial-sealed',public,
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

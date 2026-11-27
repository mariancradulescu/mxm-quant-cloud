"""New common-book experiment; no frozen original policy is re-executed."""
import argparse,json,os,subprocess,time
from pathlib import Path
from decimal import Decimal
from . import owner_controlled_recency as parent
from . import owner_cost_context_geometry as geometry
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_monetary_reduce_common_book import REPLAY,STRESSES
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha,seal_files
from .custody_new import derive_recipient
from .decode import need
STUDY='MONETARY_PATH_DISTRIBUTION_1';REGISTRY=Path('research/path_distribution_economic_1.json');REPORT=Path('path-economic-report')
def write(p,v):Path(p).write_text(exact_json(v)+'\n')
def variants(n):
 base=dict(geometry.variants()[0]['Profile'],EconomicManagement='MONETARY_REDUCE',EconomicManagementTimeframe='M15',
  EconomicGeometryTimeframe='M15',DistributionTargetRanges=Decimal('2.5'),AnchorEconomicGeometryToClosedStructure=True,
  EconomicStructureLookbackBars=6,CaptureOpportunityPathEvidence=True,MinimumEpisodes=24,MinimumDays=5,
  MinimumContractVolumeOnly=False,CaptureVolatilityContext=True)
 return [dict(Id=name,UniverseCount=n,Profile=dict(base,LifecycleEstimator=estimator,
  RequirePathTailCapacity=tail,UsePathDistributionManagement=management))
  for name,estimator,tail,management in [('CENTERED_CONTROL','CENTERED_COST_CONTEXT',False,False),
   ('DISTRIBUTION_CONTEXT','DISTRIBUTION_CONTEXT',False,False),
   ('DISTRIBUTION_CONTEXT_TAIL','DISTRIBUTION_CONTEXT',True,False),
   ('DISTRIBUTION_CONTEXT_TAIL_MANAGEMENT','DISTRIBUTION_CONTEXT',True,True)]]

def prepare(work,scope):
 p=read(REGISTRY);need(p['Study']==STUDY and p['Scopes']==['earlier','recent'] and p['Orders']==0 and not p['CloudActivated'] and p['Models']==[v['Id'] for v in variants(29)] and p['SelectionMultiplicity']==12,'PATH_ECONOMIC_SCOPE')
 parent.prepare(work,scope);source=read(work/'net-source.json');plan=read(work/'net-plan.json');receipt=read(parent.REPORT/'source-receipt.json')
 recovery=dict(p['HeldRegistry'])
 if 'Artifact' not in recovery:
  repo=os.environ['GITHUB_REPOSITORY'];started=time.monotonic()
  while True:
   state=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{recovery["Run"]}']))
   need(state['head_sha']==p['HeldRegistryHead'] and state['head_branch']=='main','PATH_ECONOMIC_HELD_SOURCE_REVISION')
   pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{recovery["Run"]}/artifacts?per_page=100']))
   found=[a for page in pages for a in page['artifacts'] if a['name']==recovery['ArtifactName']]
   if found:
    need(len(found)==1 and not found[0]['expired'],'PATH_ECONOMIC_HELD_ARTIFACT')
    recovery.update(Artifact=found[0]['id'],ArchiveSha256=found[0]['digest'].removeprefix('sha256:'));break
   need(state['status']!='completed' and time.monotonic()-started<12600,'PATH_ECONOMIC_SOURCE_NOT_PUBLISHED')
   print('WAITING_FOR_COMPLETED_AUTHENTIC_MONETARY_REGISTRY',recovery['Run'],flush=True);time.sleep(30)
 verified_download(recovery['Artifact'],recovery['Run'],recovery['ArchiveSha256'],Path('held-recovery-verified'))
 registry=Path('held-recovery-verified/verified-valuation-registry.json')
 if 'RegistrySha256' in recovery:need(sha(registry)==recovery['RegistrySha256'],'PATH_ECONOMIC_MONETARY_REGISTRY_SHA')
 recovery['RegistrySha256']=sha(registry)
 need(read(registry)['Orders']==0 and not read(registry)['CloudActivated'] and read(registry)['PacketsReconciled']>0,'PATH_ECONOMIC_MONETARY_REGISTRY')
 plan.update(Study=STUDY,Variants=variants(len(source['Markets'])))
 proof=dict(Parent=receipt,Registry=p,HeldRegistryResolved=recovery,RegistrySha256=sha(registry),SourceBrokerRequests=0,OriginalPoliciesReplayed=0,
  PredictiveHorizonIsNotExitRule=True,FundingHorizonMs=3600000)
 protocol=__import__('hashlib').sha256(exact_json(plan).encode()).hexdigest();evidence=__import__('hashlib').sha256(exact_json(proof).encode()).hexdigest()
 source.update(ProtocolSha256=protocol,EvidenceManifestSha256=evidence,EngineRevision=os.environ['GITHUB_SHA']);plan.update(SourceProtocolSha256=protocol,EvidenceManifestSha256=evidence)
 write(work/'distribution-source.json',source);write(work/'distribution-plan.json',plan);REPORT.mkdir()
 write(REPORT/'registered-plan.json',plan);write(REPORT/'source-receipt.json',dict(Study=STUDY,Scope=scope,SourceSha256=sha(work/'distribution-source.json'),
  ProtocolSha256=sha(work/'distribution-plan.json'),Proof=proof,Orders=0,CloudActivated=False))
def evaluate(work,scope):
 prepare(work,scope);results=[];receipt=read(REPORT/'source-receipt.json')
 for i,stress in enumerate(STRESSES):
  out=Path('distribution-economic-parts')/('S'+str(i));out.mkdir(parents=True)
  subprocess.run(['dotnet',REPLAY,'--owner-path-distribution',str(work/'distribution-plan.json'),str(work/'distribution-source.json'),
   str(out),str(work/'verified-protection'),stress,'held-recovery-verified/verified-valuation-registry.json'],check=True)
  r=read(out/'result.json');need(r['Study']==STUDY and r['SharedPortfolioEvaluations']==5 and r['Orders']==0 and not r['CloudActivated'],'PATH_ECONOMIC_RESULT')
  results.append(r);(REPORT/('S'+str(i)+'-result.json')).write_bytes((out/'result.json').read_bytes())
  for name in ('holding-valuation-gaps.json',):
   (REPORT/('S'+str(i)+'-'+name)).write_bytes((out/name).read_bytes())
  print('PATH_DISTRIBUTION_ECONOMIC_COMPLETE',scope,i,flush=True)
 write(REPORT/'summary.json',dict(Study=STUDY,Scope=scope,SourceSha256=receipt['SourceSha256'],ProtocolSha256=receipt['ProtocolSha256'],
  CommonBookEvaluations=15,Selection=geometry.parent.corrected_selection([x for r in results for x in r['Selection']],Decimal('2.8')),
  SelectionMultiplicity=12,OriginalPoliciesReplayed=0,SourceBrokerRequests=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False))
def conserve():
 files=sorted(Path('distribution-economic-parts').glob('*/checkpoints/**/*.json'))
 if not files:return
 receipt=read(REPORT/'source-receipt.json');public,_=derive_recipient(os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode())
 seal_files([(p,str(p.relative_to('distribution-economic-parts'))) for p in files],'distribution-economic-sealed',public,
  os.environ['GITHUB_RUN_ID'],STUDY,receipt['SourceSha256'],complete=(REPORT/'summary.json').exists(),protocol_sha=receipt['ProtocolSha256'])
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','evaluate','conserve']);p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
 if a.stage=='check':
  v=read(REGISTRY);need(v['Study']==STUDY and v['Models']==[x['Id'] for x in variants(29)] and v['SelectionMultiplicity']==12 and v['Orders']==0 and not v['CloudActivated'],'PATH_ECONOMIC_REGISTRATION')
 elif a.stage=='conserve':conserve()
 else:evaluate(a.work,a.scope)
if __name__=='__main__':main()

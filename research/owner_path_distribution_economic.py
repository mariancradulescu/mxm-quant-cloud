"""New common-book experiment; no frozen original policy is re-executed."""
import argparse,os,subprocess
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
  MinimumContractVolumeOnly=True)
 return [dict(Id=name,UniverseCount=n,Profile=dict(base,LifecycleEstimator=estimator,UsePathDistributionManagement=management))
  for name,estimator,management in [('CENTERED_CONTROL','CENTERED_COST_CONTEXT',False),
   ('DISTRIBUTION_LOCAL','DISTRIBUTION_LOCAL',False),('DISTRIBUTION_CONTEXT','DISTRIBUTION_CONTEXT',False),
   ('DISTRIBUTION_CONTEXT_MANAGEMENT','DISTRIBUTION_CONTEXT',True)]]
def prepare(work,scope):
 p=read(REGISTRY);need(p['Study']==STUDY and p['Scopes']==['earlier','recent'] and p['Orders']==0 and not p['CloudActivated'],'PATH_ECONOMIC_SCOPE')
 parent.prepare(work,scope);source=read(work/'net-source.json');plan=read(work/'net-plan.json');receipt=read(parent.REPORT/'source-receipt.json')
 recovery=p['HeldRegistry'];verified_download(recovery['Artifact'],recovery['Run'],recovery['ArchiveSha256'],Path('held-recovery-verified'))
 registry=Path('held-recovery-verified/verified-valuation-registry.json')
 need(sha(registry)==recovery['RegistrySha256'] and read(registry)['Orders']==0,'PATH_ECONOMIC_MONETARY_REGISTRY')
 plan.update(Study=STUDY,Variants=variants(len(source['Markets'])))
 proof=dict(Parent=receipt,Registry=p,RegistrySha256=sha(registry),SourceBrokerRequests=0,OriginalPoliciesReplayed=0,
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
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['evaluate','conserve']);p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
 if a.stage=='conserve':conserve()
 else:evaluate(a.work,a.scope)
if __name__=='__main__':main()

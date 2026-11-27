"""Recover only the exact residual source windows certified by native inspection."""
import argparse,gc,json,os,shutil,subprocess
from pathlib import Path
from . import owner_held_remaining_source as collector
from . import owner_held_equity_recovery as held
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/held_residual_recovery_1.json')
def write(path,v):Path(path).write_text(exact_json(v)+'\n')
def check():
 p=read(REGISTRY)
 need(p['Study']=='OWNER_HELD_RESIDUAL_RECOVERY_1' and p['Scope']=='recent' and p['ExpectedAdditionalWindows']==146 and
  p['Orders']==p['OriginalPoliciesReplayed']==0 and not p['CloudActivated'],'HELD_RESIDUAL_RECOVERY_REGISTRATION')
 return p

def download(spec,destination):
 repo=os.environ['GITHUB_REPOSITORY'];state=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{spec["Run"]}']))
 need(state['head_sha']==spec['Head'] and state['head_branch']=='main','HELD_RESIDUAL_SOURCE_REVISION')
 verified_download(spec['Artifact'],spec['Run'],spec['ArchiveSha256'],destination)

def prepare():
 p=check();inspection=Path('held-residual-inspection');prior=Path('held-residual-prior')
 download(p['Inspection'],inspection);download(p['Prior'],prior)
 proof=read(inspection/'summary.json');targets=read(inspection/'additional-uncollected-targets.json')
 need(proof['Scope']=='recent' and proof['ResidualBookPoints']==2787 and proof['OriginalBooksWithExactHeldCountParity']==33 and
  proof['Prior']['Artifact']==p['Prior']['Artifact'] and proof['Prior']['ArchiveSha256']==p['Prior']['ArchiveSha256'] and
  len(targets)==p['ExpectedAdditionalWindows'] and sha(prior/'verified-valuation-registry.json')==proof['Prior']['RegistrySha256'],
  'HELD_RESIDUAL_EXACT_VERIFIED_TARGETS')
 collector.PLAN.mkdir();rid=os.environ['GITHUB_RUN_ID']
 write(collector.PLAN/'plan.json',dict(Study=collector.STUDY,RunId=rid,RegistrationSha256=sha(collector.REGISTRY),
  ResidualRegistrationSha256=sha(REGISTRY),Inspection=p['Inspection'],Prior=p['Prior'],
  PriorRegistrySha256=proof['Prior']['RegistrySha256'],PriorCoverageSha256=sha(prior/'collection-coverage.json'),
  Partitions=[targets],Targets=len(targets),OriginalCaptureRun=45973360072,Orders=0,CloudActivated=False))
 shutil.copyfile(prior/'verified-valuation-registry.json',collector.PLAN/'prior-verified-valuation-registry.json')
 shutil.copyfile(prior/'collection-coverage.json',collector.PLAN/'prior-collection-coverage.json')
 shutil.copyfile(prior/'recent-summary.json',collector.PLAN/'prior-equity-summary.json')
 write(collector.PLAN/'prior-readback-provenance.json',dict(CaptureRun=45973360072,
  Artifacts=read(Path('research/held_settlement_completion_1.json'))['OriginalArtifacts']))
 with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('partitions=[0]\n')
 print('RESIDUAL_ONLY_AUTHENTIC_SOURCE_WINDOWS',len(targets),flush=True)

def settle(work):
 p=check();_,plan=collector.plan();rid=os.environ['GITHUB_RUN_ID']
 need(plan['ResidualRegistrationSha256']==sha(REGISTRY),'HELD_RESIDUAL_PLAN_REGISTRATION')
 rows=sorted(Path('remaining-verified-all').glob('*/verified.json'));need(len(rows)==1,'HELD_RESIDUAL_ONE_PARTITION')
 verified=read(rows[0]);need(verified['RunId']==rid and verified['Index']==0 and verified['PlanSha256']==sha(collector.PLAN/'plan.json'),
  'HELD_RESIDUAL_PACKET_BINDING')
 prior=read(collector.PLAN/'prior-verified-valuation-registry.json');prefixes=prior['Rows']+verified['Rows']
 held.REPORT.mkdir();registry=held.REPORT/'verified-valuation-registry.json'
 write(registry,dict(Study=p['Study'],RunId=rid,OriginalCaptureRun=45973360072,Rows=prefixes,
  Prior=plan['Prior'],PriorRegistrySha256=plan['PriorRegistrySha256'],PacketsReconciled=7630+verified['PacketsReconciled'],
  ResidualSourceBrokerRequests=verified['PacketsReconciled'],OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))
 count=len(prefixes);requests=verified['PacketsReconciled'];new_rows=len(verified['Rows']);coverage=verified['Coverage'];receipt=verified['PacketReceipt']
 del prefixes,prior,verified;gc.collect()
 held.reprice_saved_books(work,'recent',registry,7630+requests,count,3844)
 baseline=read(collector.PLAN/'prior-equity-summary.json');result=read(held.REPORT/'recent-summary.json')
 write(held.REPORT/'residual-source-recovery-summary.json',dict(Study=p['Study'],RunId=rid,Head=os.environ['GITHUB_SHA'],
  Scope='recent',Inspection=p['Inspection'],Prior=plan['Prior'],PriorRegistrySha256=plan['PriorRegistrySha256'],
  RegistrySha256=sha(registry),AdditionalSourceWindows=plan['Targets'],SourceBrokerRequests=requests,NewPrefixRows=new_rows,
  IncompleteSides=sum(not r['Complete'] for r in coverage),AuthenticAbsentSides=sum(r['AuthenticAbsence'] for r in coverage),
  PriorUnknown=baseline['UnknownAfter'],NewUnknown=result['UnknownAfter'],AdditionalRecoveredBookPoints=baseline['UnknownAfter']-result['UnknownAfter'],
  PacketReceipt=receipt,Coverage=coverage,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False))
 print('RESIDUAL_EQUITY_RECOVERED',baseline['UnknownAfter']-result['UnknownAfter'],'UNKNOWN',result['UnknownAfter'],flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','prepare','settle']);p.add_argument('--work',type=Path);a=p.parse_args()
 if a.stage=='check':check()
 elif a.stage=='prepare':prepare()
 else:settle(a.work)
if __name__=='__main__':main()

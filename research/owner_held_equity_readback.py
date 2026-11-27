"""Verify conserved capture and saved books using the corrected archive path.
There is no broker transport or recapture in this entry point.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from . import owner_held_equity_recovery as recovery
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .merge_eur_scenarios import read,exact_json
from .decode import need
REGISTRY=Path('research/held_equity_readback_1.json')
def check():
 p=read(REGISTRY)
 need(p['Study']=='OWNER_HELD_EQUITY_READBACK_1' and p['OriginalCaptureRun']==45973360072
  and p['OriginalCaptureHead']=='f4dfb9afe4ce07d4d95d9f665e504adc3329325d' and p['Scopes']==['earlier','recent']
  and p['SourceBrokerRequests']==p['OriginalPoliciesReplayed']==p['Orders']==0 and not p['CloudActivated'],'HELD_READBACK_REGISTRATION')
 return p
def api(path):return json.loads(subprocess.check_output(['gh','api',f'repos/{os.environ["GITHUB_REPOSITORY"]}/'+path]))
def execute(work,scope,sources_only=False):
 p=check();run=p['OriginalCaptureRun'];status=api(f'actions/runs/{run}')
 need(status['head_sha']==p['OriginalCaptureHead'] and status['head_branch']=='main','HELD_READBACK_CAPTURE_REVISION')
 names=['held-recovery-plan-earlier','held-recovery-plan-recent','held-recovery-protected'];started=time.monotonic()
 while True:
  pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{run}/artifacts?per_page=100']))
  rows=[a for page in pages for a in page['artifacts'] if a['name'] in names]
  if len(rows)==3:break
  state=api(f'actions/runs/{run}')
  need(state['status']!='completed' and time.monotonic()-started<5400,'HELD_READBACK_CAPTURE_NOT_AVAILABLE')
  print('WAITING_FOR_EXISTING_CAPTURE_PUBLICATION',run,flush=True);time.sleep(30)
 for a in rows:
  destination=recovery.CAPTURE if a['name']=='held-recovery-protected' else Path('held-readback-download')/a['name']
  destination.parent.mkdir(parents=True,exist_ok=True)
  need(a['workflow_run']['id']==run and not a['expired'],'HELD_READBACK_ARTIFACT_BINDING')
  verified_download(a['id'],run,a['digest'].removeprefix('sha256:'),destination)
  if a['name']!='held-recovery-protected':
   recovery.PLAN.mkdir(exist_ok=True)
   for file in destination.iterdir():
    need(file.is_file() and file.suffix=='.json','HELD_READBACK_PLAN_FILE');(recovery.PLAN/file.name).write_bytes(file.read_bytes())
 recovery.verify(work,scope,run,sources_only=sources_only)
 (recovery.REPORT/'readback-provenance.json').write_text(exact_json(dict(Study=p['Study'],CaptureRun=run,
  CaptureHead=p['OriginalCaptureHead'],ReadbackRun=os.environ['GITHUB_RUN_ID'],ReadbackHead=os.environ['GITHUB_SHA'],
  Artifacts=[dict(Id=a['id'],Name=a['name'],ArchiveSha256=a['digest'].removeprefix('sha256:')) for a in rows],
  ArchiveStressFolderCorrection=True,SourceBrokerRequests=0,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))+'\n')
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','verify']);p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
 if a.stage=='check':check()
 else:execute(a.work,a.scope)
if __name__=='__main__':main()

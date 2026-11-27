"""Collect only authenticated coverage gaps left by the first source budget.
Successful intervals and authentic NO_QUOTES pages are never recollected.
"""
import argparse,json,os,subprocess,time
from pathlib import Path
from . import owner_held_equity_recovery as old
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .custody_new import checked_public
from . import owner_eer1_source as eer
from . import source_history_universe as src
from .decode import need
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport
STUDY='OWNER_HELD_REMAINING_SOURCE_1';REGISTRY=Path('research/held_remaining_source_1.json')
PLAN=Path('remaining-held-plan');CAPTURE=Path('remaining-held-protected');VERIFIED=Path('remaining-held-verified')
def write(p,v):Path(p).write_text(exact_json(v)+'\n')
def registered():
 p=read(REGISTRY)
 need(p['Study']==STUDY and p['OriginalCaptureRun']==45973360072 and p['TargetsPerPartition']==200 and
  p['Orders']==p['OriginalPoliciesReplayed']==0 and not p['CloudActivated'],'REMAINING_HELD_SCOPE')
 return p

def pending_targets(coverage,prefixes=()):
 known={}
 def add(symbol,side,lo,hi):
  if lo<=hi:known.setdefault((symbol,side),[]).append((lo,hi))
 for r in prefixes:
  w=r['Witness'];add(r['Symbol'],r['Side'],w['At'],w['SearchThrough'])
 for r in coverage['Rows']:
  if r['Mode']=='CLOSED_PREFIX':
   if r['Complete'] and r['AuthenticAbsence']:add(r['Symbol'],r['Side'],r['From'],r['Through'])
   continue
  cursor=r['From']
  for lo,hi in sorted(r['MissingWindows']):
   add(r['Symbol'],r['Side'],cursor,lo-1);cursor=max(cursor,hi+1)
  add(r['Symbol'],r['Side'],cursor,r['Through'])
 for key,spans in known.items():
  merged=[]
  for lo,hi in sorted(spans):
   if merged and lo<=merged[-1][1]+1:merged[-1]=(merged[-1][0],max(hi,merged[-1][1]))
   else:merged.append((lo,hi))
  known[key]=merged
 targets={}
 for row in coverage['Rows']:
  if row['Complete']:continue
  spans=known.get((row['Symbol'],row['Side']),[])
  if row['Mode']=='CLOSED_PREFIX' and any(lo<=row['Through']<=hi for lo,hi in spans):continue
  for lo,hi in row['MissingWindows']:
   need(lo<=hi and row['Side'] in ('BID','ASK') and row['Mode'] in ('OPEN_INTERVAL','CLOSED_PREFIX'),'REMAINING_WINDOW')
   pending=[(lo,hi)]
   if row['Mode']=='OPEN_INTERVAL':
    for start,end in spans:
     pending=[part for a,b in pending for part in ([(a,min(b,start-1))] if a<start else [])+
      ([(max(a,end+1),b)] if b>end else []) if part[0]<=part[1]]
   for start,end in pending:
    key=(row['Symbol'],row['Side'],row['Mode'],start,end)
    targets[key]=dict(Symbol=row['Symbol'],Sides=[row['Side']],Mode=row['Mode'],Session=row['Group'],From=start,Through=end,Clocks=[])
 return [targets[k] for k in sorted(targets)]

def prepare():
 p=registered();prior=dict(p['PriorReadback']);folder=Path('remaining-held-prior')
 if 'Artifact' not in prior:
  repo=os.environ['GITHUB_REPOSITORY'];started=time.monotonic()
  while True:
   status=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{prior["Run"]}']))
   need(status['head_sha']==p['PriorReadbackHead'] and status['head_branch']=='main','REMAINING_PRIOR_REVISION')
   pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{prior["Run"]}/artifacts?per_page=100']))
   found=[a for page in pages for a in page['artifacts'] if a['name']==prior['ArtifactName']]
   if found:
    need(len(found)==1 and not found[0]['expired'],'REMAINING_PRIOR_ARTIFACT')
    prior.update(Artifact=found[0]['id'],ArchiveSha256=found[0]['digest'].removeprefix('sha256:'));break
   need(status['status']!='completed' and time.monotonic()-started<10800,'REMAINING_PRIOR_REPORT_NOT_AVAILABLE')
   print('WAITING_FOR_AUTHENTIC_READBACK_REPORT',prior['Run'],flush=True);time.sleep(30)
 verified_download(prior['Artifact'],prior['Run'],prior['ArchiveSha256'],folder)
 if 'RegistrySha256' in prior:need(sha(folder/'verified-valuation-registry.json')==prior['RegistrySha256'],'REMAINING_PRIOR_REGISTRY')
 prior['RegistrySha256']=sha(folder/'verified-valuation-registry.json')
 need(read(folder/'verified-valuation-registry.json')['PacketsReconciled']>0,'REMAINING_PRIOR_PACKET_VERIFICATION')
 coverage=read(folder/'collection-coverage.json');need(coverage['RunId']==str(p['OriginalCaptureRun']),'REMAINING_PRIOR_CAPTURE')
 targets=pending_targets(coverage,read(folder/'verified-valuation-registry.json')['Rows']);PLAN.mkdir();parts=[targets[i:i+p['TargetsPerPartition']] for i in range(0,len(targets),p['TargetsPerPartition'])]
 if not parts:parts=[[]]
 write(PLAN/'plan.json',dict(Study=STUDY,RunId=os.environ['GITHUB_RUN_ID'],RegistrationSha256=sha(REGISTRY),
  PriorCoverageSha256=sha(folder/'collection-coverage.json'),PriorRegistrySha256=prior['RegistrySha256'],
  Prior=prior,Partitions=parts,Targets=len(targets),OriginalCaptureRun=p['OriginalCaptureRun'],Orders=0,CloudActivated=False))
 if not (folder/'readback-provenance.json').exists():
  repo=os.environ['GITHUB_REPOSITORY'];run=p['OriginalCaptureRun']
  pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100']))
  archives=[a for page in pages for a in page['artifacts'] if a['name'] in ('held-recovery-plan-earlier','held-recovery-plan-recent','held-recovery-protected')]
  need(len(archives)==3,'REMAINING_ORIGINAL_ARCHIVES')
  write(folder/'readback-provenance.json',dict(CaptureRun=run,Artifacts=[dict(Id=a['id'],Name=a['name'],ArchiveSha256=a['digest'].removeprefix('sha256:')) for a in archives]))
 for name in ('verified-valuation-registry.json','collection-coverage.json','readback-provenance.json'):
  (PLAN/('prior-'+name)).write_bytes((folder/name).read_bytes())
 with open(os.environ['GITHUB_OUTPUT'],'a') as out:out.write('partitions='+json.dumps(list(range(len(parts))))+'\n')
 print('REMAINING_HELD_DISTINCT_WINDOWS',len(targets),'PARTITIONS',len(parts),flush=True)

def plan():
 p=registered();v=read(PLAN/'plan.json');need(v['Study']==STUDY and v['RunId']==os.environ['GITHUB_RUN_ID']
  and v['RegistrationSha256']==sha(REGISTRY),'REMAINING_PLAN_BINDING');return p,v

def capture(index):
 p,v=plan();rid=os.environ['GITHUB_RUN_ID'];targets=v['Partitions'][index]
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main'
  and os.environ['GITHUB_RUN_ATTEMPT']=='1','REMAINING_READONLY_CONTEXT')
 if not targets:
  CAPTURE.mkdir();sealed=eer.seal(CAPTURE/'packets.sealed',dict(Study=STUDY,RunId=rid,PlanSha256=sha(PLAN/'plan.json'),Index=index,
   Targets=[],Rows=[],Coverage=[],Packets=[]),checked_public(Path('new-recipient-output'),rid),rid)
  write(CAPTURE/'receipt.json',dict(Study=STUDY,Index=index,RunId=rid,sealed=sealed,Requests=0,Orders=0,CloudActivated=False));return
 t=P05ReadOnlyTransport(response_timeout=20);coverage=[]
 try:
  account=authenticate(t);need(src.original_account(account),'REMAINING_ACCOUNT')
  src.MAX_REQUESTS=5000;journal=src.Journal(t,account);journal.deadline=time.monotonic()+3000
  rows=old.collect(journal,account,targets,coverage,page_budget=4000)
 finally:t.close()
 CAPTURE.mkdir();sealed=eer.seal(CAPTURE/'packets.sealed',dict(Study=STUDY,RunId=rid,PlanSha256=sha(PLAN/'plan.json'),
  Index=index,Targets=targets,Rows=rows,Coverage=coverage,Packets=journal.packets),checked_public(Path('new-recipient-output'),rid),rid)
 write(CAPTURE/'receipt.json',dict(Study=STUDY,Index=index,RunId=rid,sealed=sealed,Requests=len(journal.packets),
  Orders=0,CloudActivated=False))
 print('REMAINING_CAPTURE',index,len(journal.packets),'INCOMPLETE',sum(not r['Complete'] for r in coverage),flush=True)

def verify(index):
 p,v=plan();rid=os.environ['GITHUB_RUN_ID'];receipt=read(CAPTURE/'receipt.json')
 payload=eer.unpack(CAPTURE,receipt['sealed'],os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode(),rid)
 need(payload['RunId']==rid and payload['Study']==STUDY and payload['Index']==index and
  payload['PlanSha256']==sha(PLAN/'plan.json') and payload['Targets']==v['Partitions'][index],'REMAINING_PACKET_BINDING')
 packets=payload['Packets']
 if not packets:
  need(not payload['Targets'] and not payload['Rows'] and not payload['Coverage'] and receipt['Requests']==0,'REMAINING_EMPTY_PARTITION')
  VERIFIED.mkdir();write(VERIFIED/'verified.json',dict(Study=STUDY,RunId=rid,Index=index,PlanSha256=sha(PLAN/'plan.json'),Rows=[],PacketsReconciled=0,Coverage=[],PacketReceipt=receipt,Orders=0,CloudActivated=False));return
 account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
 need(src.original_account(account),'REMAINING_READBACK_ACCOUNT');journal=src.ReadbackJournal(packets);coverage=[]
 rows=old.collect(journal,account,payload['Targets'],coverage,page_budget=4000)
 need(rows==payload['Rows'] and coverage==payload['Coverage'] and journal.index==len(packets)==receipt['Requests'],'REMAINING_EXACT_PACKET_PARITY')
 VERIFIED.mkdir();prefixes=[dict(Symbol=r['Symbol'],Side=r['Side'],Witness=r['Witness'],EvidenceSha256=receipt['sealed']['plainSha256'])
  for r in rows if r['Witness']['Status']=='AUTHENTIC_LATEST_PREFIX']
 write(VERIFIED/'verified.json',dict(Study=STUDY,RunId=rid,Index=index,PlanSha256=sha(PLAN/'plan.json'),Rows=prefixes,
  PacketsReconciled=len(packets),Coverage=coverage,PacketReceipt=receipt,Orders=0,CloudActivated=False))

def restore_original_inputs():
 prior=read(PLAN/'prior-readback-provenance.json')
 for a in prior['Artifacts']:
  folder=old.CAPTURE if a['Name']=='held-recovery-protected' else Path('remaining-original-download')/a['Name']
  verified_download(a['Id'],prior['CaptureRun'],a['ArchiveSha256'],folder)
  if a['Name']!='held-recovery-protected':
   old.PLAN.mkdir(exist_ok=True)
   for path in folder.iterdir():(old.PLAN/path.name).write_bytes(path.read_bytes())

def settle(work,scope):
 p,v=plan();rid=os.environ['GITHUB_RUN_ID'];root=Path('remaining-verified-all');VERIFIED.mkdir(exist_ok=True)
 files=sorted(root.glob('*/verified.json'));need(len(files)==len(v['Partitions']),'REMAINING_ALL_PARTITIONS')
 records=[read(path) for path in files]
 need({r['Index'] for r in records}==set(range(len(v['Partitions']))) and all(r['RunId']==rid and
  r['PlanSha256']==sha(PLAN/'plan.json') and r['Orders']==0 and not r['CloudActivated'] for r in records),'REMAINING_PARTITIONS_BINDING')
 prior=read(PLAN/'prior-verified-valuation-registry.json');rows=prior['Rows']+[row for r in records for row in r['Rows']]
 merged=VERIFIED/'merged-valuation-registry.json'
 write(merged,dict(Study=STUDY,RunId=rid,OriginalCaptureRun=p['OriginalCaptureRun'],Rows=rows,
  PriorRegistrySha256=v['PriorRegistrySha256'],PacketsReconciled=sum(r['PacketsReconciled'] for r in records),
  SourceBrokerRequests=sum(r['PacketsReconciled'] for r in records),Orders=0,CloudActivated=False))
 restore_original_inputs();old.verify(work,scope,p['OriginalCaptureRun'],merged)
 coverage=[row for r in records for row in r['Coverage']]
 write(old.REPORT/'remaining-source-summary.json',dict(Study=STUDY,RunId=rid,OriginalCaptureRun=p['OriginalCaptureRun'],Scope=scope,
  PreviousMissingWindows=v['Targets'],Partitions=len(records),Requests=sum(r['PacketsReconciled'] for r in records),
  ProvenPrefixes=len(rows),IncompleteSides=sum(not r['Complete'] for r in coverage),
  MissingRequestWindows=sum(len(r['MissingWindows']) for r in coverage),AuthenticAbsentSides=sum(r['AuthenticAbsence'] for r in coverage),
  Coverage=coverage,SupplementalRegistrySha256=sha(merged),OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['prepare','capture','verify','settle']);p.add_argument('--index',type=int);p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
 if a.stage=='prepare':prepare()
 elif a.stage=='capture':capture(a.index)
 elif a.stage=='verify':verify(a.index)
 else:settle(a.work,a.scope)
if __name__=='__main__':main()

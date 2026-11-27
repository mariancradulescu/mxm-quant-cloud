"""Session-deduplicated source recovery and restatement of immutable saved books.
No original policy is run; authenticated event cash/fills remain unchanged.
"""
import argparse,collections,gzip,hashlib,json,os,subprocess,time
from decimal import Decimal
from pathlib import Path
from . import owner_controlled_recency as preparation
from . import owner_held_valuation_preflight as preflight
from . import owner_eer1_source as eer
from . import source_history_universe as src
from . import owner_eur_rollover_continuity as roll
from . import owner_funding_prefix_settlement as prefix
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_monetary_reduce_common_book import REPLAY
from .owner_eur_archive_funding_2 import plan_ids
from .custody_new import checked_public
from .custody import unseal_new
from .decode import need
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .owner_readonly_auth import authenticate
from .p05_safe_transport import P05ReadOnlyTransport
from .ctrader_proto import OpenApiMessages_pb2 as m,OpenApiModelMessages_pb2 as e
STUDY='OWNER_HELD_EQUITY_RECOVERY_1'
PLAN=Path('held-recovery-plan');CAPTURE=Path('held-recovery-protected');REPORT=Path('held-recovery-report')
MEMORY={
 'earlier':(15179383978,45957472368,'c921303689f56088834678ff0352e491d44d2d0637ead291be97a94e727deb77'),
 'recent':(15179723619,45957472368,'27fcc71c4ca025846aac8ba488739187abdbc432c57cd902f1063c8b62e0d63c')}
BOOKS={
 ('NET_HORIZON','earlier'):(15175968965,45948572291,'931dc4ea074f79b124dcaf0b627b05589a1667b7cf3a178da726309ddd45333b'),
 ('NET_HORIZON','recent'):(15176756226,45948572291,'2acf2a4a45f9da7aee4ab14399db2af42ae5a50adc82034b9c3d6f732c72587f'),
 ('MEMORY','earlier'):(15180190673,45957472368,'91c56cb6ca3f09f4f7940c32e9817f775e6e9ac064e2ba2f3696e33d7d394d8b'),
 ('MEMORY','recent'):(15179639035,45957472368,'d9ae5c40f2ec4e16976a052600a488e0a09a3029cba4b0178cc535f4778f38cc')}

def write(p,v):Path(p).write_text(exact_json(v)+'\n')
def registered():
 p=read(Path('research/held_equity_recovery_1.json'))
 need(p['Study']==STUDY and p['Scopes']==['earlier','recent'] and p['Studies']==['NET_HORIZON','MEMORY']
      and p['Orders']==p['OriginalPoliciesReplayed']==0 and not p['CloudActivated'],'HELD_RECOVERY_SCOPE')
 return p

def demand_rows(reports):
 rows=collections.defaultdict(set)
 for study,folder in reports.items():
  for i in range(3):
   for row in read(folder/f'S{i}-holding-valuation-gaps.json'):
    for at in row['Clocks']:rows[row['Symbol'],at].add(study)
 return [dict(Symbol=n,At=a,Studies=sorted(s)) for (n,a),s in sorted(rows.items())]

def restore(work,scope):
 work.mkdir(mode=0o700,parents=True,exist_ok=True)
 reports={'NET_HORIZON':work/'net-original','MEMORY':work/'memory-original'}
 verified_download(*preflight.ORIGINALS[scope],reports['NET_HORIZON'])
 verified_download(*MEMORY[scope],reports['MEMORY'])
 preparation.prepare(work/'source',scope)
 base=read(work/'source/net-source.json')
 for study,folder in reports.items():
  receipt=read(folder/'source-receipt.json');plan=read(folder/'registered-plan.json')
  source=dict(base,ProtocolSha256=plan['SourceProtocolSha256'],EvidenceManifestSha256=plan['EvidenceManifestSha256'],
   EngineRevision='50bd43f3025f23f031014f27cc53ea4186283b5b' if study=='NET_HORIZON' else '763340c30a43b5f5c2248e36506beca8b17db6fb')
  path=work/(study+'-source.json');write(path,source)
  need(sha(path)==receipt['SourceSha256'],'HELD_RECOVERY_EXACT_SOURCE_'+study)
 return reports,work/'NET_HORIZON-source.json',work/'source/verified-protection'

def prepare(work,scope):
 registered();reports,source,tape=restore(work,scope);PLAN.mkdir(exist_ok=True)
 demands=PLAN/(scope+'-demands.json');write(demands,demand_rows(reports))
 subprocess.run(['dotnet',REPLAY,'--owner-held-recovery-plan',str(source),str(tape),str(demands),str(PLAN/(scope+'-plan.json'))],check=True)
 p=read(PLAN/(scope+'-plan.json'));print('HELD_RECOVERY_PLAN',scope,p['DistinctSymbolClocks'],len(p['Groups']),flush=True)

def groups():
 registered();rows={}
 for scope in ('earlier','recent'):
  p=read(PLAN/(scope+'-plan.json'));need(p['Study']==STUDY,'HELD_RECOVERY_PLAN_STUDY')
  for g in p['Groups']:
   key=(g['Symbol'],g['Mode'],g['Session'])
   if key in rows:
    old=rows[key];old['From']=min(old['From'],g['From']);old['Through']=max(old['Through'],g['Through'])
    old['Clocks']=sorted(set(old['Clocks'])|set(g['Clocks']))
   else:rows[key]=g
 return sorted(rows.values(),key=lambda g:(g['Symbol'],g['From'],g['Through']))

def collect(journal,account,targets,coverage_sink=None,page_budget=6000):
 ids=plan_ids(dict(Targets=[dict(Symbol=g['Symbol']) for g in targets]));rows=[];budget=[page_budget]
 for index,g in enumerate(targets):
  for side,label in ((e.BID,'BID'),(e.ASK,'ASK')):
   if label not in g.get('Sides',['BID','ASK']):continue
   if g['Mode']=='CLOSED_PREFIX':
    res,_,_=journal.query(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,symbolId=ids[g['Symbol']],type=side,
       fromTimestamp=g['From'],toTimestamp=g['Through']))
    witness=prefix.latest(res,account,g['From'],g['Through'])
    rows.append(dict(Group=index,Symbol=g['Symbol'],Side=label,Witness=witness))
    if coverage_sink is not None:
     absent=(type(res) is m.ProtoOAGetTickDataRes and res.IsInitialized() and res.HasField('hasMore') and not res.hasMore and not res.tickData) or (isinstance(res,m.ProtoOAErrorRes) and res.errorCode=='NO_QUOTES')
     coverage_sink.append(dict(Group=index,Symbol=g['Symbol'],Side=label,Mode=g['Mode'],From=g['From'],Through=g['Through'],
      Complete=witness['Status']=='AUTHENTIC_LATEST_PREFIX' or absent,AuthenticAbsence=absent,
      MissingWindows=[] if witness['Status']=='AUTHENTIC_LATEST_PREFIX' or absent else [[g['From'],g['Through']]]))
   else:
    ticks,leaves=roll.tick_window(journal.query,account,ids[g['Symbol']],side,g['From'],g['Through'],budget)
    complete=[(a,b) for a,b,status,_,_ in leaves if status in ('VERIFIED_COMPLETE_PAGE','PROVIDER_NO_QUOTES')]
    if coverage_sink is not None:
     missing=[];cursor=g['From']
     for lo,hi in sorted(complete):
      if hi<cursor:continue
      if lo>cursor:missing.append([cursor,min(lo-1,g['Through'])])
      cursor=max(cursor,hi+1)
     if cursor<=g['Through']:missing.append([cursor,g['Through']])
     coverage_sink.append(dict(Group=index,Symbol=g['Symbol'],Side=label,Mode=g['Mode'],From=g['From'],Through=g['Through'],
      Complete=not missing,AuthenticAbsence=not missing and not ticks,MissingWindows=missing))
    # Only ticks followed by continuously witnessed coverage become prefixes.
    by=collections.defaultdict(set)
    for at,raw in ticks:by[at].add(raw)
    stamps=sorted(by)
    for j,at in enumerate(stamps):
     if len(by[at])!=1:continue
     through=stamps[j+1]-1 if j+1<len(stamps) else g['Through']
     cursor=at
     for lo,hi in sorted(complete):
      if hi<cursor:continue
      if lo>cursor:break
      cursor=max(cursor,hi+1)
     through=min(through,cursor-1)
     if through<at:continue
     w=dict(Status='AUTHENTIC_LATEST_PREFIX',SearchFrom=at,SearchThrough=through,At=at,
      Price=str(Decimal(next(iter(by[at]))).scaleb(-5)),PrefixNewestFirst=True,LeadingTimestampComplete=True)
     rows.append(dict(Group=index,Symbol=g['Symbol'],Side=label,Witness=w))
  if (index+1)%25==0:print('HELD_RECOVERY_GROUP',index+1,len(targets),flush=True)
 return rows

def capture():
 targets=groups();rid=os.environ['GITHUB_RUN_ID']
 need(os.environ['GITHUB_EVENT_NAME']=='push' and os.environ['GITHUB_REF']=='refs/heads/main'
      and os.environ['GITHUB_RUN_ATTEMPT']=='1','HELD_RECOVERY_CAPTURE_CONTEXT')
 t=P05ReadOnlyTransport(response_timeout=20)
 try:
  account=authenticate(t);need(src.original_account(account),'HELD_RECOVERY_ACCOUNT')
  src.MAX_REQUESTS=10000;journal=src.Journal(t,account);journal.deadline=time.monotonic()+6600
  rows=collect(journal,account,targets)
 finally:t.close()
 CAPTURE.mkdir();digest=src.digest(exact_json(targets).encode())
 sealed=eer.seal(CAPTURE/'packets.sealed',dict(RunId=rid,PlanSha256=digest,Groups=targets,Rows=rows,Packets=journal.packets),
  checked_public(Path('new-recipient-output'),rid),rid)
 write(CAPTURE/'receipt.json',dict(Study=STUDY,RunId=rid,PlanSha256=digest,sealed=sealed,
  Requests=len(journal.packets),Groups=len(targets),Orders=0,CloudActivated=False))
 print('HELD_RECOVERY_CAPTURE_REQUESTS',len(journal.packets),flush=True)

def restore_final_books(spec,folder,dest,key,source_sha):
 verified_download(*spec,folder);run=str(spec[1])
 public=read(folder/'checkpoint-receipt.json');need(sha(folder/'manifest.sealed')==public['ManifestCipherSha256'],'HELD_BOOK_MANIFEST_HASH')
 manifest=json.loads(gzip.decompress(unseal_new((folder/'manifest.sealed').read_bytes(),key,run)))
 need(manifest['RunId']==run and manifest['SourceSha256']==source_sha and manifest['Complete'],'HELD_BOOK_BINDING')
 files=[x for x in manifest['Files'] if '-observer' not in x['Path']]
 final=max(int(Path(x['Path']).parts[-2]) for x in files)
 selected=[x for x in files if int(Path(x['Path']).parts[-2])==final]
 dest.mkdir()
 for row in selected:
  relative=Path(row['Path']);need(not relative.is_absolute() and '..' not in relative.parts,'HELD_BOOK_PATH')
  path=dest/relative;path.parent.mkdir(parents=True,exist_ok=True);offset=0
  with path.open('xb') as out:
   for part in row['Parts']:
    name=Path(part['File']);need(name.name==str(name),'HELD_BOOK_PART_PATH')
    cipher=(folder/name).read_bytes();need(src.digest(cipher)==part['CipherSha256'],'HELD_BOOK_CIPHER')
    clear=gzip.decompress(unseal_new(cipher,key,run))
    need(part['Offset']==offset and len(clear)==part['Bytes'] and src.digest(clear)==part['PlainSha256'],'HELD_BOOK_PART')
    out.write(clear);offset+=len(clear)
  need(offset==row['Bytes'] and sha(path)==row['Sha256'],'HELD_BOOK_PLAINTEXT_HASH');yield path

def verify(work,scope,capture_run=None,registry_override=None,sources_only=False):
 registered();p=read(CAPTURE/'receipt.json');rid=str(capture_run or os.environ['GITHUB_RUN_ID']);key=os.environ['R3_CUSTODY_PRIVATE_KEY_PEM'].encode()
 payload=eer.unpack(CAPTURE,p['sealed'],key,rid);targets=groups()
 need(payload['RunId']==rid and payload['Groups']==targets and p['PlanSha256']==src.digest(exact_json(targets).encode()),'HELD_CAPTURE_BINDING')
 packets=payload['Packets'];account=src.decode(packets[0]['reqType'],packets[0]['req']).ctidTraderAccountId
 need(src.original_account(account),'HELD_READBACK_ACCOUNT');journal=src.ReadbackJournal(packets)
 coverage=[];rows=collect(journal,account,targets,coverage)
 need(rows==payload['Rows'] and journal.index==len(packets)==p['Requests'],'HELD_PACKET_PARITY')
 REPORT.mkdir();write(REPORT/'collection-coverage.json',dict(Study=STUDY,RunId=rid,Rows=coverage,
  IncompleteSides=sum(not x['Complete'] for x in coverage),AuthenticAbsentSides=sum(x['AuthenticAbsence'] for x in coverage),
  MissingRequestWindows=sum(len(x['MissingWindows']) for x in coverage),SourceBrokerRequests=0,Orders=0,CloudActivated=False))
 proven=[dict(Symbol=r['Symbol'],Side=r['Side'],Witness=r['Witness'],EvidenceSha256=p['sealed']['plainSha256'])
  for r in rows if r['Witness']['Status']=='AUTHENTIC_LATEST_PREFIX']
 if registry_override is not None:proven=read(registry_override)['Rows']
 registry=REPORT/'verified-valuation-registry.json'
 write(registry,dict(Study=STUDY,RunId=rid,PlanSha256=p['PlanSha256'],Rows=proven,PacketsReconciled=len(packets),
  SupplementalRegistrySha256=sha(registry_override) if registry_override is not None else None,
  UnresolvedPrefixes=[r for r in rows if r['Witness']['Status']!='AUTHENTIC_LATEST_PREFIX'],OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))
 if sources_only:return
 requests,prefix_count=len(packets),len(proven)
 # The verified file is authoritative. Release multi-million-row Python
 # object graphs before decrypting saved books and starting the native reader.
 del payload,packets,rows,proven,journal
 import gc
 gc.collect()
 reports,source,tape=restore(work,scope);results=[]
 for study,folder in reports.items():
  srcpath=work/(study+'-source.json');source_sha=read(folder/'source-receipt.json')['SourceSha256']
  paths=restore_final_books(BOOKS[study,scope],work/(study+'-cipher'),work/(study+'-books'),key,source_sha)
  for path in paths:
   stress=path.parts[-4];book_id=path.stem;out=REPORT/(scope+'-'+study+'-'+stress+'-'+book_id+'.json')
   subprocess.run(['dotnet',REPLAY,'--owner-frozen-held-equity',str(srcpath),str(tape),str(registry),str(path),
    str(folder/(stress+'-result.json')),book_id,str(out)],check=True)
   r=read(out);results.append({k:v for k,v in r.items() if k!='Changes'})
   print('FROZEN_EQUITY_RECOVERED',scope,study,stress,book_id,r['RecoveredEquityPoints'],flush=True)
   path.unlink()
  import shutil
  shutil.rmtree(work/(study+'-cipher'));shutil.rmtree(work/(study+'-books'))
 write(REPORT/(scope+'-summary.json'),dict(Study=STUDY,Scope=scope,Groups=len(targets),Requests=requests,
  Prefixes=prefix_count,Results=results,RecoveredEquityPoints=sum(r['RecoveredEquityPoints'] for r in results),
  UnknownBefore=sum(r['UnknownBefore'] for r in results),UnknownAfter=sum(r['UnknownAfter'] for r in results),
  NewAdmissions=0,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False))

def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','prepare','capture','verify']);p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);p.add_argument('--capture-run',type=int);a=p.parse_args()
 if a.stage=='check':registered()
 elif a.stage=='prepare':prepare(a.work,a.scope)
 elif a.stage=='capture':capture()
 else:verify(a.work,a.scope,a.capture_run)
if __name__=='__main__':main()

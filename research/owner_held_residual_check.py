"""Inspect actual residual held symbols using conserved, authenticated sources.
Reconstruction is accepted only after every original held-count matches.
"""
import argparse,collections,hashlib,json,os,shutil,subprocess,time
from pathlib import Path
from . import owner_held_equity_recovery as old
from . import owner_held_remaining_source as remaining
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .owner_monetary_reduce_common_book import REPLAY
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/held_residual_check_1.json');REPORT=Path('held-residual-report')
def write(path,value):Path(path).write_text(exact_json(value)+'\n')
def check():
 p=read(REGISTRY)
 need(p['Study']=='OWNER_HELD_RESIDUAL_CHECK_1' and p['PriorRun']==45983234609 and
  p['PriorHead']=='2c09c5d3a68b877e1b750f2d364afc4a47ff725c' and p['Scopes']==['earlier','recent'] and
  p['SourceBrokerRequests']==p['OriginalPoliciesReplayed']==p['Orders']==0 and not p['CloudActivated'],'HELD_RESIDUAL_REGISTRATION')
 return p

def residual_demands(reports,prior,scope):
 demands=collections.defaultdict(set);book_count=points=0
 for study,folder in reports.items():
  for stress in range(3):
   original=folder/f'S{stress}-result.json';report=read(original)
   for book in report['CommonBooks']:
    baseline=read(prior/f'{scope}-{study}-S{stress}-{book["Id"]}.json');result=book['Result']
    need(baseline['OriginalReportSha256']==sha(original) and baseline['CashEur']==result['CashEur'] and
     baseline['EventChainHash']==result['EventChainHash'] and baseline['Orders']==baseline['OriginalPoliciesReplayed']==0,
     'HELD_RESIDUAL_ORIGINAL_CASH_CHAIN')
    recovered={r['At'] for r in baseline['Changes']};closing={};events=[]
    for e in book['Details']['Episodes']:closing[e['PositionId']]=max(closing.get(e['PositionId'],0),e['CloseAt'])
    for a in book['Details']['Admissions']:
     if a['FillAt'] is None:continue
     events.append((a['FillAt'],1,a['PositionId'],a['Symbol']))
     if a['PositionId'] in closing:events.append((closing[a['PositionId']],-1,a['PositionId'],a['Symbol']))
    events.sort();active={};index=0;left=0
    for point in book['Details']['EquityPath']:
     while index<len(events) and events[index][0]<=point['At']:
      _,direction,pid,symbol=events[index]
      if direction==1:
       need(pid not in active,'HELD_RESIDUAL_DUPLICATE_FILLED_POSITION');active[pid]=symbol
      else:
       need(pid in active,'HELD_RESIDUAL_CLOSE_BEFORE_FILL');del active[pid]
      index+=1
     need(len(active)==point['Held'],'HELD_RESIDUAL_EVERY_ORIGINAL_HELD_COUNT')
     if point['EquityEur'] is None and point['At'] not in recovered:
      left+=1
      for symbol in set(active.values()):demands[symbol,point['At']].add(study)
    need(left==baseline['UnknownAfter'],'HELD_RESIDUAL_POINT_PARITY');book_count+=1;points+=left
 return [dict(Symbol=s,At=t,Studies=sorted(v)) for (s,t),v in sorted(demands.items())],book_count,points

def fetch_prior(p,scope,folder):
 repo=os.environ['GITHUB_REPOSITORY'];started=time.monotonic();run=p['PriorRun'];name='held-equity-completed-'+scope
 while True:
  state=json.loads(subprocess.check_output(['gh','api',f'repos/{repo}/actions/runs/{run}']))
  need(state['head_sha']==p['PriorHead'] and state['head_branch']=='main','HELD_RESIDUAL_PRIOR_REVISION')
  pages=json.loads(subprocess.check_output(['gh','api','--paginate','--slurp',f'repos/{repo}/actions/runs/{run}/artifacts?per_page=100']))
  matches=[a for page in pages for a in page['artifacts'] if a['name']==name]
  if matches:break
  need(state['status']!='completed' and time.monotonic()-started<10800,'HELD_RESIDUAL_PRIOR_NOT_PUBLISHED')
  print('WAITING_FOR_CONSERVED_EQUITY_RESULT',scope,run,flush=True);time.sleep(30)
 need(len(matches)==1 and not matches[0]['expired'],'HELD_RESIDUAL_PRIOR_ARTIFACT')
 a=matches[0];verified_download(a['id'],run,a['digest'].removeprefix('sha256:'),folder)
 need((folder/(scope+'-summary.json')).is_file(),'HELD_RESIDUAL_PRIOR_COMPLETE')
 return dict(Run=run,Head=p['PriorHead'],Artifact=a['id'],ArchiveSha256=a['digest'].removeprefix('sha256:'),RegistrySha256=sha(folder/'verified-valuation-registry.json'))

def inspect(work,scope):
 p=check();work.mkdir(parents=True,mode=0o700);prior=work/'prior';binding=fetch_prior(p,scope,prior)
 inspect_conserved(work,scope,binding,prior,prior)

def inspect_conserved(work,scope,binding,prior,coverage_folder):
 reports,source,tape=old.restore(work/'source',scope);demands,books,points=residual_demands(reports,prior,scope)
 REPORT.mkdir();write(REPORT/'residual-demands.json',demands)
 registry=prior/'verified-valuation-registry.json';plan=REPORT/'native-residual-assessment.json'
 subprocess.run(['dotnet',REPLAY,'--owner-held-residual-plan',str(source),str(tape),str(REPORT/'residual-demands.json'),str(registry),str(plan)],check=True)
 result=read(plan);need(result['RegistrySha256']==binding['RegistrySha256'] and result['DistinctSymbolClocks']==len(demands),'HELD_RESIDUAL_NATIVE_ASSESSMENT_BINDING')
 # Positive prefixes, complete intervals, and authenticated absence all remain
 # reusable. No missing-window diagnosis may authorize recollecting them.
 base=read(coverage_folder/'collection-coverage.json');supplement=read(coverage_folder/'remaining-source-summary.json')
 coverage=dict(Rows=base['Rows']+supplement['Coverage'])
 for i,g in enumerate(result['Groups']):
  for side in ('BID','ASK'):coverage['Rows'].append(dict(Group='residual/'+str(i),Symbol=g['Symbol'],Side=side,Mode=g['Mode'],
   From=g['From'],Through=g['Through'],Complete=False,AuthenticAbsence=False,MissingWindows=[[g['From'],g['Through']]]))
 prefixes=read(registry)['Rows'];targets=remaining.pending_targets(coverage,prefixes);write(REPORT/'additional-uncollected-targets.json',targets)
 counts=collections.Counter(r['Status'] for r in result['Assessments'])
 write(REPORT/'summary.json',dict(Study='OWNER_HELD_RESIDUAL_CHECK_1',Scope=scope,Prior=binding,OriginalBooksWithExactHeldCountParity=books,
  ResidualBookPoints=points,DistinctHeldSymbolMoments=len(demands),CurrentlyCostValuableSymbolMoments=result['ResolvedBefore'],
  SourceAssessmentCounts=dict(counts),NativeUnresolvedSourceGroups=len(result['Groups']),AdditionalUncollectedSideWindows=len(targets),
  OriginalCashAndEventChainsPreserved=True,SourceBrokerRequests=0,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))
 print('HELD_RESIDUAL_CLASSIFIED',scope,books,points,len(demands),dict(counts),'NEW_UNCOLLECTED_WINDOWS',len(targets),flush=True)
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','inspect']);p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
 if a.stage=='check':check()
 else:inspect(a.work,a.scope)
if __name__=='__main__':main()

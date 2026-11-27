"""Recover an interrupted frozen-book calculation without recollecting prices.
Complete the unchanged registered NET experiment, which has not executed.
"""
import argparse,json,os,subprocess
from pathlib import Path
from . import owner_held_equity_recovery as held
from . import owner_path_distribution_economic as economic
from .owner_earlier_lifecycle_digest_recovery import verified_download
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/held_financial_recovery_1.json');LOCAL=Path('completed-held-registry')
def write(path,value):Path(path).write_text(exact_json(value)+'\n')
def check():
 p=read(REGISTRY)
 need(p['Study']=='OWNER_HELD_FINANCIAL_RECOVERY_1' and p['InterruptedRun']==45983234609 and
  p['RepriceScopes']==['earlier'] and p['EconomicScopes']==['earlier','recent'] and
  p['EconomicRegistrationSha256']==sha(economic.REGISTRY) and p['SourceBrokerRequests']==p['Orders']==p['OriginalPoliciesReplayed']==0
  and not p['CloudActivated'],'HELD_FINANCIAL_RECOVERY_REGISTRATION')
 return p

def source():
 p=check();spec=p['GlobalVerifiedRegistry']
 state=json.loads(subprocess.check_output(['gh','api',f'repos/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{spec["Run"]}']))
 need(state['head_sha']==p['InterruptedHead'] and state['head_branch']=='main','HELD_FINANCIAL_UPSTREAM_REVISION')
 verified_download(spec['Artifact'],spec['Run'],spec['ArchiveSha256'],LOCAL)
 original=read(LOCAL/'remaining-source-summary.json');prior=read(LOCAL/'recent-summary.json')
 need(original['RunId']==str(p['InterruptedRun']) and original['OriginalCaptureRun']==45973360072 and
  original['ProvenPrefixes']==3068616 and original['IncompleteSides']==original['MissingRequestWindows']==0 and
  prior['Scope']=='recent' and prior['UnknownBefore']==30510 and prior['RecoveredEquityPoints']==27723 and
  prior['OriginalPoliciesReplayed']==prior['Orders']==0 and not prior['CloudActivated'],'HELD_FINANCIAL_VERIFIED_GLOBAL_SOURCE')
 binding=dict(spec,Head=p['InterruptedHead'],RegistrySha256=sha(LOCAL/'verified-valuation-registry.json'))
 original.update(RunId=os.environ['GITHUB_RUN_ID'],UpstreamRun=p['InterruptedRun'],SourceRegistryBinding=binding,
  TechnicalRebindOnly=True,SourceBrokerRequests=0)
 write(LOCAL/'remaining-source-summary.json',original)
 return p,original

def reprice(work):
 p,original=source();held.REPORT.mkdir();registry=held.REPORT/'verified-valuation-registry.json'
 import shutil
 shutil.copyfile(LOCAL/'verified-valuation-registry.json',registry)
 held.reprice_saved_books(work,'earlier',registry,6578,3068616,3844)
 write(held.REPORT/'remaining-source-summary.json',dict(original,Scope='earlier'))
 write(held.REPORT/'technical-recovery-provenance.json',dict(Study=p['Study'],Run=os.environ['GITHUB_RUN_ID'],Head=os.environ['GITHUB_SHA'],
  InterruptedRun=p['InterruptedRun'],InterruptedJob=p['InterruptedJob'],VerifiedSource=original['SourceRegistryBinding'],
  SuccessfulRecentBooksReplayed=0,SourceBrokerRequests=0,OriginalPoliciesReplayed=0,Orders=0,CloudActivated=False))

def main():
 a=argparse.ArgumentParser();a.add_argument('stage',choices=['check','reprice','economic']);a.add_argument('--scope',choices=['earlier','recent']);a.add_argument('--work',type=Path);v=a.parse_args()
 if v.stage=='check':check()
 elif v.stage=='reprice':reprice(v.work)
 else:source();economic.evaluate(v.work,v.scope,LOCAL)
if __name__=='__main__':main()

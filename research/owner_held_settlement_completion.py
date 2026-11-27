"""Technical continuation of conserved capture and unexecuted NET comparison.
The broker receives only windows absent from the authenticated prior coverage.
"""
import argparse,os
from pathlib import Path
from . import owner_held_equity_readback as readback
from . import owner_held_equity_recovery as original
from . import owner_held_remaining_source as remaining
from . import owner_path_distribution_economic as economic
from .merge_eur_scenarios import read
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/held_settlement_completion_1.json')
def check():
 p=read(REGISTRY)
 need(p['Study']=='OWNER_HELD_SETTLEMENT_COMPLETION_1' and p['OriginalCaptureRun']==45973360072 and
  p['Scopes']==['earlier','recent'] and p['Orders']==p['OriginalPoliciesReplayed']==0 and not p['CloudActivated'] and
  p['EconomicRegistrationSha256']==sha(economic.REGISTRY),'HELD_COMPLETION_REGISTRATION')
 return p
def prepare():
 p=check();readback.execute(None,None,sources_only=True)
 proof=read(original.REPORT/'readback-provenance.json')
 need(sorted(proof['Artifacts'],key=lambda a:a['Id'])==sorted(p['OriginalArtifacts'],key=lambda a:a['Id']),
  'HELD_COMPLETION_CAPTURE_ARTIFACTS')
 remaining.prepare(original.REPORT,dict(Run=os.environ['GITHUB_RUN_ID'],Head=os.environ['GITHUB_SHA'],
  SourceOnly=True,ReadbackProvenanceSha256=sha(original.REPORT/'readback-provenance.json')))
def main():
 p=argparse.ArgumentParser();p.add_argument('stage',choices=['check','prepare','economic']);p.add_argument('--scope',choices=['earlier','recent']);p.add_argument('--work',type=Path);a=p.parse_args()
 check()
 if a.stage=='prepare':prepare()
 elif a.stage=='economic':economic.evaluate(a.work,a.scope,Path('completed-held-registry'))
if __name__=='__main__':main()

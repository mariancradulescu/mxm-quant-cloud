"""Inspect remaining earlier valuations after the interrupted runner was recovered."""
import argparse,os
from pathlib import Path
from . import owner_held_residual_check as inspection
from .owner_held_residual_recovery import download
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/held_earlier_residual_2.json')
def check():
 p=read(REGISTRY);need(p['Study']=='OWNER_HELD_EARLIER_RESIDUAL_2' and p['Scope']=='earlier' and
  p['Prior']['Run']==45993633142 and p['PriorUnknown']==1254 and
  p['SourceBrokerRequests']==p['Orders']==p['OriginalPoliciesReplayed']==0 and not p['CloudActivated'],'EARLIER_RESIDUAL_REGISTRATION');return p
def inspect(work):
 p=check();work.mkdir(mode=0o700,parents=True);prior=work/'prior';coverage=work/'coverage'
 download(p['Prior'],prior);download(p['Coverage'],coverage)
 summary=read(prior/'earlier-summary.json');need(summary['UnknownAfter']==p['PriorUnknown'] and summary['RecoveredEquityPoints']==39827,
  'EARLIER_RESIDUAL_RECOVERED_BINDING')
 need(sha(prior/'verified-valuation-registry.json')==sha(coverage/'verified-valuation-registry.json'),'EARLIER_RESIDUAL_SAME_GLOBAL_REGISTRY')
 binding=dict(p['Prior'],RegistrySha256=sha(prior/'verified-valuation-registry.json'))
 inspection.inspect_conserved(work,'earlier',binding,prior,coverage)
 r=read(inspection.REPORT/'summary.json');r.update(Study=p['Study'],CoverageBinding=p['Coverage'])
 (inspection.REPORT/'summary.json').write_text(exact_json(r)+'\n')
def main():
 a=argparse.ArgumentParser();a.add_argument('stage',choices=['check','inspect']);a.add_argument('--work',type=Path);v=a.parse_args()
 if v.stage=='check':check()
 else:inspect(v.work)
if __name__=='__main__':main()

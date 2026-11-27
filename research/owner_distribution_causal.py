"""Distinct causal correction; the closed original result remains conserved."""
import argparse
from pathlib import Path
from . import owner_distribution_path as parent
from .merge_eur_scenarios import read,exact_json
from .verified_research_cache import sha
from .decode import need
REGISTRY=Path('research/distribution_path_causal_2.json')
def check():
 p=read(REGISTRY)
 need(p['Study']=='OWNER_DISTRIBUTION_PATH_CAUSAL_2' and p['SourceRegistrationSha256']==sha(parent.REGISTRY) and
  p['OriginalResultRun']==45977053433 and p['SourceBrokerRequests']==p['Orders']==0 and not p['CloudActivated'] and
  p['SelectionMultiplicity']==6,'CAUSAL_PATH_CORRECTION_REGISTRATION');return p
def main():
 a=argparse.ArgumentParser();a.add_argument('stage',choices=['check','annual']);a.add_argument('--work',type=Path);v=a.parse_args();p=check()
 if v.stage=='check':return
 parent.annual(v.work,causal_correction=True);result=read(parent.REPORT/'annual-distribution.json')
 need(result['Study']==p['Study'] and result['PeerMembershipUsesClosedContextsOnly'] and result['SelectionMultiplicity']==6,'CAUSAL_PATH_RESULT_BINDING')
 (parent.REPORT/'causal-correction-provenance.json').write_text(exact_json(dict(Registration=p,RegistrationSha256=sha(REGISTRY),
  OriginalResultUnaffected=False,OriginalRawReferenceUnaffected=True,OriginalReportConserved=True,SourceBrokerRequests=0,Orders=0,CloudActivated=False))+'\n')
if __name__=='__main__':main()

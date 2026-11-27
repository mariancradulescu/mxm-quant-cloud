"""Next census tranche, determined causally by the immutable verified census."""
import json
from pathlib import Path
from . import owner_eur_recent_continuous as recent
from .owner_official_breadth_extension import choose
from . import source_history_universe as src
from .decode import need

REGISTRY=Path('research/official_breadth_extension_7.json')

def bind(p,prior,receipt,census):
    need(p['Study']=='OFFICIAL_BREADTH_EXTENSION_7' and p['Exposure']=='DEVELOPMENT_ONLY_NO_INDEPENDENT_CLAIM'
         and p['ExistingUniverse']==sorted(prior['ExistingUniverse']+prior['New'])
         and len(p['ExistingUniverse'])==len(set(p['ExistingUniverse']))==41
         and receipt['Study']==prior['Study'] and receipt['orders']==0 and not receipt['cloudActivated']
         and set(receipt['economicCoverage'])==set(prior['New'])
         and p['Base']==[] and p['NextCount']==4
         and p['Windows']==[
             dict(Id='NOV24_ANNUAL_CONTEXT',From='2026-11-24',To='2026-11-25'),
             dict(Id='AUG12_EXECUTION',From='2026-08-12',To='2026-08-13'),
             dict(Id='FEB12_EXECUTION',From='2026-02-12',To='2026-02-13')]
         and p['WarmFrom']=='2025-11-01' and p['PageHours']==4 and p['PerPartitionMaxRequests']==1000
         and p['PerPartitionSeconds']==1080 and p['PerSidePageBudget']==450
         and p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'BREADTH_7_SCOPE')
    names=choose(census,p['ExistingUniverse'])
    need(len(names)==len(set(names))==4 and not set(names)&set(p['ExistingUniverse']),'BREADTH_7_NEW_NAMES')
    return dict(p,New=names)

def registered():
    p=json.loads(REGISTRY.read_bytes())
    raw=Path('eer1-economic/source-census.json').read_bytes()
    need(src.digest(raw)==p['PriorCensusSha256'],'BREADTH_7_CENSUS_IDENTITY')
    prior=json.loads(Path('research/official_breadth_extension_6.json').read_bytes())
    receipt=json.loads(Path('prior-breadth-verified/breadth-extension-6-source-summary.json').read_bytes())
    bound=bind(p,prior,receipt,json.loads(raw))
    return bound,src.digest(json.dumps(bound,sort_keys=True,separators=(',',':')).encode())

def main():
    recent.registered=registered
    recent.main()

if __name__=='__main__':main()

"""New historical tranche, not a replay or renewed test of official capabilities."""
import json
from pathlib import Path
from . import owner_eur_recent_continuous as recent
from .owner_official_breadth_extension import choose
from . import source_history_universe as src
from .decode import need

REGISTRY=Path('research/official_breadth_extension_4.json')

def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    census_raw=Path('eer1-economic/source-census.json').read_bytes();census=json.loads(census_raw)
    prior=json.loads(Path('research/official_breadth_extension_3.json').read_bytes())
    need(src.digest(census_raw)==p['PriorCensusSha256'] and p['Study']=='OFFICIAL_BREADTH_EXTENSION_4_EARLIER_EXECUTION' and
         p['ExistingUniverse']==sorted(prior['ExistingUniverse']+prior['New']) and len(p['ExistingUniverse'])==29 and
         choose(census,p['ExistingUniverse'])==p['New'] and p['Base']==[] and len(p['New'])==4 and
         p['Windows']==[
             dict(Id='NOV25_26_ANNUAL_CONTEXT',From='2026-11-25',To='2026-11-26'),
             dict(Id='NOV2025_10',From='2025-11-10',To='2025-11-11'),
             dict(Id='FEB2026_09',From='2026-02-09',To='2026-02-10'),
             dict(Id='MAY2026_11',From='2026-05-11',To='2026-05-12'),
             dict(Id='AUG2026_10',From='2026-08-10',To='2026-08-11')] and
         p['WarmFrom']=='2025-11-01' and p['PageHours']==4 and p['PerPartitionMaxRequests']==1000 and
         p['PerPartitionSeconds']==1080 and p['PerSidePageBudget']==450 and
         p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'BREADTH_4_CENSUS_AND_SCOPE')
    return p,src.digest(raw)

def main():
    recent.registered=registered
    recent.main()
if __name__=='__main__':main()

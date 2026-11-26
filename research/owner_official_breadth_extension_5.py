"""Next official census tranche plus a bounded new BRF.US coverage window."""
import json
from pathlib import Path
from . import owner_eur_recent_continuous as recent
from .owner_official_breadth_extension import choose
from . import source_history_universe as src
from .decode import need

REGISTRY=Path('research/official_breadth_extension_5.json')
def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    census_raw=Path('eer1-economic/source-census.json').read_bytes();census=json.loads(census_raw)
    prior=json.loads(Path('research/official_breadth_extension_4.json').read_bytes())
    need(src.digest(census_raw)==p['PriorCensusSha256'] and p['Study']=='OFFICIAL_BREADTH_EXTENSION_5_BRF_COMPLETION'
         and p['ExistingUniverse']==sorted(prior['ExistingUniverse']+prior['New']) and len(p['ExistingUniverse'])==33
         and choose(census,p['ExistingUniverse'])==p['New'] and p['New']==['AUDUSD','HK50','Corn','TRUMPUSD']
         and p['Base']==['BRF.US'] and p['Base'][0] in p['ExistingUniverse']
         and p['Windows']==[dict(Id='NOV24_25_ANNUAL_CONTEXT',From='2026-11-24',To='2026-11-25'),
             dict(Id='NOV17_24_BRF_COMPLETION',From='2026-11-17',To='2026-11-24')]
         and p['WarmFrom']=='2025-11-01' and p['PageHours']==4 and p['PerPartitionMaxRequests']==1000
         and p['PerPartitionSeconds']==1080 and p['PerSidePageBudget']==450
         and p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'BREADTH_5_CENSUS_SCOPE')
    return p,src.digest(raw)
def main():
    recent.registered=registered
    recent.main()
if __name__=='__main__':main()

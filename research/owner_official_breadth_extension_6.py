"""Next verified census tranche with annual bars and two distinct execution days."""
import json
from pathlib import Path
from . import owner_eur_recent_continuous as recent
from .owner_official_breadth_extension import choose
from . import source_history_universe as src
from .decode import need

REGISTRY=Path('research/official_breadth_extension_6.json')

def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    census_raw=Path('eer1-economic/source-census.json').read_bytes();census=json.loads(census_raw)
    prior=json.loads(Path('research/official_breadth_extension_5.json').read_bytes())
    receipt=json.loads(Path('prior-breadth-verified/breadth-extension-5-source-summary.json').read_bytes())
    need(receipt['Study']==prior['Study'] and receipt['planned']==receipt['verified']==11 and not receipt['pending']
         and all(receipt['economicCoverage'][n]=='AUTHENTIC_BARS_AND_MONETARY_MARKS_COLLECTED' for n in prior['New']),
         'BREADTH_6_PREVIOUS_CAPTURE_COMPLETE')
    need(src.digest(census_raw)==p['PriorCensusSha256'] and p['Study']=='OFFICIAL_BREADTH_EXTENSION_6'
         and p['Exposure']=='DEVELOPMENT_ONLY_NO_INDEPENDENT_CLAIM'
         and p['ExistingUniverse']==sorted(prior['ExistingUniverse']+prior['New']) and len(p['ExistingUniverse'])==37
         and choose(census,p['ExistingUniverse'])==p['New'] and p['New']==['AIXAd.DE','EIDO.US','XAUUSD-F','USDCHF']
         and p['Base']==[] and p['Windows']==[
             dict(Id='NOV26_27_ANNUAL_CONTEXT',From='2026-11-26',To='2026-11-27'),
             dict(Id='MAY2026_12_EXECUTION',From='2026-05-12',To='2026-05-13')]
         and p['WarmFrom']=='2025-11-01' and p['PageHours']==4 and p['PerPartitionMaxRequests']==1000
         and p['PerPartitionSeconds']==1080 and p['PerSidePageBudget']==450
         and p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'BREADTH_6_CENSUS_SCOPE')
    return p,src.digest(raw)

def main():
    recent.registered=registered
    recent.main()

if __name__=='__main__':main()

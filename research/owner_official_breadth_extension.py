"""Reuse the account-bound official collector for the next census tranche.

Only the entry point's registry binding changes. All outbound allowlists,
custody, complete-page verification and independent packet readback remain
the existing collector's implementation. No original registry is mutated.
"""
import json
from pathlib import Path

from . import owner_eur_recent_continuous as recent
from . import source_history_universe as src
from .decode import need

REGISTRY=Path('research/official_breadth_extension_2.json')


def choose(census,existing):
    return [name for name in census['pending'] if name not in existing][:4]


def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    census_raw=Path('eer1-economic/source-census.json').read_bytes()
    need(src.digest(census_raw)==p['PriorCensusSha256'],'BREADTH_EXTENSION_CENSUS_IDENTITY')
    census=json.loads(census_raw)
    need(p['Study']=='OFFICIAL_BREADTH_EXTENSION_2' and p['Exposure']=='DEVELOPMENT_ONLY_NO_INDEPENDENT_CLAIM' and
         p['Base']==[] and len(p['ExistingUniverse'])==len(set(p['ExistingUniverse']))==21 and
         choose(census,p['ExistingUniverse'])==p['New'] and len(p['New'])==4 and
         not set(p['New'])&set(p['ExistingUniverse']) and
         p['Windows']==[dict(Id='NOV23_25',From='2026-11-23',To='2026-11-25')] and
         p['WarmFrom']=='2026-11-01' and p['PageHours']==4 and
         p['PerPartitionMaxRequests']==1000 and p['PerPartitionSeconds']==1080 and p['PerSidePageBudget']==450 and
         p['Orders']==0 and p['CloudActivated'] is p['IndependentConfirmationCertified'] is False,
         'BREADTH_EXTENSION_REGISTRY')
    return p,src.digest(raw)


def main():
    # Runtime dependency injection uses the existing implementation, including
    # read-only scope checks. Neither old module source nor protocol is edited.
    recent.registered=registered
    recent.main()


if __name__=='__main__':main()

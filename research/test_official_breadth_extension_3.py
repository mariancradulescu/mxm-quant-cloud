import json
from pathlib import Path
import unittest
from .owner_official_breadth_extension import choose
from .owner_eur_recent_continuous import metadata_summary,utc

class NextBreadth(unittest.TestCase):
    def test_scope_is_additive_and_not_performance_selected(self):
        p=json.loads(Path('research/official_breadth_extension_3.json').read_bytes())
        self.assertEqual(choose(dict(pending=p['ExistingUniverse']+p['New']+['LATER']),p['ExistingUniverse']),p['New'])
        self.assertEqual(len(set(p['ExistingUniverse']+p['New'])),29)
        self.assertGreaterEqual(utc(p['Windows'][0]['To'])-utc(p['WarmFrom']),365*86400000)
        prior=json.loads(Path('research/official_breadth_extension_2.json').read_bytes())
        self.assertEqual(p['Windows'][0]['From'],prior['Windows'][-1]['To'])

    def test_only_additions_get_annual_bars_and_routes_extend_the_source(self):
        p=json.loads(Path('research/official_breadth_extension_3.json').read_bytes())
        meta=dict(roster={n:dict(id=i+1,enabled=True) for i,n in enumerate(p['New']+['EURUSD'])},
                  routes={'USD':[dict(Symbol='EURUSD')]},terms={},margin={})
        summary=metadata_summary(p,'a'*64,meta,'1')
        self.assertEqual(len(summary['partitions']),5)
        self.assertEqual(sum(t['bars'] for t in summary['partitions']),4)
        for target in summary['partitions']:
            self.assertEqual(target['fromInclusive'],utc('2026-11-25'))
            self.assertEqual(target['throughExclusive'],utc('2026-11-26'))
            if target['bars']:self.assertEqual(target['barFrom'],utc('2025-11-01'))

if __name__=='__main__':unittest.main()

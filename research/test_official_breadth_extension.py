import json
from pathlib import Path
import unittest
from .owner_official_breadth_extension import choose
from .owner_eur_recent_continuous import metadata_summary


class BreadthExtension(unittest.TestCase):
    def test_census_order_without_performance_selection(self):
        p=json.loads(Path('research/official_breadth_extension_2.json').read_bytes())
        census=dict(pending=p['ExistingUniverse'][:2]+p['New']+['LATER'],
            profits={p['New'][0]:-999,'LATER':999})
        self.assertEqual(choose(census,p['ExistingUniverse']),p['New'])
        self.assertEqual(len(set(p['ExistingUniverse']+p['New'])),25)

    def test_only_new_markets_and_required_conversion_are_requested(self):
        p=json.loads(Path('research/official_breadth_extension_2.json').read_bytes())
        roster={name:dict(id=i,enabled=True) for i,name in enumerate(p['ExistingUniverse']+p['New'],1)}
        meta=dict(roster=roster,terms={},margin={},routes={'USD':[dict(Symbol='EURUSD')]})
        summary=metadata_summary(p,'a'*64,meta,'SYNTHETIC')
        self.assertEqual(set(summary['chosen']),set(p['New']))
        self.assertEqual({t['symbol'] for t in summary['partitions']},set(p['New']+['EURUSD']))
        self.assertEqual(sum(t['bars'] for t in summary['partitions']),4)
        self.assertTrue(all(t['throughExclusive']-t['fromInclusive']==2*recent_day for t in summary['partitions']))


recent_day=86_400_000
if __name__=='__main__':unittest.main()

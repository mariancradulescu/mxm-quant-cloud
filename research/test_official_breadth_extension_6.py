import json,unittest
from pathlib import Path
from .owner_official_breadth_extension import choose
from . import owner_official_breadth_extension_6 as extension

class NextBreadth(unittest.TestCase):
    def test_only_uncollected_census_names_and_separate_closed_windows(self):
        p=json.loads(extension.REGISTRY.read_bytes())
        old=json.loads(Path('research/official_breadth_extension_5.json').read_bytes())
        self.assertEqual(p['ExistingUniverse'],sorted(old['ExistingUniverse']+old['New']))
        self.assertEqual(len(p['ExistingUniverse']),37)
        self.assertFalse(set(p['ExistingUniverse'])&set(p['New']))
        self.assertEqual(choose({'pending':p['ExistingUniverse']+p['New']},p['ExistingUniverse']),p['New'])
        self.assertLess(p['Windows'][1]['To'],p['Windows'][0]['From'])
        self.assertEqual(p['Windows'][0]['To'],'2026-11-27')
        self.assertEqual(p['Orders'],0)
        self.assertFalse(p['IndependentConfirmationCertified'])

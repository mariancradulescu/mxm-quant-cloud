import json,unittest
from pathlib import Path
from .owner_official_breadth_extension import choose
from . import owner_official_breadth_extension_5 as extension
class NextBreadth(unittest.TestCase):
    def test_scope(self):
        p=json.loads(extension.REGISTRY.read_bytes())
        old=json.loads(Path('research/official_breadth_extension_4.json').read_bytes())
        self.assertEqual(p['ExistingUniverse'],sorted(old['ExistingUniverse']+old['New']))
        self.assertEqual(len(p['ExistingUniverse']),33)
        self.assertFalse(set(p['ExistingUniverse'])&set(p['New']))
        self.assertEqual(p['Base'],['BRF.US'])
        self.assertEqual(choose({'pending':p['ExistingUniverse']+p['New']},p['ExistingUniverse']),p['New'])
        self.assertEqual(p['Windows'][1]['To'],p['Windows'][0]['From'])
        self.assertFalse(p['IndependentConfirmationCertified'])

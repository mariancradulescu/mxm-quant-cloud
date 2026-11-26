import json,unittest
from pathlib import Path
from .owner_official_breadth_extension import choose
from . import owner_official_breadth_extension_4 as extension

class EarlierBreadth(unittest.TestCase):
    def test_new_tranche_and_windows(self):
        p=json.loads(extension.REGISTRY.read_bytes())
        old=json.loads(Path('research/official_breadth_extension_3.json').read_bytes())
        self.assertEqual(p['ExistingUniverse'],sorted(old['ExistingUniverse']+old['New']))
        self.assertEqual(len(p['ExistingUniverse']),29)
        self.assertEqual(len(p['New']),4)
        self.assertFalse(set(p['New'])&set(p['ExistingUniverse']))
        self.assertEqual(len(p['Windows']),5)
        self.assertEqual(p['Windows'][0]['To'],'2026-11-26')
        self.assertTrue(all(w['To']<'2026-10-01' for w in p['Windows'][1:]))
        self.assertEqual(choose({'pending':p['ExistingUniverse']+p['New']},p['ExistingUniverse']),p['New'])
        self.assertFalse(p['IndependentConfirmationCertified'])

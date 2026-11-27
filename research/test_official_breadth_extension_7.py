import json,unittest
from pathlib import Path
from . import owner_official_breadth_extension_7 as e

class NextBreadth(unittest.TestCase):
    def test_deterministic_next_tranche_does_not_discard_partial_prior_coverage(self):
        p=json.loads(e.REGISTRY.read_bytes())
        prior=json.loads(Path('research/official_breadth_extension_6.json').read_bytes())
        receipt=dict(Study=prior['Study'],orders=0,cloudActivated=False,
            economicCoverage={n:'VERIFIED_RESPONSE_WITH_INCOMPLETE_ECONOMIC_COVERAGE' for n in prior['New']})
        names=['synthetic-A','synthetic-B','synthetic-C','synthetic-D','synthetic-E']
        bound=e.bind(p,prior,receipt,{'pending':p['ExistingUniverse']+names})
        self.assertEqual(bound['New'],names[:4])
        self.assertEqual(len(bound['ExistingUniverse']),41)
        self.assertFalse(set(bound['New'])&set(bound['ExistingUniverse']))
        self.assertFalse(bound['IndependentConfirmationCertified'])

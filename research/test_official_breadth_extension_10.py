import json,unittest
from pathlib import Path
from . import owner_official_breadth_extension_10 as e

class NextBreadth(unittest.TestCase):
    def test_next_names_preserve_prior_partial_coverage(self):
        p=json.loads(e.REGISTRY.read_bytes())
        prior=json.loads(Path('research/official_breadth_extension_9.json').read_bytes())
        receipt=dict(Study=prior['Study'],orders=0,cloudActivated=False,planned=21,verified=21,pending=[],
            economicCoverage={n:'VERIFIED_RESPONSE_WITH_INCOMPLETE_ECONOMIC_COVERAGE' for n in p['PriorNames']})
        names=p['New']+['synthetic-E']
        bound=e.bind(p,prior,receipt,{'pending':prior['ExistingUniverse']+p['PriorNames']+names})
        self.assertEqual(bound['New'],names[:4])
        self.assertEqual(len(bound['ExistingUniverse']),53)
        self.assertFalse(set(bound['New'])&set(bound['ExistingUniverse']))
        self.assertFalse(bound['IndependentConfirmationCertified'])

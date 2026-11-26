import json,tempfile,unittest
from pathlib import Path
from .test_causal_source_shards import CipherShards
from .owner_causal_source_shards import partition_checkpoint
from .owner_generalized_cipher_shards import publication_action,UPLOAD

class GeneralCipherShards(unittest.TestCase):
    def test_more_than_three_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);CipherShards().fixture(root/'input')
            plan=partition_checkpoint(root/'input',root/'output',20)
            self.assertEqual(len(plan['Shards']),6)
            steps=publication_action(plan,root/'output',root/'action')
            self.assertEqual(len(steps),7)
            self.assertEqual([s['uses'] for s in steps[:-1]],[UPLOAD]*6)
            self.assertEqual(len(steps[-1]['env']),12)
            self.assertIn('PART5_SHA',steps[-1]['env'])
            self.assertEqual(json.loads((root/'action/action.yml').read_text())['runs']['steps'],steps)

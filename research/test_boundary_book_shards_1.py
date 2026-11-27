import json,tempfile,unittest
from pathlib import Path
from .owner_boundary_book_shards_1 import rewrite_publication

class BoundaryBookPublication(unittest.TestCase):
    def test_upload_receipt_retains_the_boundary_input_identity_in_its_new_process(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'action.yml'
            p.write_text(json.dumps(dict(runs=dict(steps=[
                dict(uses='PINNED',with_={}),
                dict(run='python -m research.owner_generalized_cipher_shards receipt')]))))
            rewrite_publication(p)
            self.assertEqual(json.loads(p.read_bytes())['runs']['steps'][1]['run'],
                'python -m research.owner_boundary_book_shards_1 receipt')

    def test_an_unbound_receipt_command_cannot_publish_another_archive_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'action.yml';p.write_text(json.dumps(dict(runs=dict(steps=[]))))
            with self.assertRaisesRegex(ValueError,'BOUNDARY_BOOK_RECEIPT_PROCESS_BINDING'):
                rewrite_publication(p)

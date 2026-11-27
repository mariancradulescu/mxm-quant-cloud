import json,tempfile,unittest
from pathlib import Path
from . import owner_net_horizon_book_shards as h

class NetBookShards(unittest.TestCase):
    def test_scope_specific_publication_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'action.yml'
            for scope in h.SOURCES:
                p.write_text(json.dumps(dict(runs=dict(steps=[
                    {'uses':'PINNED','with':{'name':'lifecycle-general-data-0'}},
                    {'run':'python -m research.owner_generalized_cipher_shards receipt'}]))))
                h.rewrite_publication(p,scope)
                s=json.loads(p.read_bytes())['runs']['steps']
                self.assertEqual(s[0]['with']['name'],f'net-horizon-{scope}-books-data-0')
                self.assertEqual(s[1]['run'],f'python -m research.owner_net_horizon_book_shards receipt --scope {scope}')

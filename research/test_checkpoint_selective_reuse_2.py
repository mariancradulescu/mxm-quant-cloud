import unittest
from .owner_checkpoint_selective_reuse_2 import selection

class SelectiveReuse(unittest.TestCase):
    def setUp(self):
        self.receipt={'ExpectedFiles':2,'Files':[
            {'Path':'source.json','Bytes':2,'Parts':[{'File':'part-000001.sealed','Offset':0,'Bytes':2,'CipherSha256':'a'}]},
            {'Path':'books/x.json','Bytes':3,'Parts':[{'File':'part-000002.sealed','Offset':0,'Bytes':3,'CipherSha256':'b'}]}]}
        self.plan={'Shards':[{'Index':0,'Files':[{'File':'part-000001.sealed','CipherSha256':'a'}]},
                            {'Index':1,'Files':[{'File':'part-000002.sealed','CipherSha256':'b'}]}]}
    def test_select_only_required_shard(self):
        wanted,groups=selection(self.receipt,self.plan,['books/x.json'])
        self.assertEqual(wanted,{'part-000002.sealed':'b'})
        self.assertEqual([g['Index'] for g in groups],[1])
    def test_reject_unknown_file(self):
        with self.assertRaises(ValueError):selection(self.receipt,self.plan,['missing'])
    def test_reject_missing_unselected_manifest_part(self):
        self.plan['Shards'].pop()
        with self.assertRaises(ValueError):selection(self.receipt,self.plan,['source.json'])
    def test_reject_mismatched_cipher_identity(self):
        self.plan['Shards'][0]['Files'][0]['CipherSha256']='wrong'
        with self.assertRaises(ValueError):selection(self.receipt,self.plan,['books/x.json'])

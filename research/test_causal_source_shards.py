import hashlib,json,tempfile,unittest
from pathlib import Path
from .owner_causal_source_shards import partition_checkpoint

class CipherShards(unittest.TestCase):
    def fixture(self,root):
        root.mkdir();(root/'manifest.sealed').write_bytes(b'SYNTHETIC_OPAQUE_MANIFEST')
        parts=[]
        for i in range(6):
            name=f'part-{i:06d}.sealed';data=bytes([i])*20;(root/name).write_bytes(data)
            parts.append(dict(File=name,Offset=i*20,Bytes=20,CipherSha256=hashlib.sha256(data).hexdigest()))
        receipt=dict(Complete=True,ExpectedFiles=1,Files=[dict(Path='source.json',Bytes=120,Parts=parts)],
            Orders=0,CloudActivated=False,ManifestCipherSha256=hashlib.sha256((root/'manifest.sealed').read_bytes()).hexdigest(),
            RunId='1',SourceSha256='0'*64,ProtocolSha256='1'*64)
        (root/'checkpoint-receipt.json').write_text(json.dumps(receipt))

    def test_shards_are_bounded_and_preserve_every_original_cipher_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root/'input');plan=partition_checkpoint(root/'input',root/'output',50)
            self.assertEqual(len(plan['Shards']),3)
            self.assertEqual(plan['Decryptions'],0)
            for group in plan['Shards']:
                self.assertLessEqual(group['Bytes'],50)
                for part in group['Files']:
                    self.assertEqual((root/'input'/part['File']).read_bytes(),
                        (root/'output'/f"parts{group['Index']}"/part['File']).read_bytes())
            (root/'input/part-000000.sealed').write_bytes(b'CORRUPTED')
            with self.assertRaises(ValueError):partition_checkpoint(root/'input',root/'bad',50)

if __name__=='__main__':unittest.main()

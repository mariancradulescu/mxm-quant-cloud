import unittest
from .guard import CaptureContractError
from .owner_official_breadth_spans import bounds,normalize_with_quarantine,fast_seal
class OfficialBarSpans(unittest.TestCase):
    def test_actual_bounds_do_not_infer_a_year_from_requested_dates(self):
        day=86400000;end=400*day
        short=bounds([[end-day,1]],'H1',end)
        full=bounds([[end-390*day,1],[end-day,1]],'H1',end)
        self.assertFalse(short['ReachesTwelveMonthStart'])
        self.assertTrue(full['ReachesTwelveMonthStart'])
        self.assertFalse(full['ContinuousCoverageCertified'])
        self.assertIsNone(bounds([],'M1',end)['FirstOpenAt'])
    def test_duplicate_and_forming_bars_are_rejected(self):
        with self.assertRaises(CaptureContractError):bounds([[1],[1]],'M5',1000000)
        with self.assertRaises(CaptureContractError):bounds([[900000]],'M5',1000000)
    def test_nominal_daily_overlap_is_preserved_and_both_members_are_quarantined(self):
        day=86400000
        rows=[[0,day,100,101,99,100,1],[day-3600000,2*day-3600000,100,101,99,100,1],
              [2*day,3*day,100,101,99,100,1]]
        clean,quality=normalize_with_quarantine(rows)
        self.assertEqual((len(clean),quality['QuarantinedRows']),(1,2))
        self.assertEqual(quality['OverlappingPairs'][0]['NominalOverlapMs'],3600000)
        self.assertEqual(len(rows),3)
    def test_fast_normalized_cache_preserves_all_original_bytes_and_bars(self):
        import tempfile,gzip,json
        from pathlib import Path
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        from .custody import unseal_new
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        payload=dict(OriginalNominalClosedRows={'SYNTH':{'D1':[[0,86400000,100,101,99,100,1]]}},ProtectionFiles={'fixture':'AAAAAQ=='})
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'normalized-source.sealed';receipt=fast_seal(path,payload,public,'1')
            decoded=json.loads(gzip.decompress(unseal_new(path.read_bytes(),private,'1')))
            self.assertEqual(decoded,payload)
            self.assertEqual(receipt['file'],path.name)

if __name__=='__main__':unittest.main()

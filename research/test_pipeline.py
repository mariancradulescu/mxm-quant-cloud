import json
import unittest
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from . import collect
from .custody import seal, unseal
from .guard import require_read_only_request, CaptureContractError
from .decode import decode_side
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e

class PipelineChecks(unittest.TestCase):
    def test_trade_and_envelope_rejected(self):
        for q in [m.ProtoOANewOrderReq(),m.ProtoOAClosePositionReq(),m.ProtoOACancelOrderReq(),m.ProtoOARefreshTokenReq()]:
            with self.assertRaises(CaptureContractError): require_read_only_request(q)
        q=m.ProtoOATraderReq(ctidTraderAccountId=1)
        q.payloadType=m.ProtoOANewOrderReq().payloadType
        with self.assertRaises(CaptureContractError): require_read_only_request(q)

    def test_explicit_scope_before_account_auth(self):
        class Fake:
            count=0
            def request(self,q):
                self.count+=1
                return m.ProtoOAApplicationAuthRes() if self.count==1 else m.ProtoOAGetAccountListByAccessTokenRes()
        fake=Fake()
        with patch.dict('os.environ',{'R3_CTRADER_CLIENT_ID':'test','R3_CTRADER_CLIENT_SECRET':'test','R3_CTRADER_ACCESS_TOKEN':'test','R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256':'0'*64}):
            with self.assertRaisesRegex(CaptureContractError,'SCOPE_NOT_EXPLICIT_VIEW'): collect.authenticate(fake)
        self.assertEqual(fake.count,2)

    def test_signed_tick_deltas(self):
        ticks=[e.ProtoOATickData(timestamp=1000,tick=100000),e.ProtoOATickData(timestamp=0,tick=-2),e.ProtoOATickData(timestamp=-10,tick=1)]
        self.assertEqual(decode_side(ticks,990,1000),[[990,99999],[1000,99998],[1000,100000]])

    def test_schema_completion(self):
        self.assertEqual(m.ProtoOAGetTrendbarsRes.DESCRIPTOR.fields_by_name['hasMore'].number,7)

    def test_custody_tamper_and_roundtrip(self):
        # Ephemeral in-memory fixture, never an application credential.
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        encrypted=seal(b'private-test-record',pub)
        self.assertEqual(unseal(encrypted,private),b'private-test-record')
        data=json.loads(encrypted); data['ciphertext']='AAAA'
        with self.assertRaises(Exception): unseal(json.dumps(data).encode(),private)

if __name__=='__main__': unittest.main()

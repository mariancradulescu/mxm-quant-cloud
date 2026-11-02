import json
import unittest
import os
import tempfile
import subprocess
import hashlib
from pathlib import Path
from unittest.mock import patch
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from . import collect
from .custody import seal, unseal
from .guard import require_read_only_request, CaptureContractError
from .decode import decode_side
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e

class PipelineChecks(unittest.TestCase):
    @unittest.skipUnless(Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists(), 'C# build required')
    def test_csharp_sealed_readback_pipeline(self):
        from . import readback
        root=Path.cwd()
        # Small causality fixture verifies the newly integrated serialization path.
        bundle={'schema':1,'source':'Pepperstone-cTrader-OpenAPI','readOnly':True,'start':0,'end':7200000,'bars':[dict(symbol='TEST',openTime=0,availableTime=3600000,open=100,high=102,low=99,close=101,tickVolume=2)],'raw':[]}
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            (folder/'src').symlink_to(root/'src',target_is_directory=True)
            p=folder/'source.json'; p.write_text(json.dumps(bundle,sort_keys=True))
            out=folder/'receipt.json'
            subprocess.run(['dotnet',str(root/'src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll'),str(p),str(out)],check=True)
            bundle['csharpReceipt']=json.loads(out.read_text())
            cipher=seal(json.dumps(bundle,sort_keys=True).encode(),pub)
            (folder/'sealed-output').mkdir()
            (folder/'sealed-output/source.envelope.json').write_bytes(cipher)
            (folder/'sealed-output/receipt.public.json').write_text(json.dumps({'ciphertextSha256':hashlib.sha256(cipher).hexdigest()}))
            try:
                os.chdir(folder)
                with patch.dict('os.environ',{'R3_CUSTODY_PRIVATE_KEY_PEM':private.decode()}): readback.main()
                self.assertEqual(json.loads(Path('readback.public.json').read_text())['status'],'CUSTODY_AND_CSHARP_READBACK_VERIFIED')
            finally: os.chdir(root)

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

    def test_bad_binding_never_authenticates_account(self):
        class Fake:
            count=0
            def request(self,q):
                self.count+=1
                if self.count==1: return m.ProtoOAApplicationAuthRes()
                if self.count==2: return m.ProtoOAGetAccountListByAccessTokenRes(permissionScope=e.SCOPE_VIEW)
                raise AssertionError('Account request must not be reached')
        fake=Fake()
        with patch.dict('os.environ',{'R3_CTRADER_CLIENT_ID':'test','R3_CTRADER_CLIENT_SECRET':'test','R3_CTRADER_ACCESS_TOKEN':'test','R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256':'invalid-fixture'}):
            with self.assertRaisesRegex(CaptureContractError,'ACCOUNT_BINDING_INVALID'): collect.authenticate(fake)
        self.assertEqual(fake.count,2)

    def test_credential_jobs_need_owner_main_request(self):
        # Static regression against accidentally exposing environment jobs on PR.
        # This is defense-in-depth, not a replacement for GitHub environment rules.
        workflow=Path('.github/workflows/verify.yml').read_text()
        self.assertEqual(workflow.count("github.actor == 'mariancradulescu'"),2)
        self.assertEqual(workflow.count("github.ref == 'refs/heads/main'"),2)
        self.assertEqual(workflow.count("needs.verify.outputs.authorized_source_request == 'true'"),2)
        self.assertIn('git diff-tree --no-commit-id --name-only -r HEAD',workflow)
        self.assertIn('grep -Fxq "ops/collect-request.txt"',workflow)
        self.assertIn('fetch-depth: 2',workflow)
        self.assertEqual(workflow.count("inputs.collect == true"),2)
        self.assertIn("needs.verify.result == 'success'",workflow)
        self.assertIn('permissions:\\n  contents: read'.replace('\\n','\n'),workflow)

    def test_schema_completion(self):
        self.assertEqual(m.ProtoOAGetTrendbarsRes.DESCRIPTOR.fields_by_name['hasMore'].number,7)

    def test_custody_tamper_and_roundtrip(self):
        # Ephemeral in-memory fixture, never an application credential.
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        pub=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        from .custody_preflight import verify
        self.assertEqual(verify(private,pub),'EXISTING_CUSTODY_KEY_VERIFIED_NOT_SOURCE_READBACK')
        self.assertEqual(verify(b'',pub),'CUSTODY_CONFIGURATION_MISSING')
        self.assertEqual(verify(b'invalid fixture',pub),'CUSTODY_PEM_INVALID_OR_ENCRYPTED')
        self.assertEqual(verify(private,Path('research/custody_public.pem').read_bytes()),'CUSTODY_EXISTING_RECIPIENT_MISMATCH')
        encrypted=seal(b'private-test-record',pub)
        self.assertEqual(unseal(encrypted,private),b'private-test-record')
        data=json.loads(encrypted); data['ciphertext']='AAAA'
        with self.assertRaises(Exception): unseal(json.dumps(data).encode(),private)

if __name__=='__main__': unittest.main()

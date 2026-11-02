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
from .custody import seal, unseal, seal_new, unseal_new
from .custody_new import emit_public, checked_public
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
            cipher=seal_new(json.dumps(bundle,sort_keys=True).encode(),pub,'42')
            (folder/'sealed-output').mkdir()
            (folder/'sealed-output/source.envelope.json').write_bytes(cipher)
            (folder/'sealed-output/receipt.public.json').write_text(json.dumps({'ciphertextSha256':hashlib.sha256(cipher).hexdigest()}))
            try:
                os.chdir(folder)
                with patch.dict('os.environ',{'R3_CUSTODY_PRIVATE_KEY_PEM':private.decode(),'GITHUB_RUN_ID':'42'}): readback.main()
                self.assertEqual(json.loads(Path('readback.public.json').read_text())['status'],'NEW_SOURCE_V2_CUSTODY_AND_CSHARP_READBACK_VERIFIED')
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

    def test_existing_fingerprint_format_is_strict_but_paste_safe(self):
        # Harmless synthetic fingerprint: never an account identifier.
        h="aB"*32
        expected=h.lower()
        for representation in (h, "  "+h+"  ", "'"+h+"'", '"'+h+'"',
            "`"+h+"`", "sha256:"+h,
            "ACCOUNT_FINGERPRINT_SHA256 = '"+h+"'",
            "R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256="+h):
            self.assertEqual(collect.normalize_binding(representation),expected)
        for invalid in ("", "wrong", "b"*63, "z"*64, "account_id="+h,
            "ACCOUNT_FINGERPRINT_SHA256 = short", "'"+h, h+"'", h+"junk"):
            with self.assertRaisesRegex(CaptureContractError, "ACCOUNT_BINDING_INVALID"):
                collect.normalize_binding(invalid)

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
            with self.assertRaisesRegex(CaptureContractError,'ACCOUNT_BINDING_FAILED'): collect.authenticate(fake)
        self.assertEqual(fake.count,2)

    def test_credential_jobs_need_owner_main_request(self):
        # Static regression against accidentally exposing environment jobs on PR.
        # This is defense-in-depth, not a replacement for GitHub environment rules.
        workflow=Path('.github/workflows/verify.yml').read_text()
        self.assertEqual(workflow.count("github.actor == 'mariancradulescu'"),3)
        self.assertEqual(workflow.count("github.ref == 'refs/heads/main'"),3)
        self.assertEqual(workflow.count("needs.verify.outputs.authorized_source_request == 'true'"),3)
        self.assertIn('git diff-tree --no-commit-id --name-only -r HEAD',workflow)
        self.assertIn('== "ops/collect-request.txt"',workflow)
        self.assertIn('fetch-depth: 2',workflow)
        self.assertEqual(workflow.count("inputs.collect == true"),3)
        self.assertIn("needs.verify.result == 'success'",workflow)
        self.assertIn('permissions:\\n  contents: read'.replace('\\n','\n'),workflow)

    def test_original_account_commitment_no_secret_override(self):
        # Pin was derived once from the ORIGINAL historical constant, not
        # from a token-supplied account or a mutable environment value.
        self.assertEqual(collect.HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT,
            "3e43fdd68b1cdcb030699c674bdd5e95f74c40984060847f3f9f290f29ce03d3")
        self.assertNotIn('secret("R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256")',
            Path('research/collect.py').read_text())
        self.assertIn('BOUND_LIVE_ACCOUNT_AUTH_VERIFIED',
            Path('research/collect.py').read_text())

    def test_installed_private_key_derived_new_recipient_and_tamper(self):
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private=key.private_bytes(serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            fingerprint=emit_public(private,folder,"42")
            public=checked_public(folder,"42")
            self.assertEqual(hashlib.sha256(key.public_key().public_bytes(
                serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo
            )).hexdigest(),fingerprint)
            self.assertEqual(unseal_new(seal_new(b"new-source",public,"42"),
                                       private,"42"),b"new-source")
            with self.assertRaisesRegex(ValueError,"CUSTODY_NEW_CROSS_RUN_REPLAY_BLOCKED"):
                unseal_new(seal_new(b"new-source",public,"42"),private,"43")
            with self.assertRaisesRegex(ValueError,"NEW_CUSTODY_RECIPIENT_RUN_MISMATCH"):
                checked_public(folder,"43")
            bogus=rsa.generate_private_key(public_exponent=65537,key_size=2048)
            other=bogus.private_bytes(serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
            with self.assertRaisesRegex(ValueError,"CUSTODY_NEW_RECIPIENT_MISMATCH"):
                unseal_new(seal_new(b"new-source",public,"42"),other,"42")

    def test_privileged_new_custody_gate_and_legacy_stability(self):
        workflow=Path('.github/workflows/verify.yml').read_text()
        self.assertIn('  custody_recipient:',workflow)
        self.assertIn('    needs: [verify, custody_recipient]',workflow)
        self.assertIn('NEW_SOURCE_V2',Path('research/readback.py').read_text())
        self.assertIn('checked_public(Path("new-source-recipient"),run_id)',
            Path('research/collect.py').read_text())
        self.assertNotIn('R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256: '+chr(36),
            workflow)
        # Legacy public recipient is unchanged: v2 may use different RSA key.
        self.assertTrue(Path('research/custody_public.pem').read_bytes().startswith(
            b'-----BEGIN PUBLIC KEY-----'))
        self.assertIn('CUSTODY_NEW_RECIPIENT_MISMATCH',
            Path('research/custody.py').read_text())

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

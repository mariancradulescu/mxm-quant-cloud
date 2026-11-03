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

    def test_broker_identity_readonly_allowlist(self):
        from .broker_identity_transport import require_read_only_request as identity_guard
        for q in [m.ProtoOAReconcileReq(ctidTraderAccountId=1),m.ProtoOAOrderListReq(ctidTraderAccountId=1,fromTimestamp=0,toTimestamp=1),m.ProtoOADealListReq(ctidTraderAccountId=1,fromTimestamp=0,toTimestamp=1,maxRows=1000)]:
            with self.assertRaises(CaptureContractError): require_read_only_request(q)
            identity_guard(q)
        for q in [m.ProtoOANewOrderReq(),m.ProtoOAClosePositionReq(),m.ProtoOARefreshTokenReq()]:
            with self.assertRaises(CaptureContractError): identity_guard(q)

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
        import re
        protected=[b for b in re.split(r'(?m)^  (?=[A-Za-z0-9_-]+:)',workflow)
                   if '\n    environment:' in b]
        self.assertGreaterEqual(len(protected),10)
        for block in protected:
            gate=block.split('    steps:',1)[0]
            self.assertIn("github.actor == 'mariancradulescu'",gate)
            self.assertIn("github.ref == 'refs/heads/main'",gate)
            self.assertIn('needs.verify',gate)
            self.assertIn('github.event_name',gate)
        self.assertEqual(workflow.count("needs.verify.outputs.authorized_source_request == 'true'"),3)
        self.assertIn('git diff-tree --no-commit-id --name-only -r HEAD',workflow)
        self.assertIn('== "ops/collect-request.txt"',workflow)
        self.assertIn('fetch-depth: 2',workflow)
        self.assertIn('authorized_relative_gross',workflow)
        self.assertIn('authorized_policy_attribution',workflow)
        self.assertIn('authorized_m15_anchor_net',workflow)
        self.assertIn('authorized_wick_net',workflow)
        self.assertIn('== "ops/m15-wick-net-request.txt"',workflow)
        self.assertIn('run-id: 41619870283',workflow)
        self.assertIn('python -m research.session_wick_net',workflow)
        self.assertIn('== "ops/m15-anchor-net-request.txt"',workflow)
        self.assertIn('python -m research.anchor_balance_net',workflow)
        self.assertIn('== "ops/volume-policy-attribution-request.txt"',workflow)
        self.assertIn('run-id: 41614667957',workflow)
        self.assertIn('== "ops/relative-gross-request.txt"',workflow)
        self.assertIn('run-id: 41476636915',workflow)
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

    @unittest.skipUnless(Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists(), 'C# build required')
    def test_same_native_replay_has_separate_observation_only_cold_score(self):
        # Synthetic fixture tests output mechanics only. Authentic source runs
        # solely in the protected, pinned, read-only GitHub custody job.
        import datetime as dt
        start=int(dt.datetime(2026,10,5,tzinfo=dt.timezone.utc).timestamp()*1000)
        bars=[]
        for i in range(150):
            price=1000000+i*11
            bars.append(dict(symbol="FIXTURE",openTime=start+i*3600000,
                availableTime=start+(i+1)*3600000,open=price-1,
                high=price+10,low=price-20,close=price,
                tickVolume=123+i))
        bundle={"schema":1,"source":"Pepperstone-cTrader-OpenAPI",
            "readOnly":True,"start":start,"end":start+151*3600000,
            "bars":bars,"raw":[]}
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder)
            source=folder/"source.json"
            normal=folder/"normal.json"
            scored=folder/"score.json"
            source.write_text(json.dumps(bundle,sort_keys=True))
            executable=str(Path.cwd()/"src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll")
            subprocess.run(["dotnet",executable,str(source),str(normal)],check=True)
            subprocess.run(["dotnet",executable,str(source),str(scored),
                "--score-causal"],check=True)
            a=json.loads(normal.read_text());b=json.loads(scored.read_text())
            self.assertEqual(a["status"],"SOURCE_VALIDATED_NOT_EXECUTION_REPLAY")
            self.assertFalse(a["economicQualification"])
            self.assertTrue(b["forecastScored"]>=100)
            self.assertTrue(b["publicScoreAdmitted"])
            self.assertIsNotNone(b["brierSkill"])
            self.assertFalse(b["netEurQualified"])
            self.assertEqual(b["ordersSubmitted"],0)

    def test_cold_source_is_previous_exact_authenticated_run_and_owner_only(self):
        workflow=Path('.github/workflows/verify.yml').read_text()
        script=Path('research/score_existing_source.py').read_text()
        self.assertIn("      authorized_cold_source_score:",workflow)
        self.assertIn("  cold_causal_score:",workflow)
        self.assertIn("needs.verify.outputs.authorized_cold_source_score == 'true'",workflow)
        self.assertIn('git diff-tree --no-commit-id --name-only -r HEAD',workflow)
        self.assertIn('"ops/cold-score-request.txt"',workflow)
        self.assertIn("run-id: 41467047520",workflow)
        self.assertIn('SOURCE_RUN_ID = "41467047520"',script)
        self.assertIn("unseal_new(sealed,private,SOURCE_RUN_ID)",script)
        self.assertNotIn("ProtoOAGetTrendbarsReq(",script)
        self.assertNotIn("ProtoOANewOrderReq(",script)

    def test_economic_source_exact_owner_gate_and_fixed_universe(self):
        from . import economic_source
        self.assertEqual(economic_source.UNIVERSE,
            ("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD"))
        self.assertEqual([(x[0],x[2],x[3]) for x in economic_source.RESOLUTIONS],
            [("H4",240,370),("M15",15,14)])
        workflow=Path(".github/workflows/verify.yml").read_text()
        self.assertIn("MXM_ECONOMIC_SOURCE_ADMISSION",workflow)
        self.assertIn('"ops/economic-request.txt"',workflow)
        self.assertIn("authorized_economic_request",workflow)
        self.assertIn("run: python -m research.economic_source",workflow)
        self.assertIn("run: python -m research.economic_readback",workflow)
        self.assertNotIn("ProtoOANewOrderReq(",Path("research/economic_source.py").read_text())

    @unittest.skipUnless(Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists(), 'C# build required')
    def test_native_multitimeframe_receipt_explicitly_refuses_net(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root)
            input=root/"econ.json"
            receipt=root/"receipt.json"
            data={
              "schema":"mxm-econ-source-v2",
              "source":"Pepperstone-cTrader-OpenAPI","readOnly":True,
              "developmentDataOnly":True,"captureEnd":1780000000000,
              "brokerContract":{"FIXTURE":{"minVolume":100000,
                  "stepVolume":100000,"lotSize":10000000,
                  "pipPosition":4}},
              "historicalBidAsk":{
                 "FIXTURE":{"bid":{"complete":True,"rows":[[1770000000000,110000]]},
                            "ask":{"complete":True,"rows":[[1770000000000,110002]]}}},
              "bars":[{"symbol":"FIXTURE","resolution":"H4",
                 "periodMinutes":240,"openTime":1770000000000,
                 "availableTime":1770000000000+240*60000,
                 "open":110000,"high":110100,"low":109900,
                 "close":110010,"tickVolume":12}]}
            input.write_text(json.dumps(data))
            executable=Path.cwd()/"src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
            subprocess.run(["dotnet",str(executable),str(input),str(receipt),
                "--economic-source"],check=True)
            evidence=json.loads(receipt.read_text())
            self.assertEqual(evidence["sourceBarCount"],1)
            self.assertFalse(evidence["fullyFundedNet200EurProven"])
            self.assertFalse(evidence["twelveMonthSpanObserved"])
            self.assertEqual(evidence["ordersSubmitted"],0)
            quotes=evidence["genuineHistoricalBidAskQuotes"]["FIXTURE"]
            self.assertEqual(quotes["sampleCount"],1)
            self.assertEqual(float(quotes["medianPips"]),.2)

            self.assertEqual(evidence["brokerSourceContract"]["FIXTURE"],
                "OBSERVED_BID_ASK_MARGIN_OR_COST_MISSING")

    def test_broker_boundary_bar_filtered_without_cost_or_geometry_relaxation(self):
        from .economic_source import _bounded_server_window
        origin=240*60000*100
        out=origin+240*60000
        def bar(ms):
            return e.ProtoOATrendbar(
                utcTimestampInMinutes=ms//60000,
                low=100000,deltaOpen=5,deltaHigh=10,deltaClose=6,volume=100)
        requested=_bounded_server_window([bar(origin),bar(out)],
            origin,out-1,240)
        self.assertEqual([r[0] for r in requested],[origin])
        with self.assertRaisesRegex(CaptureContractError,"BAR_GEOMETRY"):
            _bounded_server_window([bar(out+2*240*60000)],
                origin,out-1,240)

    def test_one_frozen_new_economic_challenger_never_relabels_gross_as_net(self):
        workflow=Path(".github/workflows/verify.yml").read_text()
        scorer=Path("research/score_economic_source.py").read_text()
        model=Path("src/Mxm.Core/EconomicBreakoutProbe.cs").read_text()
        self.assertIn("MXM_COLD_ECONOMIC_SCREEN",workflow)
        self.assertIn('"ops/economic-screen-request.txt"',workflow)
        self.assertIn("authorized_economic_screen",workflow)
        self.assertIn("run-id: 41476636915",workflow)
        self.assertIn('FROZEN_SOURCE_RUN="41476636915"',scorer)
        self.assertIn("originalCsharpSourceReceiptReconciled",scorer)
        self.assertIn("NO broker requests",workflow)
        self.assertNotIn("ProtoOANewOrderReq(",scorer)
        self.assertIn("GROSS_OHLC_PROXY_NOT_EXECUTABLE_NET",model)

    def test_true_broker_cost_coverage_source_is_authenticated_and_read_only(self):
        workflow=Path(".github/workflows/verify.yml").read_text()
        source=Path("research/net_coverage.py").read_text()
        bot=Path("src/Mxm.Cloud/MxmCloud.cs").read_text()
        self.assertIn("MXM_AUTHENTIC_NET_COVERAGE",workflow)
        self.assertIn('"ops/net-coverage-request.txt"',workflow)
        self.assertIn("needs.verify.outputs.authorized_net_coverage == 'true'",workflow)
        self.assertIn("run-id: 41476636915",workflow)
        self.assertIn('SOURCE_RUN_ID="41476636915"',source)
        self.assertIn("NET_ORIGINAL_CSHARP_PARITY_FAILED",source)
        self.assertNotIn("ProtoOANewOrderReq(",source)
        self.assertIn("Timer.Start(15)",bot)
        self.assertIn("protected override void OnTimer()",bot)
        self.assertIn("protected override void OnException(",bot)
        self.assertNotIn("ExecuteMarketOrder(",bot)
        self.assertNotIn("PlaceLimitOrder(",bot)
        self.assertNotIn("Stop();",bot)

    def test_broad_research_custody_has_no_broker_credentials(self):
        workflow=Path('.github/workflows/verify.yml').read_text()
        job=workflow.split('  broad_regime_discovery:')[1]
        self.assertIn("needs.verify.outputs.authorized_regime_discovery == 'true'",job)
        self.assertNotIn('R3_CTRADER_',job)
        self.assertIn('run-id: 41476636915',job)
        risk=Path('src/Mxm.Core/OwnerRiskLimits.cs').read_text()
        self.assertNotIn('RiskFraction=',risk)
        self.assertIn('ADAPTIVE_PORTFOLIO',risk)

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

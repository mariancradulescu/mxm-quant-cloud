"""Synthetic-only tests for protected materialization and C# report whitelisting."""
import json
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from . import funded_history_economic_development as d
from .integrated_market_source import FUNDED_HISTORY
from .guard import CaptureContractError


def data(v):
    return (json.dumps(v, sort_keys=True) + "\n").encode()


class AuthenticatedEconomicDevelopmentTests(unittest.TestCase):
    def fixture(self):
        market = {"Status": "COMPLETE", "ActiveHours": 1, "ResponseCompleteHours": 1,
                  "VerifiedPairedTickHours": 1, "ReplayUsableCompletePathMarks": 2,
                  "Timeframes": {key: {"Status": "COMPLETE"} for key in FUNDED_HISTORY.periods}}
        gaps = []
        for side in ("BID", "ASK"):
            for i in range(131):
                gaps.append({"Market": "NAS100", "Timeframe": "TICKS", "Side": side,
                             "From": FUNDED_HISTORY.start + i * 100,
                             "ToExclusive": FUNDED_HISTORY.start + i * 100 + 1,
                             "Reason": "MISSING"})
        gaps.append({"Market": "NAS100", "Timeframe": "TICKS", "Side": "ASK",
                     "From": FUNDED_HISTORY.start + 20_000,
                     "ToExclusive": FUNDED_HISTORY.start + 20_001,
                     "Reason": "PROVIDER_ERROR", "ProviderCode": "UNKNOWN_ERROR"})
        plan = {"Status": "PREPARED_NOT_AUTHORIZED_FOR_BROKER_ACCESS",
                "OriginalRun": d.ORIGINAL_RUN, "NewOpenApiRequests": 0, "Requests": gaps}
        original = {"RunId": d.ORIGINAL_RUN, "Study": FUNDED_HISTORY.study,
                    "Status": "SOURCE_FAILED_CLOSED", "Requests": 2, "Shards": [{"File": "dummy.enc"}],
                    "ProtocolSha256": "f" * 64,
                    "Warmup": FUNDED_HISTORY.warmup, "Start": FUNDED_HISTORY.start,
                    "End": FUNDED_HISTORY.end,
                    "NewOrders": 0, "CloudActivated": False, "EconomicEvaluations": 0}
        manifest = {"Status": "CUSTODY_VERIFIED_PARTIAL_SOURCE",
                    "OriginalRun": d.ORIGINAL_RUN, "ProtocolSha256": original["ProtocolSha256"],
                    "OriginalCipherShards": original["Shards"], "OriginalRequestsVerified": 2,
                    "OriginalShardsVerified": 1,
                    "CompleteMarketNames": ["EURUSD"], "Markets": {"EURUSD": market,
                    "NAS100": {"Status": "PARTIAL"}}}
        orig_bytes, manifest_bytes, gap_bytes = data(original), data(manifest), data(plan)
        receipt = {"Status": "CUSTODY_VERIFIED_PARTIAL_SOURCE", "OriginalStatus": "SOURCE_FAILED_CLOSED",
                   "OriginalRun": d.ORIGINAL_RUN, "RecoveryRun": d.RECOVERY_RUN,
                   "OriginalRequestsVerified": 2, "OriginalShardsVerified": 1,
                   "CompleteMarketNames": ["EURUSD"],
                   "SourceReceiptSha256": d.sha256(orig_bytes),
                   "ManifestSha256": d.sha256(manifest_bytes), "GapRequestsSha256": d.sha256(gap_bytes),
                   "NewOpenApiRequests": 0, "OrdersSubmitted": 0, "CloudActivated": False,
                   "EconomicEvaluations": 0}
        receipt_bytes = data(receipt)
        return (orig_bytes, receipt_bytes, manifest_bytes, gap_bytes)

    def test_valid_protected_provenance_selects_only_complete_subset(self):
        blobs = self.fixture()
        expected = tuple(map(d.sha256, blobs))
        original, manifest, selected = d.verify_recovery_binding(*blobs, expected_hashes=expected)
        self.assertEqual(selected, ["EURUSD"])
        self.assertEqual(original["Status"], "SOURCE_FAILED_CLOSED")
        self.assertEqual(manifest["Markets"]["NAS100"]["Status"], "PARTIAL")

    def test_any_manifest_recovery_or_source_tampering_fails(self):
        blobs = self.fixture()
        expected = tuple(map(d.sha256, blobs))
        for i in range(4):
            corrupted = list(blobs)
            corrupted[i] += b" "
            with self.subTest(index=i), self.assertRaisesRegex(
                    CaptureContractError, "FUNDED_DEVELOPMENT_IMMUTABLE_HASH_BINDING"):
                d.verify_recovery_binding(*corrupted, expected_hashes=expected)

    def test_cannot_promote_nas100_to_full_source(self):
        blobs = list(self.fixture())
        manifest = json.loads(blobs[2])
        manifest["CompleteMarketNames"].append("NAS100")
        manifest["Markets"]["NAS100"] = dict(manifest["Markets"]["EURUSD"], Status="COMPLETE")
        blobs[2] = data(manifest)
        receipt = json.loads(blobs[1])
        receipt["CompleteMarketNames"].append("NAS100")
        receipt["ManifestSha256"] = d.sha256(blobs[2])
        blobs[1] = data(receipt)
        expected = tuple(map(d.sha256, blobs))
        with self.assertRaisesRegex(CaptureContractError, "FUNDED_DEVELOPMENT_NAS100_MUST_STAY_PARTIAL"):
            d.verify_recovery_binding(*blobs, expected_hashes=expected)

    def test_fresh_ciphertext_scan_must_equal_previous_original_manifest(self):
        blobs = self.fixture()
        original = json.loads(blobs[0])
        manifest = json.loads(blobs[2])
        scanned = {**manifest, "OriginalStatus": "SOURCE_FAILED_CLOSED",
                   "ActiveHourCoverage": [], "MissingRequests": json.loads(blobs[3])["Requests"]}
        manifest["ActiveHourCoverage"] = []
        d.verify_original_against_manifest(original, manifest, scanned, blobs[3])
        scanned["Markets"] = json.loads(json.dumps(manifest["Markets"]))
        scanned["Markets"]["EURUSD"]["ActiveHours"] = 99
        with self.assertRaisesRegex(CaptureContractError, "FUNDED_DEVELOPMENT_FRESH_CUSTODY_RECONCILIATION"):
            d.verify_original_against_manifest(original, manifest, scanned, blobs[3])

    def test_safe_csharp_report_is_only_aggregate_and_preserves_censorship(self):
        books = {}
        nets = {}
        weekly = {}
        for v in d.VARIANTS:
            book = {"Financial": {
                "Boundary": {"RightCensored": v == d.CONTEXT, "CashEur": 300},
                "CompleteModeledNetEur": None if v == d.CONTEXT else 0,
                "RealizedLedgerNetEur": 0, "GrossEur": 0,
                "Costs": {"Commission": 0, "Spread": 0, "Slippage": 0, "Conversion": 0,
                          "Financing": 0},
                "FinancingUnverifiedTrips": 0, "UnknownPathTrips": 0,
                "UnknownEquityClocks": 0, "MaxMarginEur": 0, "MaxPlannedRiskEur": 0,
                "SampledFloatingDrawdownPercent": 0, "KnownSampledEquityClocks": 0,
                "ContinuousFloatingDrawdownCertified": False,
                "MaxConcurrent": 0, "StopRiskOverruns": 0,
                "SettlementEvents": [{"PrivateAccountIdentity": "DO_NOT_PUBLISH"}]},
                "CompletedTradesByWeek": {"2026-W32": 0}, "Hard21ByWeek": {"2026-W32": False},
                "WeeksWithHard21": 0, "BothWeeksHard21": False, "ByFamily": {}}
            books[v] = {"Book": book, "BySymbol": {}, "ActionValues": [{"PrivateTick": "DO_NOT_PUBLISH"}]}
            nets[v] = None if v == d.CONTEXT else 0
            weekly[v] = [None]
        scenario = {"Books": books, "CompleteModeledNetEur": nets,
                    "CompleteComparableWeeklyNetEur": weekly, "ContextMinusControlsEur": {},
                    "CalibrationMetrics": {}, "MatchedForecastRows": {},
                    "LabelCoverage": [], "ModelCohorts": [], "PrimaryAdverseComparisons": None}
        report = {"SourceRun": d.ORIGINAL_RUN, "InputSha256": "a"*64,
                  "CostEvidence": "CONDITIONAL_COST_MODEL_FIXED_ORIGINAL_BROKER_SNAPSHOT",
                  "BrokerNetCertified": False, "IndependentConfirmation": False,
                  "Start": FUNDED_HISTORY.start, "End": FUNDED_HISTORY.end,
                  "Status": "FINANCED_POLICY_DEVELOPMENT",
                  "Result": {"Evidence": "HISTORICAL_DEVELOPMENT", "IndependentConfirmation": False,
                             "Orders": 0, "CloudActivation": False, "EvaluationStart": 1, "End": 2,
                             "EvaluationCoverage": [], "Central": scenario, "Adverse": scenario}}
        result = d.extract_safe_economics(report, "a"*64, ["EURUSD"], {}, {})
        encoded = json.dumps(result)
        self.assertNotIn("Private", encoded)
        self.assertNotIn("DO_NOT_PUBLISH", encoded)
        self.assertIsNone(result["Scenarios"]["Adverse"]["Policies"][d.CONTEXT]["CapitalFinalEur"])
        self.assertIsNone(result["Scenarios"]["Central"]["Policies"][d.CONTEXT]["DeltaVsCashEur"])
        self.assertEqual(set(result["Scenarios"]["Central"]["Policies"]), set(d.VARIANTS))


    def test_original_failed_market_subset_materializes_private_replay_source(self):
        from . import integrated_market_readback as original_reader
        from . import funded_history_recovery as recovery
        from .ctrader_proto import OpenApiMessages_pb2 as m
        from .ctrader_proto import OpenApiModelMessages_pb2 as e
        from .test_integrated_market_ticks import SourceCollectionTests
        fixture = SourceCollectionTests()

        def intermittent_provider(req):
            if isinstance(req, m.ProtoOAGetTickDataReq) and req.symbolId == 4 and req.type == e.ASK:
                return m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="UNKNOWN_ERROR")
            return fixture.api_response(req)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                fixture.capture(directory, intermittent_provider)
            cipher = Path(directory) / "cipher"
            receipt = json.loads((Path(directory) / "public" / "source.json").read_bytes())
            self.assertEqual(receipt["Status"], "SOURCE_FAILED_CLOSED")
            with patch.object(recovery, "unseal_new", side_effect=lambda data, *_: data), \
                 patch.object(original_reader, "unseal_new", side_effect=lambda data, *_: data), \
                 patch.object(original_reader, "CIPHER_DIR", cipher):
                scanned = recovery.scan(receipt, b"only-fixture",
                                        expected_run="1234", scope=fixture.scope,
                                        cipher_dir=cipher)
                selected = scanned["CompleteMarketNames"]
                markets = original_reader.readback(receipt, b"only-fixture",
                    interval=30_000, scope=fixture.scope, include_markets=selected)
            self.assertEqual(set(selected), set(fixture.names[:3]))
            self.assertEqual({market["Name"] for market in markets}, set(selected))
            self.assertTrue(all(market["RequestedTickHours"] == 1
                                and len(market["Quotes"]) > 0 for market in markets))
            self.assertNotIn("NO_VOLUME", {market["Name"] for market in markets})

    def test_partial_original_symbol_cannot_be_materialized_as_complete(self):
        from . import integrated_market_readback as original_reader
        from .ctrader_proto import OpenApiMessages_pb2 as m
        from .ctrader_proto import OpenApiModelMessages_pb2 as e
        from .test_integrated_market_ticks import SourceCollectionTests
        fixture = SourceCollectionTests()

        def rejected(req):
            if isinstance(req, m.ProtoOAGetTickDataReq) and req.symbolId == 4 and req.type == e.ASK:
                return m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="UNKNOWN_ERROR")
            return fixture.api_response(req)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                fixture.capture(directory, rejected)
            receipt = json.loads((Path(directory) / "public" / "source.json").read_bytes())
            with patch.object(original_reader, "CIPHER_DIR", Path(directory) / "cipher"), \
                 patch.object(original_reader, "unseal_new", side_effect=lambda data, *_: data):
                with self.assertRaises(CaptureContractError):
                    original_reader.readback(receipt, b"only-fixture", interval=30_000,
                        scope=fixture.scope, include_markets=["NO_VOLUME"])


if __name__ == "__main__":
    unittest.main()

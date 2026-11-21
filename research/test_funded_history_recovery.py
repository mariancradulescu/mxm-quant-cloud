"""No-market-access fixtures for partial-source recovery, duplicates and integrity."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import funded_history_recovery as recovery
from . import integrated_market_source as source
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .guard import CaptureContractError
from .test_integrated_market_ticks import SourceCollectionTests


class PartialRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SourceCollectionTests()

    def readback(self, receipt, cipher):
        with patch.object(recovery, "unseal_new", side_effect=lambda value, *_: value):
            return recovery.scan(receipt, b"fixture-only", expected_run="1234",
                                 scope=self.fixture.scope, cipher_dir=cipher)

    def test_complete_shards_require_all_original_packets_and_both_sides(self):
        with tempfile.TemporaryDirectory() as d:
            cipher, receipt = self.fixture.capture(d)
            receipt["Status"] = "SOURCE_FAILED_CLOSED"  # exercising interrupted provenance
            result = self.readback(receipt, cipher)
            self.assertEqual(result["OriginalRequestsVerified"], receipt["Requests"])
            self.assertEqual(result["OriginalShardsVerified"], len(receipt["Shards"]))
            self.assertEqual(set(result["CompleteMarketNames"]), set(self.fixture.names))
            self.assertFalse(result["MissingRequests"])
            self.assertTrue(all(x["Status"] == "COMPLETE" for x in result["ActiveHourCoverage"]))

    def test_failed_ask_is_not_no_quotes_and_keeps_prior_markets(self):
        def fail_last_ask(req):
            if isinstance(req, m.ProtoOAGetTickDataReq) and req.symbolId == 4 and req.type == e.ASK:
                return m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="UNKNOWN_ERROR")
            return self.fixture.api_response(req)

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                self.fixture.capture(d, fail_last_ask)
            receipt = json.loads((Path(d) / "public" / "source.json").read_text())
            self.assertEqual(receipt["Status"], "SOURCE_FAILED_CLOSED")
            result = self.readback(receipt, Path(d) / "cipher")
            self.assertEqual(set(result["CompleteMarketNames"]), set(self.fixture.names[:3]))
            self.assertEqual(result["Markets"]["NO_VOLUME"]["Status"], "PARTIAL")
            self.assertTrue(any(x["Market"] == "NO_VOLUME" and x["Side"] == "ASK" and
                                x["Reason"] == "PROVIDER_ERROR" and x["ProviderCode"] == "UNKNOWN_ERROR"
                                for x in result["MissingRequests"]))
            self.assertTrue(any(x["Market"] == "NO_VOLUME" and x["Status"] == "INCOMPLETE"
                                for x in result["ActiveHourCoverage"]))
            self.assertEqual(result["NewOpenApiRequests"], 0)

    def test_ciphertext_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            cipher, receipt = self.fixture.capture(d)
            receipt["Status"] = "SOURCE_FAILED_CLOSED"
            shard = next(cipher.glob("*-bars.enc"))
            shard.write_bytes(shard.read_bytes() + b"changed")
            with self.assertRaisesRegex(CaptureContractError, "RECOVERY_CIPHERTEXT_HASH"):
                self.readback(receipt, cipher)

    def test_receipt_must_bind_to_original_failed_study(self):
        with tempfile.TemporaryDirectory() as d:
            cipher, receipt = self.fixture.capture(d)
            with self.assertRaisesRegex(CaptureContractError, "RECOVERY_ORIGINAL_RECEIPT_BINDING"):
                self.readback(receipt, cipher)


    def test_hour_response_vs_quote_evidence(self):
        hour = self.fixture.base
        terminal = [(hour, hour + source.HOUR - 1, "TERMINAL")]
        no_quotes = [(hour, hour + source.HOUR - 1, "NO_QUOTES")]
        quoted = recovery.classify_hour(terminal, [(hour + 15_000, 10_000_000)], hour)
        self.assertEqual(quoted["RequestCoverage"], "COMPLETE")
        self.assertEqual(quoted["ObservedTicks"], 1)
        self.assertEqual(quoted["NoQuotesMilliseconds"], 0)
        empty = recovery.classify_hour(no_quotes, [], hour)
        self.assertEqual(empty["RequestCoverage"], "COMPLETE")
        self.assertEqual(empty["QuoteEvidence"], "NO_QUOTES_ONLY")
        self.assertEqual(empty["ObservedTicks"], 0)
        self.assertEqual(empty["NoQuotesMilliseconds"], source.HOUR)
        mixed = recovery.classify_hour(
            [(hour, hour + source.HOUR // 2 - 1, "NO_QUOTES"),
             (hour + source.HOUR // 2, hour + source.HOUR - 1, "TERMINAL")],
            [(hour + source.HOUR // 2 + 15_000, 10_000_001)], hour)
        self.assertEqual(mixed["RequestCoverage"], "COMPLETE")
        self.assertEqual(mixed["NoQuotesMilliseconds"], source.HOUR // 2)
        self.assertEqual(mixed["ObservedTicks"], 1)
        partial = recovery.classify_hour(
            [(hour, hour + source.HOUR // 2 - 1, "TERMINAL"),
             (hour + source.HOUR // 2, hour + source.HOUR - 1, "MISSING")],
            [(hour + 15_000, 10_000_001)], hour)
        self.assertEqual(partial["RequestCoverage"], "PARTIAL")
        self.assertEqual(partial["MissingMilliseconds"], source.HOUR // 2)
        self.assertEqual(partial["ObservedTicks"], 1)
        self.assertEqual(partial["QuoteEvidence"], "INCOMPLETE_WITH_AUTHENTIC_QUOTE")

    def test_legitimate_no_quotes_on_one_or_both_sides_does_not_need_recollection(self):
        for no_quote_sides in ((e.ASK,), (e.BID, e.ASK)):
            with self.subTest(no_quote_sides=no_quote_sides):
                def provider(req):
                    if (isinstance(req, m.ProtoOAGetTickDataReq) and req.symbolId == 1
                            and req.type in no_quote_sides):
                        return m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="NO_QUOTES")
                    return self.fixture.api_response(req)
                with tempfile.TemporaryDirectory() as directory:
                    cipher, receipt = self.fixture.capture(directory, provider)
                    receipt["Status"] = "SOURCE_FAILED_CLOSED"
                    result = self.readback(receipt, cipher)
                    row = next(x for x in result["ActiveHourCoverage"] if x["Market"] == "EXPENSIVE")
                    self.assertEqual(row["ResponseCoverage"], "COMPLETE")
                    self.assertFalse(row["GenuineBidAskObserved"])
                    self.assertEqual(row["ReplayUsableMarks"], 0)
                    for side in no_quote_sides:
                        self.assertEqual(row["SideEvidence"]["BID" if side == e.BID else "ASK"]
                                         ["QuoteEvidence"], "NO_QUOTES_ONLY")
                    self.assertFalse(any(x["Market"] == "EXPENSIVE" for x in result["MissingRequests"]))
                    self.assertIn("EXPENSIVE", result["CompleteMarketNames"])

    def test_split_page_mixes_terminal_and_no_quotes_without_fake_quotes(self):
        def provider(req):
            if isinstance(req, m.ProtoOAGetTickDataReq) and req.symbolId == 1 and req.type == e.BID:
                span = req.toTimestamp - req.fromTimestamp + 1
                if span == source.HOUR:
                    return m.ProtoOAGetTickDataRes(ctidTraderAccountId=61, hasMore=True)
                if req.fromTimestamp == self.fixture.base:
                    return m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="NO_QUOTES")
            return self.fixture.api_response(req)

        with tempfile.TemporaryDirectory() as directory:
            cipher, receipt = self.fixture.capture(directory, provider)
            receipt["Status"] = "SOURCE_FAILED_CLOSED"
            result = self.readback(receipt, cipher)
            row = next(x for x in result["ActiveHourCoverage"] if x["Market"] == "EXPENSIVE")
            self.assertEqual(row["ResponseCoverage"], "COMPLETE")
            self.assertEqual(row["SideEvidence"]["BID"]["NoQuotesMilliseconds"], source.HOUR // 2)
            self.assertEqual(row["SideEvidence"]["BID"]["ObservedTicks"], 1)
            self.assertEqual(row["SideEvidence"]["ASK"]["ObservedTicks"], 1)
            self.assertTrue(row["GenuineBidAskObserved"])
            self.assertFalse(any(x["Market"] == "EXPENSIVE" for x in result["MissingRequests"]))


if __name__ == "__main__":
    unittest.main()

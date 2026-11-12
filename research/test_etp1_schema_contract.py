"""ETP1 native receipt regression: direct schema and frozen legacy Receipt.

No broker access, source reading, token, custody secret or portfolio scoring.
"""
import unittest

from .native_original_openapi_product_replay import (
    MarketReplayError, require_native_profile_result
)


class ETP1SchemaContractTest(unittest.TestCase):
    @staticmethod
    def etp():
        financial = {
            "CompletedModelRoundTrips": 0,
            "ModelClosedCentralNetEur": 0,
            "ModelClosedAdverseNetEur": 0,
            "ModelTripsPerObservedIsoWeek": {},
        }
        return {
            "Study": "ETP1",
            "SourceSha256": "test-hash",
            "Joint": financial,
            "LeaderOnly": financial,
            "FollowerOnly": financial,
            "Long": financial,
            "Short": financial,
            "Fixed90": financial,
            "Cash": financial,
        }

    def test_etp1_uses_direct_native_schema_without_receipt(self):
        direct = self.etp()
        self.assertNotIn("Receipt", direct)
        self.assertIs(require_native_profile_result(direct, "--native-etp1"), direct)
        self.assertIn("Joint", direct)

    def test_etp1_rejects_missing_financial_book(self):
        bad = self.etp()
        del bad["FollowerOnly"]
        with self.assertRaises(MarketReplayError):
            require_native_profile_result(bad, "--native-etp1")

    def test_etp1_rejects_nested_legacy_result(self):
        with self.assertRaises(MarketReplayError):
            require_native_profile_result({"Receipt": self.etp()}, "--native-etp1")

    def test_legacy_profiles_retain_nested_receipt_contract(self):
        old = {"Receipt": {"CompletedModelRoundTrips": 4}}
        self.assertIs(require_native_profile_result(old, "--native-prr1"), old)
        with self.assertRaises(MarketReplayError):
            require_native_profile_result(self.etp(), "--native-prr1")

    def test_direct_schema_not_mistaken_for_legacy_study(self):
        wrong = self.etp()
        wrong["Study"] = "ANOTHER_STUDY"
        with self.assertRaises(MarketReplayError):
            require_native_profile_result(wrong, "--native-etp1")


if __name__ == "__main__":
    unittest.main()

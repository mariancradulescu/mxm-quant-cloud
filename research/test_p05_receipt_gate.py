"""Broker-free self-tests for new public receipt reader, using synthetic input."""
from datetime import datetime, timezone
import unittest

from research.p05_receipt_gate import summarize


def fixture():
    ts = int(datetime(2026, 9, 1, tzinfo=timezone.utc).timestamp() * 1000)
    horizons = {
        tf: {"bars": 2, "firstUTC": ts, "lastUTC": ts + 1000,
             "rejectedOrFailedPages": 0, "sessionGapsReconciled": False,
             "sampledSpreadOnlyToMedianRangePercentByMultiplier": {"1.5": 22.0}}
        for tf in ("M15", "M30", "H1", "H4", "D1")
    }
    return {
        "schema": "P05_NEW_PEPPERSTONE_AUTHENTIC_READ_ONLY_SOURCE",
        "ordersSubmitted": 0, "cloudActivated": False, "resultsDevelopmentOnly": True,
        "runId": "synthetic-only", "historicalStart": "2026-08-24T00:00:00Z",
        "endExclusive": "2026-11-23T00:00:00Z", "totalNonArchivedSymbols": 10,
        "visibleSymbols": 1, "contractDetailsExamined": 1, "marginsObserved": 1,
        "marginsBelow300EUR": 1, "marketProbeTargets": 1, "marketProbesCompleted": 1,
        "marketCoverage": {
            "TEST": {"bidAsk": {"window0": {"validAsOfPairs": 3}},
                     "observedFixedClockMedianSpreadBps": 0.0,
                     "allInCostEur": None, "timeframes": horizons}
        }
    }


class PublicReceiptTests(unittest.TestCase):
    def test_missing_costs_are_not_profit_or_zero_dd(self):
        result = summarize(fixture())
        self.assertIsNone(result["NET_EUR"])
        self.assertIsNone(result["DD_equity_percent"])
        self.assertEqual(result["HARD21"], "UNKNOWN")
        self.assertEqual(result["zeroSpreadSamplesRequiringReview"], ["TEST"])
        self.assertEqual(result["allInCostMissingSymbols"], 1)

    def test_future_bars_are_rejected(self):
        data = fixture()
        data["marketCoverage"]["TEST"]["timeframes"]["M15"]["lastUTC"] = 1990000000000
        with self.assertRaises(ValueError):
            summarize(data)

    def test_trading_or_confirmatory_flags_fail_closed(self):
        for name, value in [
            ("ordersSubmitted", 1), ("cloudActivated", True),
            ("resultsDevelopmentOnly", False)
        ]:
            data = fixture()
            data[name] = value
            with self.assertRaises(ValueError):
                summarize(data)

    def test_unjustified_margin_counts_fail(self):
        data = fixture()
        data["marginsObserved"] = 2
        with self.assertRaises(ValueError):
            summarize(data)

    def test_unavailable_ratio_never_inferred(self):
        data = fixture()
        data["marketCoverage"]["TEST"]["timeframes"]["H4"]["sampledSpreadOnlyToMedianRangePercentByMultiplier"] = None
        self.assertIsNone(summarize(data)["horizons"]["H4"]["medianSampledSpreadToMedianRangePercentX15"])


if __name__ == "__main__":
    unittest.main()

"""Source-independent, broker-free mathematical/safety checks, NOT Spotware API tests."""
import unittest

from research.p05_source_economic_gate import (
    PERIODS, RUN, SOURCE_END_MS, SOURCE_FIRST_MS,
    upper_bound_diagnostic, _iso_week,
)


class SourceEconomicGateTests(unittest.TestCase):
    def test_source_window_exact_utc(self):
        self.assertEqual(SOURCE_FIRST_MS, 1787529600000)
        self.assertEqual(SOURCE_END_MS, 1795392000000)
        self.assertEqual(RUN, "45134137836")
        self.assertEqual(set(PERIODS), {"M15", "M30", "H1", "H4", "D1"})

    def test_cost_hurdle_counts_expost_only(self):
        t = 1787788800000
        bars = [(t, t + 900000, 10000, 10050, 9960, 10020, 12)]
        result = upper_bound_diagnostic(bars, 30, 100, 15)
        self.assertEqual(result["barCount"], 1)
        self.assertEqual(sum(result["hindsightRangeOnly"]["1.5"].values()), 1)
        self.assertEqual(sum(result["hindsightRangeOnly"]["2"].values()), 1)
        self.assertEqual(sum(result["hindsightAbsoluteOpenCloseOnly"]["1"].values()), 0)
        self.assertTrue(result["fundableMinimumMarginAt210StaticStress"])
        self.assertNotIn("NET_EUR", result)
        self.assertNotIn("filledTrades", result)
        self.assertNotIn("eligibleISOWeeks", result)

    def test_missing_spread_does_not_become_zero(self):
        t = 1787788800000
        row = (t, t + 900000, 10000, 10100, 9900, 10050, 100)
        result = upper_bound_diagnostic([row], None, 15, 15)
        self.assertEqual(result["barCount"], 1)
        self.assertEqual(result["hindsightRangeOnly"], {"1": {}, "1.5": {}, "2": {}})

    def test_future_or_unclosed_bar_rejected(self):
        rows = [(SOURCE_END_MS - 300000, SOURCE_END_MS + 600000,
                 1000, 1020, 990, 1010, 1)]
        with self.assertRaises(ValueError):
            upper_bound_diagnostic(rows, 5, 15, 15)

    def test_negative_spread_and_missing_margin_rejected(self):
        with self.assertRaises(ValueError):
            upper_bound_diagnostic([], -1, 15, 15)
        with self.assertRaises(ValueError):
            upper_bound_diagnostic([], 2, None, 15)

    def test_iso_week_monday_utc(self):
        self.assertEqual(_iso_week(1787616000000), "2026-W35")


if __name__ == "__main__":
    unittest.main()

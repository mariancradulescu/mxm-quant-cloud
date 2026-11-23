"""Offline anti-overclaim regression for the economic source inventory."""
import unittest
from decimal import Decimal
from .p05_economic_screen import load, screen, ratio, summary

class EconomicScreenChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src, hashes = load()
        cls.report = screen(src, hashes)

    def test_source_roster_not_arbitrarily_narrowed(self):
        r = self.report["fullRoster"]
        self.assertEqual(r["nonArchived"], 5339)
        self.assertEqual(r["contractProbed"] + r["notIndividuallyProbed"], 5339)
        self.assertEqual(r["asOfMinMarginBelow200"], 74)
        self.assertFalse(r["wholeRosterCostsAndMarginsKnown"])

    def test_five_asset_classes_and_broader_than_h1(self):
        m = self.report["priorMulticlassSample"]
        self.assertEqual(m["instrumentCount"], 18)
        self.assertEqual(set(m["assetClasses"]), {"fx","crypto","energy","equity","index"})
        self.assertEqual(self.report["H1IncompleteProxy"]["symbols"], 12)
        self.assertEqual(self.report["historicalM5"]["sourceBars"], 836087)

    def test_no_economic_profit_overclaim(self):
        p = self.report["policyEvidence"]
        self.assertIsNone(p["allInNetEUR"])
        self.assertIsNone(p["fundedWeeklyCompleteTrades"])
        self.assertIsNone(p["markedEquityMaxDDPercent"])
        self.assertEqual(p["P0_5"], "NOT_PASSED")
        self.assertTrue(self.report["H1IncompleteProxy"]["NOTAllInCost"])
        self.assertTrue(self.report["H1IncompleteProxy"]["NOTMathematicalExclusion"])

    def test_m15_to_d1_not_excluded(self):
        self.assertEqual(list(self.report["horizonDiagnostics"]), ["M15","M30","H1","H4","D1"])
        self.assertTrue(all(x["historicallyCompleteRoundTripCost"] is None for x in self.report["priorMulticlassSample"]["rows"]))

    def test_arithmetic_and_bad_inputs(self):
        self.assertEqual(ratio(".3","1.2"), Decimal(".25"))
        for a,b in [("-1","1"),("1","0"),("nan","1")]:
            with self.assertRaises(ValueError):
                ratio(a,b)

    def test_report_uses_unknown_not_zero(self):
        md = summary(self.report)
        self.assertIn("NET EUR/%: UNKNOWN",md)
        self.assertIn("No new Open API calls", md)
        self.assertNotIn("HARD21: PASS", md)

if __name__ == "__main__":
    unittest.main()

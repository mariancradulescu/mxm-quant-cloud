"""RNV1 exact frozen 2025 prior-year test, no 2026 price rerun."""
import unittest
from datetime import date,timedelta
from .rnv1_rne1_2025_blind_stress import (START,WEEKS,EXCLUDE,
    TARGETS,MARKETS,dates,calc,MAX_CALLS)
from .rne1_eia_gas_release import event_decision,stamp

class Rnv1Tests(unittest.TestCase):
    def test_fixed_2025_calendar_and_official_june_exception(self):
        d=dates()
        self.assertEqual(WEEKS,39)
        self.assertEqual(len(d),76)
        self.assertEqual(len([x for x in d if x["kind"]=="THURSDAY_EIA"]),38)
        self.assertEqual(len([x for x in d if x["kind"]=="TUESDAY_CONTROL"]),38)
        self.assertTrue(all(x["day"].year==2025 for x in d))
        self.assertFalse(any(x["day"]==date(2025,6,19) for x in d))
        self.assertEqual(len([x for x in d if x["kind"]=="THURSDAY_EIA" and x["rank"]<19]),19)
        self.assertEqual(len([x for x in d if x["kind"]=="THURSDAY_EIA" and x["rank"]>=19]),19)
        self.assertEqual(EXCLUDE,date(2025,6,16))
    def test_fixed_rne1_original_two_targets_and_request_budget(self):
        self.assertEqual(TARGETS,("NatGas","EQT.US"))
        self.assertEqual(MARKETS,("NatGas","EQT.US","EURUSD"))
        self.assertEqual(MAX_CALLS,1800)
    def test_no_2026_repricing_study_period(self):
        self.assertLess(max(x["day"] for x in dates()),date(2025,11,3))
        self.assertNotEqual(START,date(2026,5,4))
    def test_summary_preserves_empty_complete_paths(self):
        empty=[{"week":i,"kind":"THURSDAY_EIA",
                "state":"MISSING_ENTRY_QUOTE"} for i in range(38)]
        x=calc(empty)
        self.assertEqual(x["scheduled"],38)
        self.assertEqual(x["pricedAdaptive"],0)
        self.assertIsNone(x["meanAdaptiveMidpointGrossBps"])
        self.assertEqual(x["currentContractConditionalEur"]["adverse"]["eia"],0)
    def test_uses_original_event_decision_and_calendar_timezone(self):
        d=date(2025,10,23)
        # Empty bars must be explicitly unpriced, not treated as trade.
        self.assertEqual(event_decision(d,{})["state"],
                         "MISSING_COMPLETED_M5_FEATURES")
        self.assertEqual(stamp(d,10,45)-stamp(d,10,30),900000)

if __name__=="__main__":
    unittest.main()

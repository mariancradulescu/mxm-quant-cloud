"""BWR1 frozen Brent-WTI economic cause, calendars, and quote/cash logic."""
from datetime import date
from decimal import Decimal as D
import unittest
from .bwr1_brent_wti_paired_eur import (
    START,WEEKS,MARKETS,CLOCKS,MAX_CALLS,M5,stamp,
    basis,first_signal,exit_policy,pairs,summary)


class Bwr1OriginalCausalTests(unittest.TestCase):
    def setUp(self):
        self.day=date(2026,6,17)
        t0=stamp(self.day,8,30)
        self.bars={
            "SpotBrent":{t0+i*M5:8000000 for i in range(37)},
            "SpotCrude":{t0+i*M5:7800000 for i in range(37)}}
        self.hi=stamp(self.day,9,45)
        self.back=stamp(self.day,10,0)
    def test_contract_calendar(self):
        self.assertEqual(START,date(2025,11,3))
        self.assertEqual(WEEKS,52)
        self.assertEqual(MARKETS,("SpotBrent","SpotCrude"))
        self.assertEqual([x[0] for x in CLOCKS],["10:05","10:40","11:35"])
        self.assertEqual(MAX_CALLS,6200)
    def test_feature_up_sweep_rejected_short_rich_brent(self):
        self.bars["SpotBrent"][self.hi]=8100000
        self.bars["SpotBrent"][self.back]=8000000
        x=first_signal(self.day,self.bars)
        self.assertEqual(x["state"],"CAUSAL_REJECTED_BASIS")
        self.assertEqual(x["side"],-1)
    def test_feature_down_sweep_rejected_long_cheap_brent(self):
        self.bars["SpotBrent"][self.hi]=7900000
        self.bars["SpotBrent"][self.back]=8000000
        self.assertEqual(first_signal(self.day,self.bars)["side"],1)
    def test_sweep_without_reentry_is_not_signal(self):
        self.bars["SpotBrent"][self.hi]=8100000
        self.bars["SpotBrent"][self.back]=8100000
        self.assertEqual(first_signal(self.day,self.bars)["state"],
                         "NO_REJECTED_BASIS_SWEEP")
    def test_no_sweep_is_abstention(self):
        self.assertEqual(first_signal(self.day,self.bars)["state"],
                         "NO_REJECTED_BASIS_SWEEP")
    def test_1035_exit_is_later_monitor_only(self):
        self.bars["SpotBrent"][self.hi]=8100000
        x=first_signal(self.day,self.bars)
        self.bars["SpotBrent"][stamp(self.day,10,35)]=8110000
        v=exit_policy(self.day,self.bars,x)
        self.assertEqual(v["exit"],"10:40")
        self.assertTrue(v["invalidated"])
        self.bars["SpotBrent"][stamp(self.day,10,35)]=8000000
        self.assertEqual(exit_policy(self.day,self.bars,x)["exit"],"11:35")
    def test_bid_ask_at_exact_asof(self):
        at=100000
        self.assertEqual(pairs([[at-3000,100000]],[[at-9000,100100]],at),
                         [100000,100100])
        self.assertIsNone(pairs([[at-30000,100000]],[[at-100,100100]],at))
        self.assertIsNone(pairs([[at-20,100110]],[[at-50,100100]],at))
        self.assertIsNone(pairs([[at+100,100000]],[[at-50,100100]],at))
    def test_no_imputation_of_empty_finance(self):
        x=summary([{"week":0,"state":"NO_REJECTED_BASIS_SWEEP"}]*260)
        self.assertEqual(x["scheduledDays"],260)
        self.assertEqual(x["basisSweepIntents"],0)
        self.assertEqual(x["pairedCompleteEurPriced"],0)
        self.assertEqual(x["money"]["adverse"]["adaptive"]["conditionalNetEurSum"],0)

if __name__=="__main__":
    unittest.main()

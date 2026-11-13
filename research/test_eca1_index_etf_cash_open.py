"""ECA1 causal ETF-index first-bar discrepancy and after-seal price."""
import unittest
from datetime import date
from .eca1_index_etf_cash_open import (
    START,WEEKS,PAIRS,stamp,entry_event,decision,priced_pair,gross_quote_bps)


def bar(t,o,c):
    return [t,t+300000,o,max(o,c),min(o,c),c,10]


class TestEca1(unittest.TestCase):
    def setUp(self):
        self.day=date(2026,9,17)
        self.start=stamp(self.day,9,30)
        self.idx=[bar(self.start,100000,101000)]
        self.etf=[bar(self.start,100000,99000)]
    def test_frozen_pair_and_calendar(self):
        self.assertEqual(PAIRS,{"SPY.US":"US500","QQQ.US":"NAS100"})
        self.assertEqual(WEEKS,26)
        self.assertEqual(START,date(2026,5,4))
        self.assertEqual(stamp(self.day,9,35)-stamp(self.day,9,30),300000)
    def test_causal_entry_works_without_any_future_bars(self):
        d=entry_event(self.day,self.idx,self.etf)
        self.assertEqual(d["state"],"CAUSAL_0935_EVENT")
        self.assertEqual(d["side"],1)
        self.assertEqual(d["etfFirstSide"],-1)
        self.assertEqual(decision(self.day,self.idx,self.etf)["state"],
                         "SIGNAL_EXIT_MONITOR_BARS_MISSING")
    def test_no_signal_on_same_direction_or_zero(self):
        self.assertEqual(entry_event(self.day,self.idx,[bar(self.start,100000,101000)])["state"],
                         "NO_OPENING_PRICE_DISCOVERY_DISCREPANCY")
        self.assertEqual(entry_event(self.day,self.idx,[bar(self.start,100000,100000)])["state"],
                         "NO_OPENING_PRICE_DISCOVERY_DISCREPANCY")
    def test_1000_later_index_reversal_early_exit(self):
        idx=self.idx[:]
        for i in range(1,6):
            o=101000-300*(i-1)
            c=101000-300*i
            idx.append(bar(self.start+i*300000,o,c))
        d=decision(self.day,idx,self.etf)
        self.assertEqual(d["state"],"SIGNAL_WITH_CAUSAL_EXIT")
        self.assertEqual(d["exit"],"10:05")
        self.assertTrue(d["invalidation"])
    def test_no_invalidation_holds_to_1030(self):
        idx=self.idx[:]
        for i in range(1,6):
            o=101000+100*(i-1)
            idx.append(bar(self.start+i*300000,o,o+100))
        d=decision(self.day,idx,self.etf)
        self.assertEqual(d["exit"],"10:30")
        self.assertFalse(d["invalidation"])
    def test_independent_quote_sides_and_age(self):
        at=100000
        self.assertEqual(priced_pair([[at-5000,100]],[[at-9000,101]],at),
                         [100,101])
        self.assertIsNone(priced_pair([[at-30000,100]],[[at-100,101]],at))
        self.assertIsNone(priced_pair([[at-10,105]],[[at-15,104]],at))
        self.assertIsNone(priced_pair([[at+100,100]],[[at-10,101]],at))
    def test_real_crossing_bps_costs_more_than_mid(self):
        values=gross_quote_bps([100000,100200],[100400,100600],1)
        self.assertLess(values[1],values[0])
        self.assertEqual(gross_quote_bps([100000,100200],[100400,100600],0),[0.,0.])

if __name__=="__main__":
    unittest.main()

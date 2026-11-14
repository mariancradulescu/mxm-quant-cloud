"""Focused CAC1 causality and matched denominator regression tests."""
import unittest
from datetime import date
from .cac1_us_cash_close import feature,stamp,M5,summarize


def bars(day,hour,minute,sign):
    start=stamp(day,hour,minute)
    return [[start+i*M5,start+(i+1)*M5,
             100+i*sign,101+i*sign,99+i*sign,100+(i+1)*sign]
            for i in range(3)]


class CAC1CausalTests(unittest.TestCase):
    def test_aligned_closing_bars_signal(self):
        d=date(2026,6,5)
        z=feature(d,bars(d,15,15,1),bars(d,15,15,1),15,15)
        self.assertEqual((z["state"],z["side"],z["etfSide"]),
                         ("CAUSAL_ALIGNED",1,1))

    def test_disagreement_abstains_but_exposes_own_direction(self):
        d=date(2026,6,5)
        z=feature(d,bars(d,13,15,-1),bars(d,13,15,1),13,15)
        self.assertEqual(z["side"],0)
        self.assertEqual(z["etfSide"],1)

    def test_no_future_bars_used(self):
        d=date(2026,6,5)
        i=bars(d,15,15,1); f=bars(d,15,15,1)
        before=feature(d,i,f,15,15)
        i.extend(bars(d,15,35,-50)); f.extend(bars(d,15,35,-50))
        self.assertEqual(feature(d,i,f,15,15),before)

    def test_missing_instead_of_backfill(self):
        d=date(2026,6,5)
        z=feature(d,bars(d,15,15,1)[:2],bars(d,15,15,1),15,15)
        self.assertEqual(z["state"],"UNKNOWN_M5_MISSING")

    def test_only_complete_denominator_no_zero_imputation(self):
        m={"central":{k:0.0 for k in
           ("close","midday","etfOnly","long","short","cash")},
           "adverse":{k:0.0 for k in
           ("close","midday","etfOnly","long","short","cash")}}
        m["adverse"]["close"]=-1.0
        s=summarize([{"state":"UNKNOWN_ETF_BID_ASK","week":0,"closeSide":1,
                      "middaySide":1},
                     {"state":"COMPLETE_COMPARABLE_DAY","week":1,
                      "closeSide":1,"middaySide":0,"money":m}])
        self.assertEqual(s["scheduledDays"],2)
        self.assertEqual(s["completeComparableDays"],1)
        self.assertEqual(s["adverseCurrentContractNetEur"]["close"],-1.0)


if __name__=="__main__":
    unittest.main()

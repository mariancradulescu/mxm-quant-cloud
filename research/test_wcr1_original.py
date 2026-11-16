"""WCR1 synthetic invariants. Never access original broker or outcomes."""
import unittest
from datetime import date,timedelta
from .wcr1_original_reopen_source import calendar,last_pair,stamp,START
from .wcr1_original_native_eur_readback import sides

class TestWcr1(unittest.TestCase):
    def test_52_fixed_sundays_and_dst(self):
        all_=list(calendar())
        self.assertEqual(len(all_),52)
        self.assertEqual(all_[0][1],date(2025,11,16))
        self.assertEqual(all_[-1][1],date(2026,11,8))
        for i,sun,bars,marks in all_:
            self.assertEqual(sun,START+timedelta(weeks=i))
            self.assertEqual(len(bars),4)
            self.assertEqual([x[0] for x in bars],["BTCUSD","BTCUSD","US500","US500"])
            self.assertEqual([x[1] for x in bars],
                [stamp(sun-timedelta(days=2),17),stamp(sun,17),
                 stamp(sun,18,5),stamp(sun,18,15)])
            self.assertEqual(marks,(stamp(sun,18,20),stamp(sun,18,40),
                                    stamp(sun,19,0),stamp(sun,19,20)))
            self.assertTrue(all(bars[j][1] < marks[0] for j in range(4)))
            self.assertTrue(all(marks[j]<marks[j+1] for j in range(3)))
            self.assertEqual(marks[-1]-marks[0],60*60000)
        self.assertNotEqual(stamp(date(2026,3,1),18)-stamp(date(2026,3,1),17),
                            0)
        self.assertEqual(stamp(date(2026,3,15),18)-stamp(date(2026,3,15),17),
                         3600000)
        self.assertNotEqual(stamp(date(2026,3,1),18)-stamp(date(2026,3,15),18),
                            14*86400000)

    def test_source_only_signal_no_future_prices(self):
        self.assertEqual(sides([100,120,1000,1001]),
                         dict(wcr1=1,ownMomentum=1,long=1,short=-1,cash=0,
                              oppositeBtcDiagnostic=-1))
        self.assertEqual(sides([120,100,1001,1000])["wcr1"],-1)
        self.assertEqual(sides([100,100,1000,1000])["wcr1"],0)
        self.assertIsNone(sides([None,120,1000,1001]))
        self.assertIsNone(sides([100,120,0,1001]))

    def test_strict_side_age_and_no_crossed(self):
        at=100000
        self.assertEqual(last_pair([[(80000,100),(90000,102)],
                                    [(90001,103)]],at),
                         [[90000,102],[90001,103]])
        self.assertIsNone(last_pair([[(79000,100)],[(90000,110)]],at))
        self.assertIsNone(last_pair([[(90000,110)],[(90000,105)]],at))
        self.assertIsNone(last_pair([[(90000,110)],[]],at))

if __name__=="__main__":
    unittest.main()

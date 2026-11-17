"""Synthetic presignal timing/source tests; NEVER access broker or score future PnL."""
import unittest
from datetime import date
from .ivp1_original_presignal_pilot import (
    calendar,pilot_calendar,utc,expected_bar_ends,pair,sign,MIN,MAX_CALLS)
class TestIvp1(unittest.TestCase):
    def test_325_weekday_and_50_fixed_pilot(self):
        all_=list(calendar())
        p=pilot_calendar()
        self.assertEqual(len(all_),325)
        self.assertEqual(len(p),50)
        self.assertEqual(all_[0],(date(2026,8,17),utc(date(2026,8,17),14)))
        self.assertEqual(all_[-1],(date(2026,11,13),utc(date(2026,11,13),18)))
        self.assertEqual(p[0],(date(2026,11,2),utc(date(2026,11,2),14)))
        self.assertEqual(p[-1],all_[-1])
        self.assertTrue(all(d.weekday()<5 and t==utc(d,h) for d,t in all_
                            for h in [t//3600000%24]))
        self.assertEqual(MAX_CALLS,800)
        self.assertEqual(7+50*(2+3*2*2),707)

    def test_disjoint_vix_before_us500_own_and_future(self):
        for _,t in pilot_calendar():
            v=expected_bar_ends("VIX",t)
            u=expected_bar_ends("US500",t)
            self.assertEqual(v,[t-j*MIN for j in (35,30,25,20,15)])
            self.assertEqual(u,[t-j*MIN for j in (35,30,25,20,15,10,5,0)])
            self.assertEqual(max(v),u[4])
            self.assertEqual(min(v),min(u))
            self.assertEqual(len(v)+len(u),13)
            self.assertTrue(all(x<=t for x in v+u))
            self.assertLess(max(v),t)
            self.assertLess(max(u),t+90000)
            self.assertEqual(t+31*MIN+30000-(t+90000),30*MIN)
        self.assertEqual(-sign(22,21),-1)
        self.assertEqual(-sign(21,22),1)
        self.assertEqual(-sign(22,22),0)

    def test_quote_price_age(self):
        t=100000
        self.assertEqual(pair([[80000,100],[90000,101]],
                              [[90001,103]],t),[[90000,101],[90001,103]])
        self.assertIsNone(pair([[79000,101]],[[90001,103]],t))
        self.assertIsNone(pair([[90000,105]],[[90001,103]],t))
        self.assertIsNone(pair([[90000,101]],[],t))
if __name__=="__main__":
    unittest.main()

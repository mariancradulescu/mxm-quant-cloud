"""Nonprice tests for CXL1 original source-only presignal pilot."""
import unittest
from datetime import date
from .cxl1_original_feasibility import (
    calendar,pilot_calendar,crypto_features,classification,fresh,clock,START,PILOT_START)

class TestCxl1OriginalFeasibility(unittest.TestCase):
    def test_325_fixed_weekday_schedule_and_no_rollover(self):
        grid=list(calendar())
        self.assertEqual(len(grid),325)
        self.assertEqual(len({d for d,t in grid}),65)
        self.assertEqual(grid[0][0],date(2026,8,17))
        self.assertEqual(grid[-1][0],date(2026,11,13))
        self.assertTrue(all(d.weekday()<5 and t == clock(d,h,m)
            for d,t in grid for h,m in [(8,30),(10,30),(12,30),(14,30),(16,30)]
            if (h,m)== next(x for x in [(8,30),(10,30),(12,30),(14,30),(16,30)] if t==clock(d,*x))))
        self.assertEqual(len(pilot_calendar()),50)
        self.assertEqual(pilot_calendar()[0][0],PILOT_START)
        self.assertEqual(pilot_calendar()[-1][0],date(2026,11,13))

    def test_vol_normalization_and_lag_class(self):
        btc=[10000*(1.001**i) for i in range(289)]
        eth=[3000*(1.0005**i) for i in range(289)]
        zbtc=crypto_features(btc)
        zeth=crypto_features(eth)
        self.assertIsNotNone(zbtc)
        self.assertIsNotNone(zeth)
        self.assertEqual(classification((2.0,20.),(1.0,10.)),1)
        self.assertEqual(classification((-2.0,20.),(-1.0,10.)),-1)
        self.assertEqual(classification((1.0,10.),(2.0,20.)),0)
        self.assertIsNone(classification(None,zeth))
        self.assertIsNone(crypto_features([0]*289))
        self.assertIsNone(crypto_features([100]*288))

    def test_authentic_quote_age_and_cross(self):
        at=100000
        self.assertEqual(fresh([[80000,100],[90000,100]],[[90001,102]],at),
                         [[90000,100],[90001,102]])
        self.assertIsNone(fresh([[79000,100]],[[90001,102]],at))
        self.assertIsNone(fresh([[90000,103]],[[90001,102]],at))
        self.assertIsNone(fresh([[90000,100]],[],at))

if __name__=="__main__":
    unittest.main()

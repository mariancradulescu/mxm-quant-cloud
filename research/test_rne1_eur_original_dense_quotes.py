"""RNE1 dense original EURUSD/NatGas quote causality and clock fixtures."""
import unittest
from datetime import date,timedelta
from .rne1_eur_original_dense_quotes import (SAMPLES,START,WEEKS,MAX_AGE,
    sampled_side,sampled_pair,stamp)

class Rne1DenseQuoteTests(unittest.TestCase):
    def test_26_thursdays_16_clocks(self):
        self.assertEqual(WEEKS,26)
        self.assertEqual(len(SAMPLES),16)
        self.assertEqual(SAMPLES[0],(10,50))
        self.assertEqual(SAMPLES[-1],(12,5))
        for i in range(WEEKS):
            day=START+timedelta(weeks=i,days=3)
            self.assertEqual(day.weekday(),3)
            a=[stamp(day,hh,mm) for hh,mm in SAMPLES]
            self.assertTrue(all(b-a==300000 for a,b in zip(a,a[1:])))
    def test_require_fresh_independent_bid_ask(self):
        t=100000
        self.assertIsNone(sampled_pair([[t-30000,100]],
                                       [[t-5000,104]],t))
        p=sampled_pair([[t-15000,100]],
                       [[t-10000,104]],t)
        self.assertEqual(p['bid']['raw'],100)
        self.assertEqual(p['ask']['ageMs'],10000)
        self.assertIsNone(sampled_pair([[t-1000,105]],[[t-2000,104]],t))
        self.assertIsNone(sampled_pair([[t+1000,100]],[[t-1000,104]],t))
    def test_exact_dst_wall_clocks(self):
        a=stamp(date(2026,5,7),10,50)
        b=stamp(date(2026,10,29),10,50)
        self.assertEqual((a//1000)%60,0)
        self.assertEqual((b//1000)%60,0)
    def test_locked_price_observed_not_rejected(self):
        p=sampled_pair([[80000,100]],[[80000,100]],90000)
        self.assertEqual(p['bid']['raw'],p['ask']['raw'])

if __name__=="__main__":
    unittest.main()

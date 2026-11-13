"""QPI1 synthetic quote event causality and continuation-exit tests."""
import unittest
from .qpi1_quote_event_quality import (
    pressure, pair, price_bps, decide, direction
)

class Qpi1Tests(unittest.TestCase):
    def test_directional_quote_update_count_not_endpoint_displacement(self):
        b = [(0,100), (1000,101), (2000,102), (3000,101), (4000,102)]
        a = [(0,104), (1000,105), (2000,106), (3000,105), (4000,106)]
        score,n,c=pressure(b,a,0,4000)
        self.assertEqual(n,8)
        self.assertAlmostEqual(score,0.5)
        self.assertEqual(c['bidUp'],3)
        self.assertEqual(c['bidDown'],1)
    def test_asof_never_sees_future_quote(self):
        self.assertEqual(pair([(0,100),(30000,101)],
                              [(0,104),(30000,105)],10000),(100,104))
        self.assertIsNone(pair([(0,100)],[(0,104)],30000))
    def test_no_updates_produces_no_signal(self):
        self.assertEqual(pressure([(0,100),(1000,100)],
                                  [(0,104),(1000,104)],0,1000)[0],0)
    def test_price_crossing_not_gross(self):
        x=price_bps((100,102),(103,105),1)
        self.assertAlmostEqual(x[0],(104-101)/101*10000)
        self.assertAlmostEqual(x[1],(103-102)/101*10000)
        self.assertGreater(x[0],x[1])
    def test_fully_causal_policy_and_flip_exit(self):
        t=600000
        b=[(0,10000),(30000,10010),(100000,10020),
           (300000,10030),(590000,10040),(600000,10045)]
        a=[(x,y+10) for x,y in b]
        # entry t+1m and opposite quote changes t..t+10m
        bb=[(600000,10045),(655000,10044),(660000,10043),
            (700000,10042),(1190000,10035),
            (1200000,10035),(1790000,10050),(1800000,10050),
            (2400000,10048)]
        aa=[(x,y+10) for x,y in bb]
        out=decide(b,a,bb,aa,t)
        self.assertEqual(out['state'],'CANDIDATE_PRICED')
        self.assertEqual(out['side'],1)
        self.assertEqual(out['reason'],'QUOTE_PRESSURE_REVERSAL')
        self.assertEqual(out['minutes'],10)
        self.assertTrue(out['fixed_complete'])

if __name__=="__main__":
    unittest.main()

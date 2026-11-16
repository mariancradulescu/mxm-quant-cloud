"""EWL1 as-of endpoint, warmup, label maturity and financial boundary tests.

Purely technical, synthetic clocks and prices. Never economic qualification.
"""
import math
import unittest

from .decode import need
from .guard import CaptureContractError
from .ewl1_endpoint_learning import (
    PROTOCOL, HOUR, WEEK, DAY, frozen, feature, label_ready,
    phase_at, analog_prediction, week_summary, economic_pair)


class EndpointChronology(unittest.TestCase):
    def setUp(self):
        self.p,self.hash,self.b=frozen()

    def bars(self,n=60):
        return [
            [i*HOUR,(i+1)*HOUR,110000+2*i,110015+2*i,
             109985+2*i,110004+2*i,200+i] for i in range(n)
        ]

    def test_frozen_26_13_13_and_labeled_independence(self):
        self.assertEqual(self.b[1]-self.b[0],26*WEEK)
        self.assertEqual(self.b[2]-self.b[1],13*WEEK)
        self.assertEqual(self.b[3]-self.b[2],13*WEEK)
        self.assertTrue(self.p["timeline"]["alreadyGloballyExposed"])
        self.assertFalse(self.p["timeline"]["independentConfirmation"])
        self.assertEqual(self.p["model"]["maxAnalogs"],64)

    def test_features_only_see_completed_h1_before_endpoint(self):
        bars=self.bars()
        t=feature(bars,45)
        self.assertIsNotNone(t)
        self.assertEqual(t["clock"],46*HOUR)
        copy=[row[:] for row in bars]
        copy[46][5]+=10000000
        copy[46][3]+=10000000
        self.assertEqual(feature(copy,45),t)

    def test_session_gaps_are_not_synthesized(self):
        bars=self.bars()
        gap=[row[:] for row in bars]
        for i in range(43,60):
            gap[i][0]+=2*HOUR
            gap[i][1]+=2*HOUR
        self.assertIsNotNone(feature(gap,53))
        # latest four H1 gaps invalidate a feature, not silently impute it.
        gap[52][0]+=HOUR
        self.assertIsNone(feature(gap,53))

    def test_label_release_only_after_real_maturity_plus_embargo(self):
        t=80*HOUR
        self.assertFalse(label_ready(t,t+4*HOUR))
        self.assertTrue(label_ready(t,t+5*HOUR))
        self.assertFalse(label_ready(t,t+5*HOUR-1))
        self.assertFalse(label_ready(t,t))
        self.assertEqual(phase_at(self.b[1]-2*HOUR,self.b[1]+2*HOUR,self.b),
                         "LABEL_CROSSES_PHASE")

    def test_analog_distribution_neighbors_are_past_only_contract(self):
        # Caller may pass only mature pool; fixed kNN itself never inspects
        # any "future" key and is stable against added unrelated metadata.
        pool=[]
        t=250*DAY
        for i in range(64):
            past={"t":t-(i+2)*HOUR,"feature":(0.,0.,0.,0.,0.,0.),
                  "_outcome":(0.1,110000,110010,0.2,0.3)}
            pool.append(past)
        full=analog_prediction(pool,(0.,0.,0.,0.,0.,0.),0.0,True,t)
        self.assertGreater(full["mean"],0)
        self.assertTrue(0<full["up"]<1)
        self.assertGreaterEqual(full["effectiveSupport"],1)
        self.assertGreater(full["riskLongQ90"],0)

    def test_economic_proxy_conversions_not_executable_net(self):
        gross,after=economic_pair("EURUSD",1,110000,110100,110000,1,0.06)
        self.assertAlmostEqual(gross,1000*(100/100000)/1.1)
        self.assertLess(after,gross)
        jpy,jpyAfter=economic_pair("USDJPY",1,15000000,15010000,
                                    110000,15010000,0.06)
        self.assertAlmostEqual(jpy,1000*(10000/100000)/150.1/1.1)
        self.assertLess(jpyAfter,jpy)

    def test_zero_observation_weeks_do_not_disappear(self):
        s=week_summary([],self.b,"SELECTION","seBase","seFull")
        self.assertEqual(s["meanWeeklyDifference"],0)
        self.assertEqual(s["weeksWithScoredEndpoints"],0)
        self.assertEqual(s["phaseWeeks"],13)


if __name__=="__main__":
    unittest.main()

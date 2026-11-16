"""HXP1 technical isolation tests; no original secret, source or market result."""
import json
import math
import unittest
from .hxp1_fx_peer_delay import (PROTOCOL, HOUR, WEEK, invariant_policy,
                                series_feature, peer_feature, next_outcome,
                                signed_payoff_eur, bound_weekly, phase_at)


class Hxp1Invariant(unittest.TestCase):
    def setUp(self):
        self.p=json.loads(PROTOCOL.read_text())

    def test_exact_phases_and_nonindependence(self):
        bounds=invariant_policy(self.p)
        self.assertEqual(bounds[1]-bounds[0],26*WEEK)
        self.assertEqual(bounds[2]-bounds[1],13*WEEK)
        self.assertEqual(bounds[3]-bounds[2],13*WEEK)
        self.assertFalse(self.p["chronology"]["independentConfirmation"])
        self.assertTrue(self.p["chronology"]["allHistoricalHXC1PeriodsPreviouslyExposed"])

    def test_no_maturity_crossing(self):
        a=invariant_policy(self.p)
        self.assertEqual(phase_at(a[1]-3*HOUR,a[1]-HOUR,a),"TRAIN")
        self.assertEqual(phase_at(a[1]-HOUR,a[1]+HOUR,a),"UNKNOWN_MATURITY")

    def test_causal_data_and_missing_hours(self):
        a={i*HOUR:(i*HOUR-HOUR,100000+i,100000+i+1) for i in range(1,28)}
        self.assertIsNotNone(series_feature(a,27*HOUR))
        self.assertIsNotNone(peer_feature(a,27*HOUR))
        self.assertEqual(next_outcome(a,25*HOUR),(100026,100028))
        a.pop(10*HOUR)
        self.assertIsNone(series_feature(a,27*HOUR))

    def test_price_conversion_not_full_net(self):
        gross,floor=signed_payoff_eur(1,110000,110100,110000,1000,0.06)
        self.assertGreater(gross,0)
        self.assertLess(floor,gross)
        self.assertAlmostEqual(gross,1000*(100/100000)/1.1,places=9)

    def test_zero_signal_weeks_not_omitted(self):
        res=bound_weekly([],26,13,"eventCommissionFloorEur")
        self.assertEqual(res["weeklyLower95Eur"],0)
        self.assertEqual(len(res["weeklyTotalsEur"]),13)
        self.assertEqual(res["weeksWithSignals"],0)


if __name__=="__main__":
    unittest.main()

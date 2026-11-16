"""BTI1 synthetic causality and orthogonality invariants. No broker/custody."""
import unittest

from .bti1_temporal_burstiness import (
    asof, pair, timing_feature, revisions, side_bps, paired_weekly_lower,
)


class TestBti1(unittest.TestCase):
    @staticmethod
    def sequence(times, start):
        result = [[0, start]]
        for i, t in enumerate(times, 1):
            result.append([t, start+i])
        result.append([600000, start+len(times)])
        return result

    def test_identical_qpi_up_down_counts_and_endpoint_price_distinct_timing(self):
        uniform = [50000,150000,250000,350000,450000,550000]
        clustered = [1000,2000,3000,4000,5000,6000]
        a = timing_feature([self.sequence(uniform, 100),
                            self.sequence(uniform, 104)], 600000)
        b = timing_feature([self.sequence(clustered, 100),
                            self.sequence(clustered, 104)], 600000)
        self.assertEqual((a["N"],a["signedCount"],a["ownMomentumBps"]),
                         (b["N"],b["signedCount"],b["ownMomentumBps"]))
        self.assertEqual(a["state"],"QUIET")
        self.assertEqual(b["state"],"BURST")
        self.assertLess(a["collision"], 0.20)
        self.assertGreaterEqual(b["collision"], 0.20)

    def test_burst_feature_cannot_see_after_decision(self):
        uniform = [50000,150000,250000,350000,450000,550000]
        before = [self.sequence(uniform, 100),self.sequence(uniform,104)]
        f = timing_feature(before,600000)
        late = [s + [[600001, 999999]] for s in before]
        self.assertEqual(f,timing_feature(late,600000))

    def test_future_asof_not_allowed_and_freshness_required(self):
        self.assertEqual(asof([[100,100],[30000,101]],110),100)
        self.assertIsNone(asof([[100,100],[30000,101]],20101))
        self.assertIsNone(pair([[0,100]],[[21000,101]],20000))

    def test_unchanged_quote_not_revision(self):
        t,up,down = revisions([[-1,99],[1,99],[2,100],[3,100],[4,99]],0,10)
        self.assertEqual(t,[2,4])
        self.assertEqual((up,down),(1,1))

    def test_cash_never_pays_slippage_and_crossing_less_than_gross(self):
        entry=(100.0,102.0)
        exit_=(101.0,103.0)
        self.assertEqual(side_bps(entry,exit_,0),(0.0,0.0))
        gross,cross = side_bps(entry,exit_,1)
        self.assertGreater(gross,cross)

    def test_weekly_ci_fails_when_increment_not_positive(self):
        self.assertLess(paired_weekly_lower([-1.0,1.0,0.0,-2.0]),0.0)


if __name__ == "__main__":
    unittest.main()

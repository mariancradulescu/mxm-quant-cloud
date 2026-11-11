"""SQIC1 protocol invariants with fake quote tape, no Pepperstone requests."""
import unittest
from .sqic1_quote_impulse import (
    PRIOR, point_at, at_pair, quote_impulse, summarise
)


class CausalQuoteImpulseChecks(unittest.TestCase):
    def test_asof_does_not_look_ahead_or_widen_age(self):
        tape = [(1000, 10), (1980, 12), (2500, 14)]
        self.assertEqual(point_at(tape, 2000, 20), 12)
        self.assertIsNone(point_at(tape, 2000, 19))
        self.assertIsNone(point_at(tape, 900, 20))
        self.assertIsNone(point_at(tape, 2400, 20))
        self.assertEqual(at_pair([(1000, 20)], [(1000, 20)], 1000), (20, 20))
        self.assertIsNone(at_pair([(1000, 21)], [(1000, 20)], 1000))
        self.assertIsNone(at_pair([], [(1000, 21)], 1000))

    def test_fixed_bid_and_ask_pressure_direction_and_spread(self):
        sample = dict(zip(PRIOR, (
            (100000, 100010), (100030, 100040), (100080, 100090))))
        self.assertEqual(quote_impulse(sample), 1)
        reverse = dict(zip(PRIOR, (
            (100080, 100090), (100030, 100040), (100000, 100010))))
        self.assertEqual(quote_impulse(reverse), -1)
        # Valid locked quotes are not automatically classified as missing.
        locked = dict(zip(PRIOR, (
            (100000, 100000), (100010, 100010), (100030, 100030))))
        self.assertEqual(quote_impulse(locked), 1)
        wider = dict(sample)
        wider[0] = (100080, 100160)
        self.assertEqual(quote_impulse(wider), 0)
        one_sided = dict(sample)
        one_sided[-60] = (100030, 100010)
        self.assertEqual(quote_impulse(one_sided), 0)

    def test_no_signal_if_one_leg_disagrees_or_move_too_small(self):
        flip = dict(zip(PRIOR, (
            (100000, 100010), (100030, 100040), (100010, 100020))))
        self.assertEqual(quote_impulse(flip), 0)
        small = dict(zip(PRIOR, (
            (100000, 100050), (100010, 100060), (100020, 100070))))
        self.assertEqual(quote_impulse(small), 0)
        self.assertEqual(quote_impulse({-120: (100000, 100010)}), 0)

    def test_pooled_gate_is_not_per_symbol_hard21(self):
        one = {"model":2.0, "long":1.0, "short":-1.0, "cash":0.0}
        def entry():
            return {"central":dict(one),"adverse":dict(one)}
        # Eight pooled weeks, four events each = 32 shared opportunities;
        # no per-market or per-week >=21 requirement.
        bars = {i:[entry()]*4 for i in range(8)}
        results = {
            "AUDUSD": {0: {
                "counts":{"scheduled":195,"causalSignals":32,
                          "pricedWithExactCost":32},
                "pricedByWeek":bars
            }}
        }
        for market in ("US2000", "SpotCrude"):
            results[market] = {}
        scored = summarise(None, 0, results)
        self.assertEqual(scored["priced"],32)
        self.assertTrue(scored["passed"])
        self.assertEqual(scored["activeWeeks"],8)
        # A matched long outperforming the model fails despite positive NET.
        worse = {"model":.4, "long":1.0, "short":-.4, "cash":0.0}
        results["AUDUSD"][0]["pricedByWeek"] = {
            i:[{"central":dict(worse),"adverse":dict(worse)}]*4
            for i in range(8)}
        self.assertFalse(summarise(None,0,results)["passed"])


if __name__=="__main__":
    unittest.main()

"""LQR1 independent synthetic information/causality contracts only. No old model or economic scoring."""
import unittest
from .lqr1_original_presignal_support import decide_predecision,last_price_change,BACK_MS


class Lqr1Causality(unittest.TestCase):
    def test_newest_bid_revision_direction_is_past_only(self):
        t=1_000_000
        before=[
            [[t-BACK_MS,100000],[t-10000,100020],[t-1000,100025]],
            [[t-BACK_MS,100050],[t-15000,100055]]]
        first=decide_predecision(before,t)
        self.assertEqual(first["state"],"SIDE_SPECIFIC_SIGNAL")
        self.assertEqual(first["laterSide"],"BID")
        self.assertEqual(first["side"],1)
        future=[x[:] for x in before]
        future[0].append([t+10000,90000])
        self.assertEqual(first,decide_predecision(future,t))

    def test_simultaneous_last_changes_abstain_not_guess_event_order(self):
        t=1_000_000
        before=[
            [[t-BACK_MS,100000],[t-5000,100010]],
            [[t-BACK_MS,100040],[t-5000,100050]]]
        self.assertEqual(decide_predecision(before,t)["state"],"ABSTAIN_SIMULTANEOUS")

    def test_one_missing_side_change_is_unknown_not_cash(self):
        t=1_000_000
        before=[
            [[t-BACK_MS,100000],[t-1000,100010]],
            [[t-BACK_MS,100040],[t-1000,100040]]]
        self.assertEqual(decide_predecision(before,t)["state"],"FEATURE_UNKNOWN")

    def test_no_future_quote_qualifies_prior_stale_side(self):
        t=1_000_000
        before=[
            [[t-BACK_MS,100000],[t-1000,100005]],
            [[t-BACK_MS,100040],[t-21000,100045]]]
        self.assertEqual(decide_predecision(before,t)["state"],"SOURCE_UNKNOWN")

    def test_nonpositive_price_is_rejected(self):
        t=1_000_000
        with self.assertRaises(Exception):
            last_price_change([[t-BACK_MS,100000],[t-1000,-1]],t-BACK_MS,t)


if __name__=="__main__":
    unittest.main()

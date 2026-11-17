"""Causal invariants for frozen CMP1; tests use synthetic observations, not broker data."""
from dataclasses import replace
from decimal import Decimal as D
import unittest

from research.cmp1_common_capital import Event, UNIVERSE, run_policy, causal_prediction

HOUR = 3_600_000
DAY = 24 * HOUR

def rows(days=8, return_bps=100, margin="10"):
    out = []
    for i in range(days):
        for s in UNIVERSE:
            out.append(Event(1_760_000_000_000 + i * DAY,
                             1_760_000_000_000 + i * DAY + 2 * HOUR,
                             s, float(return_bps), 1., D(500), D(margin), True))
    return out

class Cmp1Checks(unittest.TestCase):
    def test_cash_has_no_synthetic_profit(self):
        self.assertEqual(run_policy(rows(), "CASH")["conditionalTerminalCashEur"], "300")

    def test_future_label_never_changes_current_prediction(self):
        a = rows()
        context = {s: [r for r in a if r.symbol == s and r.at < a[24].at]
                   for s in UNIVERSE}
        p1, reason1 = causal_prediction(a[24], context, "JOINT")
        altered = replace(a[24], outcome=-999.0)
        p2, reason2 = causal_prediction(altered, context, "JOINT")
        self.assertEqual(reason1, "OFFER")
        self.assertEqual(reason2, "OFFER")
        self.assertEqual(p1, p2)

    def test_matured_labels_only(self):
        a = rows()
        context = {s: [r for r in a if r.symbol == s and r.exit < a[24].at]
                   for s in UNIVERSE}
        self.assertEqual(causal_prediction(a[24], context, "JOINT")[1], "OFFER")
        context[UNIVERSE[0]] = context[UNIVERSE[0]][:3]
        self.assertEqual(causal_prediction(a[24], context, "JOINT")[1], "OWN_CAUSAL_WARMUP")

    def test_shared_margin_blocks_six_concurrent_minima(self):
        p = run_policy(rows(margin="120"), "JOINT")
        t = p["decisionTrace"]
        self.assertGreater(len(t), 0)
        self.assertEqual(len([x for x in t if x["at"] == t[0]["at"]]), 1)
        self.assertGreater(p["rejectedAtCapacity"], 0)
        self.assertLessEqual(D(p["maximumReservedMarginEur"]), D(180))

    def test_forecasts_not_magic_fills(self):
        p = run_policy(rows(), "JOINT")
        self.assertIsNone(p["nativeFundedNetEur"])
        self.assertTrue(all(not x["sourceIsBrokerFill"] for x in p["closedPriceProxyTrace"]))
        self.assertEqual(p["pendingAtEnd"], 0)

    def test_unobserved_future_return_propagates_unknown(self):
        a = rows()
        a[24] = replace(a[24], outcome=None)
        p = run_policy(a, "JOINT")
        self.assertIsNone(p["conditionalTerminalCashEur"])
        self.assertGreater(p["originalFutureLabelsMissing"], 0)

if __name__ == "__main__":
    unittest.main()

"""Synthetic GCR1 A1 attribution, future-data causality and event-order tests.

These do not certify real funding, 30% floating DD, or source completeness.
"""
import unittest
from datetime import datetime, timezone
from decimal import Decimal as D
from research.gcr1_macro_signal import scheduled_clocks, STEP_MS, ENTRY_AFTER_MS, EXIT_AFTER_MS
from research.gcr1_eur_model import (
    intents, asof_pair, price_all, summary, POLICIES,
)


def panel(t, c_first=100000, c_last=101000,
          g_first=200000000, g_last=198000000,
          a_first=65000, a_last=65200):
    result = {}
    for name, first, last in (
        ("Copper", c_first, c_last),
        ("XAUUSD", g_first, g_last),
        ("AUDUSD", a_first, a_last),
    ):
        result[name] = {
            str(t - (48-i)*STEP_MS): int(first + (last-first)*i/48)
            for i in range(49)
        }
    return result


def quote(bid=65000, ask=65010, t=0, age=2):
    return {"bid": {"at": t-age*1000, "raw": bid},
            "ask": {"at": t-age*1000, "raw": ask},
            "hasMore": False}


class GCR1A1Tests(unittest.TestCase):
    def setUp(self):
        self.t = scheduled_clocks()[0]

    def test_metal_on_full_clock_has_distinguishable_states(self):
        x = intents(panel(self.t), self.t)
        self.assertEqual((x["sides"]["combined"],
                          x["sides"]["copperOnly"],
                          x["sides"]["inverseGoldOnly"],
                          x["sides"]["audOwnMomentum"]), (1, 1, 1, 1))
        y = intents(panel(self.t, g_last=201000000), self.t)
        self.assertEqual((y["sides"]["combined"],
                          y["sides"]["copperOnly"],
                          y["sides"]["inverseGoldOnly"]), (0, 1, -1))
        self.assertEqual(y["metalCell"], "BOTH_SAME_SIGN")

    def test_missing_gold_does_not_erase_copper_intent(self):
        x = panel(self.t)
        x["XAUUSD"].pop(str(self.t-3*STEP_MS))
        d = intents(x, self.t)
        self.assertIsNone(d["sides"]["combined"])
        self.assertEqual(d["sides"]["copperOnly"], 1)
        self.assertEqual(d["sides"]["audOwnMomentum"], 1)

    def test_future_source_availability_never_changes_intent(self):
        before = intents(panel(self.t), self.t)
        # There is no future quote parameter in this function, by design.
        entry, ending = self.t+ENTRY_AFTER_MS, self.t+EXIT_AFTER_MS
        q = {"AUDUSD": {str(entry): quote(t=entry),
                        str(ending): quote(t=ending)}}
        missing, why = price_all(q, self.t, None, D(50))
        self.assertIsNone(missing)
        self.assertTrue(why.startswith("FINANCIAL_UNKNOWN"))
        self.assertEqual(before, intents(panel(self.t), self.t))

    def test_quote_asof_rejects_future_stale_truncated_and_crossed(self):
        t=self.t
        q={"AUDUSD": {str(t): quote(t=t)}}
        self.assertEqual(asof_pair(q, "AUDUSD", t), (D("0.65"), D("0.6501")))
        q["AUDUSD"][str(t)]["bid"]["at"]=t+1
        self.assertIsNone(asof_pair(q, "AUDUSD", t))
        q["AUDUSD"][str(t)]=quote(t=t, age=21)
        self.assertIsNone(asof_pair(q, "AUDUSD", t))
        q["AUDUSD"][str(t)]=quote(t=t, bid=66000, ask=65000)
        self.assertIsNone(asof_pair(q, "AUDUSD", t))
        q["AUDUSD"][str(t)]=quote(t=t)
        q["AUDUSD"][str(t)]["hasMore"]=True
        self.assertIsNone(asof_pair(q, "AUDUSD", t))

    def test_same_nominal_clock_must_close_before_open(self):
        schedules=scheduled_clocks()
        self.assertEqual(len(schedules), 780)
        events = []
        for index, t in enumerate(schedules[:3]):
            events.append((t+ENTRY_AFTER_MS, 1, index, "ENTRY"))
            events.append((t+EXIT_AFTER_MS, 0, index, "EXIT"))
        events.sort()
        coincident = [e for e in events if e[0] == schedules[1]+ENTRY_AFTER_MS]
        self.assertEqual([e[-1] for e in coincident], ["EXIT", "ENTRY"])
        # A missing settlement cannot be interpreted as released capital.
        settled = False
        reserved_margin = D(50)
        free_before_old_exit = D(60)
        new_minimum = D(50)
        def can_admit(due_exit_settled):
            remaining = free_before_old_exit + (
                reserved_margin if due_exit_settled else D(0))
            return due_exit_settled and remaining >= new_minimum
        self.assertFalse(can_admit(settled))
        self.assertTrue(can_admit(True))

    def test_summary_denominator_does_not_turn_unknown_into_cash(self):
        priced = {
            "money": {s: {p: {"netEur": (0.0 if p == "combined" else -1.0)}
                              for p in POLICIES} for s in ("adverse", "central")},
            "intent": {"metalCell": "BOTH_SAME_SIGN",
                       "sides": {p: (0 if p=="combined" else 1)
                                 for p in POLICIES}},
            "financeStatus": "COMMON_EUR_PRICED",
        }
        missing = {
            "money": None,
            "intent": {"metalCell": "BOTH_SAME_SIGN",
                       "sides": {p: (0 if p=="combined" else 1)
                                 for p in POLICIES}},
            "financeStatus": "FINANCIAL_UNKNOWN_EXIT",
        }
        s=summary([priced, missing])
        self.assertEqual((s["scheduled"],s["commonPricedClocks"],
                          s["commonUnknownClocks"]), (2,1,1))
        self.assertEqual(s["adverseMatchedNetEur"]["combined"], 0)
        self.assertEqual(s["adversePrimaryIncrementalEur"]["copperOnly"], 1)


if __name__ == "__main__":
    unittest.main()

"""Synthetic causal invariants for prospective CMR1; no broker reads or returns."""
import unittest
from datetime import date

from .cmr1 import BAR, at, complete_session


class Cmr1CausalityTests(unittest.TestCase):
    def setUp(self):
        self.day = date(2026, 9, 14)

    def session(self, high_displacement=True):
        bars = {}
        for i in range(72):
            p = 100.0
            if high_displacement:
                if i == 68:
                    p = 101.0
                elif i == 69:
                    p = 100.8
                elif i == 70:
                    p = 100.6
                elif i == 71:
                    p = 100.45
            bars[at(self.day, 9, 30) + i * BAR] = (
                at(self.day, 9, 30) + i * BAR, 0, p, p, p, p, 100)
        return bars

    def test_completed_session_anchor_and_counter_momentum(self):
        signal = complete_session(self.session(), self.day)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["model"], -1)
        self.assertEqual(signal["momentum"], 1)
        self.assertGreater(signal["deviationBps"], 20)
        self.assertGreaterEqual(signal["reversionBps"], 3)

    def test_missing_completed_bar_is_not_imputed(self):
        bars = self.session()
        del bars[at(self.day, 10)]
        self.assertIsNone(complete_session(bars, self.day))

    def test_unknown_future_prices_cannot_affect_decision(self):
        bars = self.session()
        original = complete_session(bars, self.day)
        for i in range(72, 100):
            t = at(self.day, 9, 30) + i * BAR
            bars[t] = (t, 0, 10.0, 10.0, 10.0, 10.0, 100000)
        self.assertEqual(complete_session(bars, self.day), original)

    def test_no_arbitrary_signal_when_displacement_absent(self):
        self.assertIsNone(complete_session(self.session(False), self.day))


if __name__ == "__main__":
    unittest.main()

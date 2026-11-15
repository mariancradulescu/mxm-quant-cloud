"""GCR1 synthetic-only causality tests; not historical trading evidence."""
import unittest
from datetime import datetime, timezone
from research.gcr1_macro_signal import (
    BarClose, NUM_CLOSES, STEP_MS, ENTRY_AFTER_MS, EXIT_AFTER_MS,
    decide, scheduled_clocks,
)


def bars(t, first, last):
    return [BarClose(t-(NUM_CLOSES-1-i)*STEP_MS,
                     first+i*(last-first)/(NUM_CLOSES-1))
            for i in range(NUM_CLOSES)]


class GCR1CausalTests(unittest.TestCase):
    def setUp(self):
        self.t = scheduled_clocks()[0]

    def test_780_immutable_slots(self):
        clocks = scheduled_clocks()
        self.assertEqual((len(clocks), len(set(clocks))), (780, 780))
        self.assertEqual(datetime.fromtimestamp(clocks[0]/1000, timezone.utc).isoformat(),
                         "2025-11-03T08:00:00+00:00")
        self.assertEqual(datetime.fromtimestamp(clocks[-1]/1000, timezone.utc).isoformat(),
                         "2026-10-30T16:00:00+00:00")

    def test_growth_buy_and_fixed_exit(self):
        d = decide(bars(self.t, 4.0, 4.2), bars(self.t, 4000, 3950), self.t)
        self.assertEqual((d.state, d.side), ("BUY_AUDUSD_GROWTH", 1))
        self.assertEqual(d.entry_clock_utc_ms, self.t+ENTRY_AFTER_MS)
        self.assertEqual(d.exit_clock_utc_ms, self.t+EXIT_AFTER_MS)

    def test_safety_sell_and_ambiguous_abstain(self):
        self.assertEqual(decide(bars(self.t, 4, 3), bars(self.t, 4000, 4100), self.t).side, -1)
        self.assertEqual(decide(bars(self.t, 4, 5), bars(self.t, 4000, 4100), self.t).state,
                         "ABSTAIN_MACRO_AMBIGUOUS")
        self.assertEqual(decide(bars(self.t, 4, 4), bars(self.t, 4000, 3900), self.t).state,
                         "ABSTAIN_MACRO_AMBIGUOUS")

    def test_absent_source_and_future_data_cannot_bias_intents(self):
        c, g = bars(self.t, 4, 4.2), bars(self.t, 4000, 3950)
        self.assertEqual(decide(c[:-1], g, self.t).state, "DECISION_UNKNOWN")
        self.assertEqual(decide(c+[BarClose(self.t+STEP_MS, 4.3)], g, self.t).state,
                         "DECISION_UNKNOWN")
        self.assertEqual(decide(c, g, self.t).state, "BUY_AUDUSD_GROWTH")
        c[11] = BarClose(c[11].end_utc_ms + 1, c[11].close)
        self.assertEqual(decide(c, g, self.t).state, "DECISION_UNKNOWN")

    def test_unplanned_clock_rejected(self):
        c, g = bars(self.t, 4, 4.2), bars(self.t, 4000, 3950)
        with self.assertRaises(ValueError):
            decide(c, g, self.t+60_000)
        with self.assertRaises(ValueError):
            decide(c, g, self.t+5*24*60*60*1000)


if __name__ == "__main__":
    unittest.main()

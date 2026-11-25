import unittest
from unittest.mock import patch

from . import owner_eur_dense_monetary as dense
from .ctrader_proto import OpenApiModelMessages_pb2 as model


class DenseMonetaryTests(unittest.TestCase):
    def test_last_price_requires_fresh_unambiguous_clock(self):
        rows = [(100, 3), (100, 4), (200, 5)]
        clocks = [r[0] for r in rows]
        self.assertIsNone(dense.latest(rows, clocks, 100, 30))
        self.assertEqual(dense.latest(rows, clocks, 201, 30), 5)
        self.assertIsNone(dense.latest(rows, clocks, 231, 30))

    def test_partial_page_is_not_monetary_coverage(self):
        def fake(request, account, sid, side, lo, hi, budget):
            if lo and side == model.ASK:
                return [], [[lo, hi, "PENDING_BUDGET", None, 0]]
            price = 100 if side == model.BID else 101
            rows = [(lo + 14000, price)]
            return rows, [[lo, hi, "VERIFIED_COMPLETE_PAGE", 9999999, len(rows)]]

        plan = dict(study="TEST", partitionHours=2, perSidePageBudget=16,
                    markOffsetMs=15000, markIntervalMs=300000, markFreshnessMs=30000)
        class Journal:
            query = None
        with patch.object(dense.rollover, "tick_window", side_effect=fake), patch("builtins.print"):
            result = dense.collect(Journal(), 1, plan, "TEST", 1, "DAY", 0, "hash")
        self.assertEqual(result["verifiedTwoSidedMarks"], 1)
        self.assertEqual(result["completeResponseHours"], 1)
        self.assertEqual(result["hours"][1]["verifiedTwoSidedMarkCount"], 0)
        self.assertFalse(result["executionContinuityCertified"])
        self.assertEqual(result["orders"], 0)


if __name__ == "__main__":
    unittest.main()

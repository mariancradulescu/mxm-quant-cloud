"""Synthetic ORX1 algorithm verification; not historical market evidence."""
import unittest
from research.orx1_recorded_oracle import optimum_one_slot, maximum_count_one_slot

class Orx1Tests(unittest.TestCase):
    def test_weighted_interval_optimum_is_not_greedy_profit(self):
        xs = [
            dict(PositionId="A", OpenedAt=1, ClosedAt=5, NetEur=3.0),
            dict(PositionId="B", OpenedAt=2, ClosedAt=3, NetEur=2.0),
            dict(PositionId="C", OpenedAt=3, ClosedAt=5, NetEur=2.0),
        ]
        chosen=optimum_one_slot(xs)
        self.assertEqual([x["PositionId"] for x in chosen], ["B", "C"])
        self.assertAlmostEqual(sum(x["NetEur"] for x in chosen), 4.0)
        self.assertEqual(len(maximum_count_one_slot(xs)), 2)
    def test_overlap_and_zero_values(self):
        xs=[
            dict(PositionId="a", OpenedAt=1, ClosedAt=9, NetEur=1.0),
            dict(PositionId="b", OpenedAt=2, ClosedAt=8, NetEur=0.0),
            dict(PositionId="c", OpenedAt=9, ClosedAt=12, NetEur=0.8),
        ]
        self.assertEqual([x["PositionId"] for x in optimum_one_slot(xs)], ["a","c"])
        self.assertEqual(optimum_one_slot([]), [])

if __name__=="__main__":
    unittest.main()

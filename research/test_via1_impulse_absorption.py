"""Synthetic, no-source-money checks for VIA1 causal decision boundaries."""
import unittest
from .via1_impulse_absorption import frozen_decision, exit_reason


class Via1Tests(unittest.TestCase):
    def test_upward_shock_absorption(self):
        points = [100 + i * .01 for i in range(19)]
        points[16], points[17], points[18] = 101., 102., 101.8
        direction, start, extreme = frozen_decision(points)
        self.assertEqual(direction, -1)
        self.assertEqual(start, points[15])
        self.assertEqual(extreme, 102.)
        self.assertEqual(exit_reason(start, direction, start, extreme), "target")
        self.assertEqual(exit_reason(102.01, direction, start, extreme), "invalidation")
        self.assertIsNone(exit_reason(101., direction, start, extreme))

    def test_downward_shock_absorption(self):
        points = [100 - i * .01 for i in range(19)]
        points[16], points[17], points[18] = 99., 98., 98.2
        direction, start, extreme = frozen_decision(points)
        self.assertEqual(direction, 1)
        self.assertEqual(start, points[15])
        self.assertEqual(extreme, 98.)
        self.assertEqual(exit_reason(start, direction, start, extreme), "target")
        self.assertEqual(exit_reason(97.99, direction, start, extreme), "invalidation")

    def test_no_signal_on_persistent_direction(self):
        points = [100 + i * .01 for i in range(19)]
        points[16], points[17], points[18] = 101., 102., 103.
        self.assertIsNone(frozen_decision(points))


if __name__ == "__main__":
    unittest.main()

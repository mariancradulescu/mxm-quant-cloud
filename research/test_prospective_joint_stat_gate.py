"""Prospective dual-HAC statistical gates: no SFX1 replay."""
import unittest
from .prospective_joint_stat_gate import assess_prospective_weekly

def series(a,b,n=52,k=4,missing=False):
    return [{"week":w,"grossBps":a+1,"benchmarkGrossBps":b+1,
         "centralNetBps":a+.5 if not missing else None,
         "adverseNetBps":a if not missing else None,
         "adverseBenchmarkNetBps":b if not missing else None}
        for w in range(n) for _ in range(k)]

class FutureJointGateChecks(unittest.TestCase):
    def test_cash_positive_benchmark_wins_gives_no_promotion(self):
        z=assess_prospective_weekly(series(1,2),0,52,2)
        self.assertGreater(z.cashAdverseWeeklyHacBonferroniLowerBps,0)
        self.assertLess(z.benchmarkIncrementalWeeklyHacBonferroniLowerBps,0)
        self.assertFalse(z.passesBothProspectiveStatGates)

    def test_incremental_positive_absolute_net_negative_gives_no_promotion(self):
        z=assess_prospective_weekly(series(-1,-3),0,52,2)
        self.assertLess(z.cashAdverseWeeklyHacBonferroniLowerBps,0)
        self.assertGreater(z.benchmarkIncrementalWeeklyHacBonferroniLowerBps,0)
        self.assertFalse(z.passesBothProspectiveStatGates)

    def test_both_positive_multiple_tests(self):
        z=assess_prospective_weekly(series(3,1),0,52,3)
        self.assertTrue(z.passesBothProspectiveStatGates)
        self.assertEqual(z.testsInFamily,6)
        self.assertAlmostEqual(z.familywiseOneSidedAlpha,.05/6)
        self.assertAlmostEqual(z.adverseIncrementalMeanBps,2)

    def test_unknown_costs_fail_closed_gross_still_reports(self):
        z=assess_prospective_weekly(series(3,1,missing=True),0,52,3)
        self.assertEqual(z.grossMeanBps,4)
        self.assertFalse(z.costAndConversionEvidenceComplete)
        self.assertIsNone(z.cashAdverseWeeklyHacBonferroniLowerBps)
        self.assertIsNone(z.benchmarkIncrementalWeeklyHacBonferroniLowerBps)
        self.assertFalse(z.passesBothProspectiveStatGates)

    def test_missing_independent_week_counts_and_support_gate(self):
        sparse=series(3,1,n=4,k=2)
        z=assess_prospective_weekly(sparse,0,52,2)
        self.assertEqual(z.completeSignals,8)
        self.assertEqual(z.activeWeeks,4)
        self.assertFalse(z.passesBothProspectiveStatGates)

    def test_invalid_predeclared_multiplicity(self):
        for bad in (0,-1,21):
            with self.assertRaises(ValueError):
                assess_prospective_weekly(series(3,1),0,52,bad)

if __name__=="__main__":unittest.main()

"""Synthetic BCF1/F2 contracts. Never contact Pepperstone or inspect returns."""
import unittest
from . import bcf1_source as bcf
from .f2_preflight import prospective_economic_futility


class BondSourceAndFutilityContract(unittest.TestCase):
    def test_exante_exact_source_clocks_budget_and_holdout_boundary(self):
        p=bcf.p_read()
        times=bcf.periods(p)
        quotes=bcf.clocks(p)
        self.assertEqual(len(times),53)
        self.assertEqual(len(quotes),13)
        self.assertEqual(times[0][0],1762128000000)
        self.assertEqual(times[51][1],1793577600000)
        self.assertEqual(times[-1],(1793577600000,1793937600000,"chronological_new_unscored"))
        self.assertEqual(3+4+len(times)*2+len(quotes)*2*2,165)
        self.assertTrue(p["historicalSource"]["allHistoricalCalendarWeeksGloballyExposed"])
        self.assertTrue(p["newChronologicalSource"]["notToBeScoredOrUnsealedForPredictionWithoutPriorIndependentProtocol"])
        self.assertFalse(p["sourceFeasibility"]["noScoredReturns"])
        # noScoredReturns must be TRUE to prohibit outcome leakage.
    
    def test_cost_unknown_is_not_zero_or_approval(self):
        a=[-5+.1*(i%3) for i in range(26)]
        b=[-2+.1*(i%4) for i in range(26)]
        unknown=prospective_economic_futility(a,b,model_cost_context_complete=False,
            predeclared_comparisons=6,active_development_weeks=26)
        self.assertIsNone(unknown["economicallyFutile"])
        self.assertFalse(unknown["scoreSelectionAllowed"])

    def test_negative_upper_bound_stops_before_selection(self):
        a=[-5+.1*(i%5) for i in range(26)]
        b=[-2+.1*(i%4) for i in range(26)]
        result=prospective_economic_futility(a,b,model_cost_context_complete=True,
            predeclared_comparisons=6,active_development_weeks=26)
        self.assertEqual(result["status"],"FUTILE_STOP_BEFORE_SELECTION")
        self.assertLess(result["upperAdverseNetBps"],0)
        self.assertFalse(result["scoreSelectionAllowed"])

    def test_positive_upper_bound_not_profit_certificate(self):
        a=[.3+(i%4-1.5)*4 for i in range(26)]
        b=[.3+(i%6-2.5)*3 for i in range(26)]
        r=prospective_economic_futility(a,b,model_cost_context_complete=True,
            predeclared_comparisons=6,active_development_weeks=26)
        self.assertEqual(r["status"],"UPPER_BOUND_ALLOWS_PLAUSIBILITY_NOT_EVIDENCE")
        self.assertTrue(r["statusIsNotProofOfPositiveEdge"])
        self.assertFalse(r["financeCertified"])
        self.assertFalse(r["independenceCertified"])
    
    def test_short_or_zero_variance_blocks_scoring(self):
        r=prospective_economic_futility([-5.]*13,[-3.]*13,
            model_cost_context_complete=True,predeclared_comparisons=6,active_development_weeks=13)
        self.assertEqual(r["status"],"NOT_INFORMATIVE_NO_ECONOMIC_PROMOTION")
        r=prospective_economic_futility([-5.]*26,[-3.]*26,
            model_cost_context_complete=True,predeclared_comparisons=6,active_development_weeks=26)
        self.assertFalse(r["scoreSelectionAllowed"])

if __name__=="__main__":
    unittest.main()

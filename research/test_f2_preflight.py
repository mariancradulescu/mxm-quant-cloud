"""CI F2: honest source-coverage feasibility, detectable effect and distinction."""
import copy,unittest
from .f2_preflight import assess,causal_sign

class F2Checks(unittest.TestCase):
    def test_existing_source_preflight_rejects_premature_scoring_without_stopping_exploration(self):
        r=assess()
        self.assertEqual(r["authenticOldM5Bars"],836087)
        self.assertEqual(r["sourceInstruments"],12)
        self.assertEqual(r["accountRoster"],5339)
        self.assertEqual(r["oldObservedFx5MinMarginEur"],164.0)
        self.assertEqual(r["oldObservedFx5PlusGoldMarginEur"],339.58)
        self.assertIsNone(r["powerMdeBps"])
        self.assertTrue(r["exploratoryFeaturesAllowed"])
        self.assertFalse(r["protectedEconomicScoringAllowed"])
        self.assertFalse(r["fundedNetPromotionAllowed"])
        self.assertFalse(r["independentConfirmation"])
        self.assertIn("INFORMATIVE_WEEKS_OR_PILOT_VARIANCE_UNKNOWN",r["blockReasons"])
        self.assertIn("MIN_VOLUME_CURRENT_COST_AND_FX_NOT_COMPLETE",r["blockReasons"])
    def test_predictor_can_differ_from_unconditional_benchmark_without_peeking(self):
        alternating=[1 if i%2==0 else -1 for i in range(21)]
        self.assertEqual(causal_sign(alternating),-alternating[-1])
        self.assertEqual(causal_sign([1]*21),0)
        self.assertEqual(causal_sign(alternating),causal_sign(alternating+[999999][:-1]))
    def test_power_uses_effective_weeks_and_bonferroni_not_aggregated_bars(self):
        pilot=dict(effectiveSelectionWeeks=10,selectionWeeklyStandardDeviationBps=5,
                   requiredEconomicallyDetectableEffectBps=1)
        r=assess(pilot=pilot)
        self.assertIn("POWER_INSUFFICIENT_FOR_ECONOMIC_MINIMUM_EFFECT",r["blockReasons"])
        self.assertGreater(r["powerMdeBps"],1)
        positive=assess(pilot=dict(pilot,requiredEconomicallyDetectableEffectBps=20))
        self.assertNotIn("POWER_INSUFFICIENT_FOR_ECONOMIC_MINIMUM_EFFECT",positive["blockReasons"])
        self.assertFalse(positive["protectedEconomicScoringAllowed"])  # costs/margin still unknown
    def test_qualifying_claims_and_capital_never_bypass_native(self):
        import json
        from pathlib import Path
        p=json.loads(Path("research/f2_screening_candidate.json").read_text())
        bad=copy.deepcopy(p);bad["capital"]["prospectiveInitialEur"]=200
        self.assertIn("ACTIVE_EUR300_CAPITAL_MISMATCH",assess(candidate=bad)["blockReasons"])
        bad=copy.deepcopy(p);bad["status"]="QUALIFIED";bad["statusClaims"]["netQualified"]=True
        self.assertIn("SCIENTIFIC_STATUS_OR_NET_PROMOTION_FORBIDDEN",assess(candidate=bad)["blockReasons"])
        bad=copy.deepcopy(p);bad["calendar"]["independentConfirmationWeeks"]=13
        self.assertIn("GLOBALLY_EXPOSED_MUST_NOT_BE_CALLED_INDEPENDENT",assess(candidate=bad)["blockReasons"])
        bad=copy.deepcopy(p);bad["capital"]["nativeFundedAuthority"]="PYTHON_BOOK"
        self.assertIn("NATIVE_PHYSICAL_FINANCIAL_AUTHORITY_MISSING",assess(candidate=bad)["blockReasons"])
if __name__=="__main__":unittest.main()

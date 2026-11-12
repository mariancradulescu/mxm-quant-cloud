"""Real-source regression checks for preregistered JAR1; no broker calls."""
from hashlib import sha256
import json
from pathlib import Path
import unittest

from research.jar1_exposed_opening_reversal import (
    EXPECTED_SOURCE_SHA256, evaluate, hac_lower,
)


class Jar1OriginalSourceChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source=Path("docs/AIP1_AUTHENTIC_RESULT.json").read_bytes()
        assert sha256(source).hexdigest()==EXPECTED_SOURCE_SHA256
        cls.live=json.loads(source)
        cls.report=json.loads(Path("docs/JAR1_AUTHENTIC_EXPOSED_RESULT_20261112.json").read_text())
        cls.result=evaluate(cls.live)

    def test_exact_source_and_causal_coverage(self):
        self.assertEqual(self.result["SourceScheduledSelectionClocks"],287)
        self.assertEqual(self.result["CausalSignalCandidates"],274)
        self.assertEqual(self.result["CompleteCostAndReturnProxyLabels"],274)
        self.assertEqual(self.result["UnobservedCandidatePayoffs"],0)
        self.assertEqual(self.result["RejectedBeforeEntryByReason"],
                         {"NO_PRIOR_SELECTION_EVENT":6,"LATEST_PRIOR_SOURCE_ZERO_MOVE":1,
                          "LATEST_PRIOR_SOURCE_TOO_OLD":6})

    def test_independent_summary_parity(self):
        actual=self.result["PolicyFullCalendarEqualWeekAdverseMeanBps"]
        expected=self.report["MeanAdverseNetProxyBpsByPolicy"]
        for key in expected:
            self.assertAlmostEqual(actual[key],expected[key],places=10)
        self.assertAlmostEqual(self.result["PrimaryAdverseVsCashHac3Bonferroni"]["meanBps"],
                               self.report["FullCalendarHac3AdverseVsCash"]["meanBps"],places=10)
        self.assertEqual(sum(1 for w in self.result["Weekly"]
                             if w["CompleteProxyLabels"]>=21),4)

    def test_negative_outcome_cannot_promote(self):
        self.assertFalse(self.result["PredeclaredExploratoryEconomicScreenPassed"])
        self.assertLess(self.result["EarlySixWeeksMeanAdverseBps"],0)
        self.assertLess(self.result["LateSevenWeeksMeanAdverseBps"],0)
        self.assertLess(self.result["PrimaryAdverseVsCashHac3Bonferroni"]["multiplicityAdjustedLowerBps"],0)
        self.assertFalse(self.result["FundedEUR300PortfolioExecuted"])
        self.assertFalse(self.result["IndependentConfirmation"])

    def test_future_audit_rows_do_not_affect_selection(self):
        altered=json.loads(json.dumps(self.live))
        start=int(altered["Protocol"]["selectionEnd"])
        for row in altered["Forecasts"]:
            if int(row["At"])>=start:
                row["OutcomeBps"]="9999999999"
                row["CostBps"]="0"
        replay=evaluate(altered)
        self.assertEqual(self.result,replay)


if __name__ == "__main__":
    unittest.main()

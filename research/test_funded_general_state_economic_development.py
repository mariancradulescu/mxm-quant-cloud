"""Synthetic-only safeguards for the NEW general-state public financial receipt."""
import json
import unittest

from . import funded_history_economic_development as d
from .guard import CaptureContractError
from .integrated_market_source import FUNDED_HISTORY


class GeneralStateReceiptChecks(unittest.TestCase):
    @staticmethod
    def report():
        books, net, weeks = {}, {}, {}
        for variant in d.GENERAL_VARIANTS:
            fin = {
                "Boundary": {"RightCensored": False, "CashEur": 300},
                "CompleteModeledNetEur": 0,
                "RealizedLedgerNetEur": 0, "GrossEur": 0,
                "Costs": {"Commission": 0, "Spread": 0, "Slippage": 0,
                          "Conversion": 0, "Financing": 0},
                "FinancingUnverifiedTrips": 0, "UnknownPathTrips": 0,
                "UnknownEquityClocks": 0, "MaxMarginEur": 0,
                "MaxPlannedRiskEur": 0, "SampledFloatingDrawdownPercent": 0,
                "KnownSampledEquityClocks": 0,
                "ContinuousFloatingDrawdownCertified": False,
                "MaxConcurrent": 0, "StopRiskOverruns": 0,
                "PrivateAccountAndQuotes": "NEVER_EXPORT"
            }
            books[variant] = {"Book": {
                "Financial": fin, "CompletedTradesByWeek": {"2026-W33": 0},
                "Hard21ByWeek": {"2026-W33": False}, "WeeksWithHard21": 0,
                "BothWeeksHard21": False, "ByFamily": {}},
                "BySymbol": {}, "ActionValues": ["NEVER_EXPORT"]}
            net[variant] = 0
            weeks[variant] = [0]
        scenario = {
            "Books": books, "CompleteModeledNetEur": net,
            "CompleteComparableWeeklyNetEur": weeks,
            "ContextMinusControlsEur": {}, "CalibrationMetrics": {},
            "MatchedForecastRows": {}, "LabelCoverage": [],
            "ModelCohorts": [], "PrimaryAdverseComparisons": None
        }
        return {
            "SourceRun": d.ORIGINAL_RUN, "InputSha256": "b" * 64,
            "CostEvidence": "CONDITIONAL_COST_MODEL_FIXED_ORIGINAL_BROKER_SNAPSHOT",
            "ResearchMechanism": "GENERAL_CLOSED_STATE_BIDIRECTIONAL_NEW_RESEARCH_NOT_ORIGINAL_RUN",
            "BrokerNetCertified": False, "IndependentConfirmation": False,
            "Start": FUNDED_HISTORY.start, "End": FUNDED_HISTORY.end,
            "Status": "FINANCED_POLICY_DEVELOPMENT",
            "Result": {
                "Evidence": "GENERAL_STATE_HISTORICAL_DEVELOPMENT_EXPOSED",
                "IndependentConfirmation": False, "Orders": 0,
                "CloudActivation": False, "EvaluationStart": 1, "End": 2,
                "EvaluationCoverage": [], "Central": scenario, "Adverse": scenario
            }
        }

    def test_new_receipt_only_exposes_general_policies_not_private_facts(self):
        report = self.report()
        public = d.extract_safe_economics(
            report, "b" * 64, ["EURUSD"], {}, {}, generalized=True)
        self.assertEqual(set(public["Scenarios"]["Central"]["Policies"]),
                         set(d.GENERAL_VARIANTS))
        self.assertNotIn("NEVER_EXPORT", json.dumps(public))
        self.assertFalse(public["IndependentConfirmation"])
        self.assertFalse(public["BrokerNetCertified"])
        self.assertEqual(public["Scenarios"]["Adverse"]["Policies"][d.GENERAL_CONTEXT]["DeltaVsCashEur"], "0")

    def test_original_study_cannot_pass_new_identity_gate(self):
        report = self.report()
        report["ResearchMechanism"] = "EXACT_LEGACY_FUNDED_ACTION_RESEARCH"
        with self.assertRaises(CaptureContractError):
            d.extract_safe_economics(report, "b" * 64, ["EURUSD"], {}, {}, generalized=True)

    def test_censored_capital_and_money_are_not_promoted(self):
        report = self.report()
        policy = report["Result"]["Central"]["Books"][d.GENERAL_CONTEXT]["Book"]["Financial"]
        policy["Boundary"]["RightCensored"] = True
        policy["CompleteModeledNetEur"] = None
        report["Result"]["Central"]["CompleteModeledNetEur"][d.GENERAL_CONTEXT] = None
        public = d.extract_safe_economics(
            report, "b" * 64, ["EURUSD"], {}, {}, generalized=True)
        assert public["Scenarios"]["Central"]["Policies"][d.GENERAL_CONTEXT]["CapitalFinalEur"] is None
        assert public["Scenarios"]["Central"]["Policies"][d.GENERAL_CONTEXT]["DeltaVsCashEur"] is None


if __name__ == "__main__":
    unittest.main()

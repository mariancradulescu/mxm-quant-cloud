"""Receipted-only 18-market economic screen, NEVER a strategy backtest."""
import unittest
from copy import deepcopy
from .owner_existing_multiasset_cost_envelope import actual_receipt_envelope,raw_sources

class CrossClassExistingCostEnvelopeTests(unittest.TestCase):
    def test_original_18_market_source_and_5_classes(self):
        z=actual_receipt_envelope()
        self.assertEqual(z["distinctContractSymbolsReviewed"],18)
        self.assertEqual(z["sourceClassCounts"],
                         {"crypto":1,"energy":3,"equity":1,"fx":9,"index":4})
        self.assertEqual(z["newBrokerRequests"],0)
        self.assertFalse(z["originalClosedXua1OrSfx1OutcomesRescored"])
        self.assertIsNone(z["economicConclusions"]["actualPortfolioNetEur"])
        self.assertEqual(z["contracts"]["EURJPY"]["sourceRoundTripCommissionUsdAtMinUnits"],"0.06")
        self.assertIsNone(z["contracts"]["JPYX"]["sourceObservedSpreadBps"])
        self.assertTrue(z["contracts"]["GBPJPY"]["xua1NegativeExactStrategyVerdictRetained"])

    def test_actual_broker_contract_margins_under_stress(self):
        z=actual_receipt_envelope()
        m=z["economicConclusions"]
        self.assertEqual(m["usdxOneSourceMinPositionConsumesCapitalPercent"],"61.2800")
        self.assertEqual(m["minMarginNatGasPlusUsdxAtStressLeavesEur"],"1.42")
        self.assertEqual(m["minMarginAllThreeMcs1Exceeds210StressEquityEur"],"6.57")
        positions={tuple(x["symbols"]):x for x in z["selectedActualSourceMarginConfigurations"]}
        self.assertEqual(positions[("NatGas","USDX","AMD.US")]["observedAsOfMinMarginSumEur"],"216.57")
        self.assertFalse(positions[("NatGas","USDX","AMD.US")]["stress210SourceDateMinimumMarginFits"])
        self.assertTrue(positions[("NatGas","HK50","AMD.US")]["stress210SourceDateMinimumMarginFits"])
        self.assertGreater(z["distinctThreeClassCombinationsUnderIllustrativeStress210"],0)
        self.assertFalse(m["systemHard21Certified"])

    def test_original_one_snapshot_is_not_an_adverse_distribution(self):
        z=actual_receipt_envelope()
        q=z["illustrativeCurrentSingleSnapshotCostHurdles"]
        self.assertEqual(q["NatGas"]["illustrativeCentralGrossBreakEvenBps"],"17.1574130")
        self.assertEqual(q["NatGas"]["illustrativeAdverseGrossBreakEvenBps"],"23.209884")
        self.assertEqual(q["USDX"]["illustrativeCentralGrossBreakEvenBps"],"7.8767345")
        self.assertEqual(q["USDX"]["illustrativeAdverseGrossBreakEvenBps"],"10.835646")
        self.assertEqual(q["AMD.US"]["minVolumeCommissionAtIllustrativeAmdUsd200Bps"],"20.000")
        self.assertEqual(q["AMD.US"]["illustrativeCentralGrossBreakEvenBps"],"43.0168870")
        self.assertEqual(q["AMD.US"]["illustrativeAdverseGrossBreakEvenBps"],"51.022516")
        for x in q.values():
            self.assertTrue(x["notObservedHistoricalCostDistribution"])
            self.assertTrue(x["notPredictiveGrossOrNet"])

    def test_public_executed_receipt_recomputed_from_original_source_docs(self):
        import json
        from pathlib import Path
        from decimal import Decimal as D
        derived=actual_receipt_envelope()
        receipt=json.loads(Path(
            "docs/OWNER_EXECUTED_MULTI_ASSET_COST_CAPITAL_SCREEN_20261108.json").read_text())
        self.assertEqual(receipt["sourceMarketCount"],derived["distinctContractSymbolsReviewed"])
        self.assertEqual(receipt["sourceClasses"],derived["sourceClassCounts"])
        self.assertEqual(receipt["threeDistinctAssetClassesIllustrativelyUnderEUR210Stress"],
                         derived["distinctThreeClassCombinationsUnderIllustrativeStress210"])
        self.assertEqual(receipt["threeDistinctAssetClassesIllustrativelyUnderEUR210Stress"],227)
        for actual,expected in zip(
            receipt["combinationsAtOneSourceMinimumVolume"],
            derived["selectedActualSourceMarginConfigurations"]):
            self.assertEqual(actual["symbols"],expected["symbols"])
            self.assertEqual(D(str(actual["sourceDateSumMarginEUR"])),
                             D(expected["observedAsOfMinMarginSumEur"]))
            self.assertEqual(D(str(actual["stressHeadroomEUR210"])),
                             D(expected["stress210StaticHeadroomBeforeCostsEur"]))
            self.assertEqual(actual["stress210Fits"],
                             expected["stress210SourceDateMinimumMarginFits"])
            self.assertFalse(actual["financedCertified"])
        for symbol,scenario in derived["illustrativeCurrentSingleSnapshotCostHurdles"].items():
            observed=receipt["costBreakEvenHurdlesSourceOneSnapshotPlusDeclaredHypotheticalFriction"][symbol]
            self.assertAlmostEqual(observed["illustrativeCentralGrossHurdleBps"],
                  float(scenario["illustrativeCentralGrossBreakEvenBps"]),places=6)
            self.assertAlmostEqual(observed["illustrativeAdverseGrossHurdleBps"],
                  float(scenario["illustrativeAdverseGrossBreakEvenBps"]),places=6)
            self.assertFalse(observed["distributionProven"])
            self.assertIsNone(observed["modelNetEUR"])
        self.assertIsNone(receipt["economicVerdict"]["forecastGrossBps"])
        self.assertIsNone(receipt["economicVerdict"]["financedBrokerNetEUR"])
        self.assertFalse(receipt["economicVerdict"]["hard21Proven"])

    def test_source_provenance_failure_closed(self):
        docs=raw_sources()
        broken=deepcopy(docs)
        broken["cma2"]["evidence"]["originalRawRequestResponseIndependentDecryptReadback"]=False
        with self.assertRaises(ValueError):actual_receipt_envelope(broken)
        broken=deepcopy(docs)
        del broken["cma2"]["candidates"]["JPYX"]
        with self.assertRaises(ValueError):actual_receipt_envelope(broken)

if __name__=="__main__":unittest.main()

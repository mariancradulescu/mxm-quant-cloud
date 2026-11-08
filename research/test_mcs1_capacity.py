"""No invented signal frequency or funding from as-of original CMA2 terms."""
import unittest
from .mcs1_capacity import inspect_capacity
class Mcs1CapacityTest(unittest.TestCase):
    def test_nominal_frozen_clock_rate_and_cost_floor(self):
        r=inspect_capacity()
        self.assertEqual(r["nominalMaximumWeeklyDecisions"],105)
        self.assertEqual(r["nominalEligibleH1DecisionClocksPerWeekByInstrument"],
                         {"NatGas":40,"USDX":40,"AMD.US":25})
        self.assertEqual(r["minimumSignalAndFundingConversionRateFromNominalClocks"],"0.2")
        self.assertEqual(r["sumOfSourceDateOneMinPositionMarginsEur"],"216.57")
        self.assertEqual(r["hypotheticalHeadroomBeforeCommissionsAndFloatingDrawdownEur"],"83.43")
        hurdles=r["illustrativeSingleSpreadConditionalMinimumGrossHurdlesBps"]
        self.assertEqual(hurdles["NatGas"]["illustrativeCentralCostBps"],"17.1574130")
        self.assertEqual(hurdles["NatGas"]["illustrativeAdverseCostBps"],"23.209884")
        self.assertEqual(hurdles["USDX"]["illustrativeCentralCostBps"],"7.8767345")
        self.assertEqual(hurdles["USDX"]["illustrativeAdverseCostBps"],"10.835646")
        self.assertEqual(hurdles["AMD.US"]["illustrativeCentralCostBps"],"43.0168870")
        self.assertEqual(hurdles["AMD.US"]["illustrativeAdverseCostBps"],"51.022516")
        self.assertTrue(r["oneObservedQuotePairPerSymbolNotHistoricalDistribution"])
        self.assertIsNone(r["realHistoricalSignalFrequencies"])
        self.assertIsNone(r["actualBidAskFillEurNet"])
        self.assertEqual(r["actualFundedPositions"],0)
    def test_protocol_clock_hardcode_is_rejected(self):
        import json
        from .mcs1_capacity import P
        p=json.loads(P.read_text())
        p["families"][0]["decisionUtcHours"]=[12]
        with self.assertRaises(ValueError):inspect_capacity(protocol=p)
if __name__=="__main__":unittest.main()

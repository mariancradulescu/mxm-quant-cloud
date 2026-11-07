"""No broker access: CMA1 explicit fee / rollover wire presence tests."""
import unittest
from .ctrader_proto import OpenApiModelMessages_pb2 as model
from .cma1_cost_recovery import contract_terms

class Cma1Tests(unittest.TestCase):
    def symbol(self):
        c=model.ProtoOASymbol(symbolId=42, digits=5, pipPosition=4)
        c.minVolume=100000; c.stepVolume=100000; c.maxVolume=300000
        c.lotSize=10000000; c.tradingMode=0
        c.commissionType=1; c.preciseTradingCommissionRate=0
        c.minCommissionType=1; c.minCommissionAsset="USD"; c.preciseMinCommission=0
        c.pnlConversionFeeRate=0; c.swapLong=-1.1; c.swapShort=0.2
        c.swapCalculationType=0; c.swapPeriod=24; c.swapTime=1320
        c.swapRollover3Days=3; c.chargeSwapAtWeekends=False
        return c
    def test_explicit_zero_is_not_missing(self):
        x=contract_terms(self.symbol(),42,[])
        self.assertTrue(x["allRequiredCommissionWireFieldsExplicit"])
        self.assertEqual(x["preciseCommissionRateWire"],0)
        self.assertEqual(x["pnlConversionFeeRateBasisPointsExplicit"],0)
        self.assertEqual(x["swapTimeMinutesFromUtcMidnightExplicit"],1320)
        self.assertEqual(x["swapRollover3DaysExplicit"],3)
        self.assertFalse(x["chargeSwapAtWeekendsExplicit"])
        self.assertIsNone(x["brokerRoundTripFeeEur"])
    def test_missing_required_fee_not_assumed_zero(self):
        c=self.symbol(); c.ClearField("preciseTradingCommissionRate")
        x=contract_terms(c,42,[])
        self.assertFalse(x["allRequiredCommissionWireFieldsExplicit"])
        self.assertIsNone(x["preciseCommissionRateWire"])
    def test_missing_swap_fields_are_not_assumed_midnight(self):
        c=self.symbol(); c.ClearField("swapTime"); c.ClearField("swapPeriod")
        x=contract_terms(c,42,[])
        self.assertIsNone(x["swapTimeMinutesFromUtcMidnightExplicit"])
        self.assertIsNone(x["swapPeriodHoursExplicit"])
    def test_nonstandard_fees_have_disclosed_scaling(self):
        c=self.symbol(); c.commissionType=3
        x=contract_terms(c,42,[])
        self.assertEqual(x["commissionRateScale"],100000)
        self.assertIsNone(x["brokerRoundTripFeeEur"])
    def test_invalid_volume_and_clock_fail(self):
        c=self.symbol(); c.minVolume=0
        with self.assertRaisesRegex(ValueError,"CMA1_INVALID_VOLUME_GRID"):
            contract_terms(c,42,[])
        c=self.symbol(); c.swapTime=1440
        with self.assertRaisesRegex(ValueError,"CMA1_INVALID_SWAP_CLOCK"):
            contract_terms(c,42,[])
    def test_nonzero_swap_does_not_imply_carry_credit(self):
        x=contract_terms(self.symbol(),42,[])
        self.assertEqual(x["swapLongExplicit"],-1.1)
        self.assertFalse(x["longHorizonFundingCertified"])
        self.assertFalse(x["historicalTariffContinuityCertified"])

if __name__=="__main__":
    unittest.main()

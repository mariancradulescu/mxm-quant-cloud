"""RNE1 protected readback cost arithmetic and no hidden zero-cost fallbacks."""
import unittest
from .rne1_source_financial_preflight import fee_usd,outcome,Unpriced

class FakeContract:
    def __init__(self):
        self.minVolume=10000
        self.stepVolume=10000
        self.maxVolume=1000000
        self.lotSize=100000
        self.preciseTradingCommissionRate=300000000
        self.preciseMinCommission=0
        self.commissionType=2
        self.minCommissionType=2
        self.tradingMode=0
        self.pnlConversionFeeRate=0
        self.minCommissionAsset="USD"
        self.excluded=set()
    def HasField(self,name):
        return name not in self.excluded

class Rne1FinancialTests(unittest.TestCase):
    def test_current_per_lot_commission_is_two_sided(self):
        c=FakeContract()
        from decimal import Decimal as D
        self.assertEqual(fee_usd(c,D("100"),D("3.00")),D("0.3"))
        o=outcome(c,[300000,300010],[300100,300110],1,0.5)
        self.assertAlmostEqual(o["currentCommissionUSD"],0.6)
        self.assertGreater(o["conditionalCostUSD"],0.6)
        self.assertLess(o["conditionalNetUSD"],o["grossUSD"])
    def test_cash_not_charged(self):
        c=FakeContract()
        self.assertEqual(outcome(c,[300000,300010],[300100,300110],0,2.0)
                         ["conditionalNetUSD"],0.0)
    def test_missing_conversion_fee_not_favorable_zero(self):
        c=FakeContract()
        c.excluded.add("pnlConversionFeeRate")
        with self.assertRaises(Unpriced):
            outcome(c,[300000,300010],[300100,300110],1,2.0)
    def test_non_usd_minimum_floor_not_imputed(self):
        from decimal import Decimal as D
        c=FakeContract()
        c.minCommissionType=1
        c.minCommissionAsset="EUR"
        c.preciseMinCommission=100000000
        with self.assertRaises(Unpriced):
            fee_usd(c,D("100"),D("3.0"))
    def test_adverse_slippage_dominates_central(self):
        c=FakeContract()
        central=outcome(c,[300000,300010],[300100,300110],1,0.5)
        adverse=outcome(c,[300000,300010],[300100,300110],1,2.0)
        self.assertLess(adverse["conditionalNetUSD"],central["conditionalNetUSD"])

if __name__=="__main__":
    unittest.main()

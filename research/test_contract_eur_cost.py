"""Contract EUR cost breakdown: official ProtoOACommissionType/MinCommissionType."""
import unittest
from decimal import Decimal as D
from .ctrader_proto import OpenApiModelMessages_pb2 as m
from .contract_eur_cost import fee_at_current_contract,attribute_costs,IncompleteCostEvidence

def contract(kind=1,rate=5000000000,minimum=100000000,asset="USD"):
    c=m.ProtoOASymbol(symbolId=9,digits=5,pipPosition=4)
    c.minVolume=100000
    c.stepVolume=100000
    c.maxVolume=300000
    c.lotSize=10000000
    c.preciseTradingCommissionRate=rate
    c.preciseMinCommission=minimum
    c.commissionType=kind
    c.minCommissionType=1
    c.minCommissionAsset=asset
    c.pnlConversionFeeRate=4
    return c

class CurrentContractCostTests(unittest.TestCase):
    def test_usd_million_notional_and_floor(self):
        c=contract(rate=5000000000,minimum=100000000)
        x=fee_at_current_contract(c,"USD",1000,D("1.1"),{"USD":D("0.9")})
        self.assertEqual(D(x["oneSideContractCommissionEur"]),D("0.9"))
        self.assertEqual(D(x["baseCommissionEur"]),D("0.0495"))
    def test_usd_per_lot(self):
        c=contract(kind=2,rate=2000000000,minimum=0)
        x=fee_at_current_contract(c,"USD",1000,D("1.1"),{"USD":D("0.9")})
        self.assertEqual(D(x["oneSideContractCommissionEur"]),D("0.18"))
    def test_equity_percentage_of_notional_in_quote(self):
        c=contract(kind=3,rate=50000,minimum=0,asset="USD")
        x=fee_at_current_contract(c,"USD",1000,D("2"),{"USD":D("0.9")})
        self.assertEqual(D(x["oneSideContractCommissionEur"]),D("9.0"))
    def test_quote_per_lot_not_mistaken_usd(self):
        c=contract(kind=4,rate=1500000000,minimum=0)
        x=fee_at_current_contract(c,"JPY",1000,D("2"),{"JPY":D("0.006"),"USD":D("0.9")})
        self.assertEqual(D(x["baseCommissionEur"]),D("0.0009"))
    def test_explicit_zero_components_do_not_require_fx(self):
        for kind in (1, 2, 3, 4):
            with self.subTest(kind=kind):
                c=contract(kind=kind,rate=0,minimum=0)
                self.assertEqual(D(fee_at_current_contract(c,"EUR",1000,D("2"),{})
                                   ["oneSideContractCommissionEur"]),0)

    def test_positive_usd_floor_still_requires_fx_with_zero_base(self):
        c=contract(kind=2,rate=0)
        with self.assertRaisesRegex(IncompleteCostEvidence,"MISSING_EUR_ROUTE_USD"):
            fee_at_current_contract(c,"EUR",1000,D("2"),{"EUR":1})

    def test_million_notional_uses_quote_conversion(self):
        c=contract(rate=5000000000,minimum=0)
        self.assertEqual(D(fee_at_current_contract(c,"EUR",1000,D("2"),{"EUR":1})
                           ["oneSideContractCommissionEur"]),D("0.1"))

    def test_missing_fx_route_does_not_default_to_zero(self):
        c=contract(kind=2)
        with self.assertRaises(IncompleteCostEvidence):
            fee_at_current_contract(c,"JPY",1000,D("2"),{"JPY":D(".006")})
    def test_missing_contract_fee_wire_fails_closed(self):
        c=contract()
        c.ClearField("preciseMinCommission")
        with self.assertRaisesRegex(IncompleteCostEvidence,"MISSING_CONTRACT_FIELD_preciseMinCommission"):
            fee_at_current_contract(c,"USD",1000,D("1"),{"USD":D(".9")})
    def test_no_double_spread_for_already_executable_prices(self):
        c=contract(rate=0,minimum=0)
        rates={"USD":D(".9")}
        extra=attribute_costs(c,"USD",1000,D("1.0000"),D("1.0003"),rates,
            execution_bid_ask_already_priced=False)
        implicit=attribute_costs(c,"USD",1000,D("1.0000"),D("1.0003"),rates,
            execution_bid_ask_already_priced=True)
        self.assertEqual(D(extra["additionalSpreadBookedEur"]),D(".27"))
        self.assertEqual(D(implicit["spreadObservedEur"]),D(".27"))
        self.assertEqual(D(implicit["additionalSpreadBookedEur"]),0)
        self.assertIsNone(extra["completeConditionalCostEur"])
        self.assertIsNone(implicit["pnlConversionFeeEur"])
    def test_complete_conditional_case_not_historical_certificate(self):
        c=contract(rate=0,minimum=0)
        x=attribute_costs(c,"USD",1000,D("1"),D("1.0003"),{"USD":D(".9")},
           slippage_eur=D(".1"),financing_eur=D(".2"),gross_realized_eur=D("10"))
        self.assertEqual(D(x["pnlConversionFeeEur"]),D(".004"))
        self.assertEqual(D(x["completeConditionalCostEur"]),D(".574"))
        self.assertIsNone(x["fundedBrokerNetEur"])
        self.assertFalse(x["historicalTermsCertified"])
    def test_volume_below_minimum_and_wrong_grid(self):
        c=contract()
        with self.assertRaises(IncompleteCostEvidence):
            fee_at_current_contract(c,"USD",1001,D("1.1"),{"USD":D(".9")})
        with self.assertRaises(IncompleteCostEvidence):
            fee_at_current_contract(c,"USD",999,D("1.1"),{"USD":D(".9")})
    def test_quote_minimum_fee_as_separate_asset_type(self):
        c=contract(kind=4,rate=0,minimum=1000000000)
        c.minCommissionType=2
        x=fee_at_current_contract(c,"JPY",1000,D("3"),{"JPY":D(".006")})
        self.assertEqual(D(x["oneSideContractCommissionEur"]),D(".06"))
if __name__=="__main__":unittest.main()

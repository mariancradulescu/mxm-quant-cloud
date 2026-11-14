"""SFV1 economic necessity and missingness; no broker/network calls."""
import unittest
from .sfv1_term_pair_preflight import (
    PAIRS,CLOCKS,EXPECTED_CEILING_ALL_PRESENT,LIMIT,classify_pair,summary
)
from .cma2_cost_preflight import asof_spread


def instrument(name, margin, enabled=True, mode=0, short=True):
    return {
        "symbol":name,
        "enabledCurrent":enabled,
        "tradingMode":mode,
        "shortSellingAllowed":short,
        "marginBuyEur":str(margin) if margin is not None else None,
        "marginSellEur":str(margin) if margin is not None else None,
    }


class Sfv1Tests(unittest.TestCase):
    def test_oil_future_single_leg_exceeds_eur300(self):
        r=classify_pair(instrument("SpotBrent",8.76),
                        instrument("Brent-F",843.04))
        self.assertEqual(r["state"],"NECESSARY_CAPITAL_SCREEN_FAILED")
        self.assertFalse(r["futureLegAloneBelow300Eur"])

    def test_pair_below_capital_is_only_preliminary(self):
        r=classify_pair(instrument("JPN225",20),
                        instrument("JPN225-F",17.63))
        self.assertEqual(r["state"],
                         "ONLY_PRELIMINARY_MARGIN_FEASIBLE_TERM_CONVENTION_UNKNOWN")
        self.assertEqual(r["sumSingleLegMinMarginEur"],"37.63")

    def test_absent_market_is_unknown(self):
        self.assertEqual(classify_pair(None,instrument("NatGas-F",20))["state"],
                         "UNKNOWN_MISSING_SYMBOL")

    def test_missing_margin_not_zero(self):
        r=classify_pair(instrument("NatGas",23.88),
                        instrument("NatGas-F",None))
        self.assertEqual(r["state"],"UNKNOWN_ORIGINAL_MARGIN")

    def test_non_openable_and_missing_mode_fail_closed(self):
        r=classify_pair(instrument("NatGas",20,mode=3),
                        instrument("NatGas-F",15))
        self.assertEqual(r["state"],"NOT_CURRENTLY_OPENABLE_TRADING_MODE")
        r=classify_pair(instrument("NatGas",20,mode=None),
                        instrument("NatGas-F",15))
        self.assertEqual(r["state"],"UNKNOWN_TRADING_MODE_WIRE")

    def test_two_short_prohibited_not_a_spread(self):
        r=classify_pair(instrument("NatGas",20,short=False),
                        instrument("NatGas-F",15,short=False))
        self.assertEqual(r["state"],"NO_TWO_LEG_LONG_SHORT_ORIENTATION")

    def test_future_price_tick_cannot_erase_asof_missingness(self):
        # A quote arriving after the decision clock must not be used.
        d=asof_spread([(10100,100),(9980,99)],[(10010,102)],10000,20,20)
        self.assertNotEqual(d["status"],"CAUSAL_PAIRED_SPREAD_OBSERVED")
        r=asof_spread([(9990,100)],[(9990,101)],10000,20,20)
        self.assertEqual(r["status"],"CAUSAL_PAIRED_SPREAD_OBSERVED")

    def test_no_alpha_claim_from_contract_screen(self):
        names=[s for pair in PAIRS for s in pair]
        rows=[instrument(n,15) for n in names]
        z=summary(rows,EXPECTED_CEILING_ALL_PRESENT,"cipher","protocol")
        self.assertEqual(len(z["pairNecessaryCapitalScreens"]),5)
        self.assertTrue(z["futuresExpiryAndRolloverSourceUnknown"])
        self.assertIsNone(z["actualFundedPortfolioEurNet"])
        self.assertEqual(z["ordersSubmitted"],0)
        self.assertEqual(CLOCKS[0],"2026-11-12T08:15:00+00:00")
        self.assertLess(EXPECTED_CEILING_ALL_PRESENT,LIMIT)


if __name__=="__main__":
    unittest.main()

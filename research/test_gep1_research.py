"""Synthetic contract checks for one-shot GEP1 research (never broker evidence)."""
import unittest
from . import gep1_research as g


class GEP1ContractChecks(unittest.TestCase):
    def test_causal_gold_to_jpy_and_usd_to_index_are_distinct(self):
        t = 10*g.H
        def v(a,b):
            return {t-g.H:(t-g.H,t-g.H,0,0,0,a,0),
                    t:(t-g.M5,t,0,0,0,b,0)}
        # gold up -> USDJPY short. USD strengthens on four fixed FX roles
        # -> both stock indices short. No candidate returns are inspected.
        market=dict(XAUUSD=v(2000,2010), USDJPY=v(150,150.1),
                    EURUSD=v(1.1,1.09),GBPUSD=v(1.3,1.29),
                    AUDUSD=v(.7,.69),USDCAD=v(1.3,1.31),
                    US500=v(4000,4010),NAS100=v(16000,16020))
        self.assertEqual(g.signal_side("GOLD_RISK_TO_JPY/USDJPY",market,t),-1)
        self.assertEqual(g.signal_side("USD_FUNDING_TO_US_INDEX/US500",market,t),-1)
        self.assertEqual(g.signal_side("USD_FUNDING_TO_US_INDEX/NAS100",market,t),-1)
        market["XAUUSD"] = v(2000,1990)
        self.assertEqual(g.signal_side("GOLD_RISK_TO_JPY/USDJPY",market,t),1)
        del market["EURUSD"][t-g.H]
        self.assertIsNone(g.signal_side("USD_FUNDING_TO_US_INDEX/US500",market,t))

    def make_rows(self):
        v = {}
        dev, selection = [], []
        for stage, weeks in (("development",26),("selection",26)):
            for w in range(weeks):
                for j in range(5):
                    entry = (1 if stage=="development" else 100)*10**10 + (w*5+j)*g.H
                    due = entry + 60*g.M5
                    # vary blocks to ensure we test a mechanism-specific variance
                    r = (6 + .015*(w%5) + .001*j) / 10000
                    v[entry] = (0, entry,0,0,0,100,0)
                    v[due] = (0,due,0,0,0,100*(2.718281828459045**r),0)
                    (dev if stage=="development" else selection).append((w,1,-1,entry,due))
        return dict(development=dev,selection=selection), {"US500":v}

    def test_power_gate_uses_signed_strategy_and_paired_weekly_variance(self):
        p={"scientific":dict(groups=3,oneSidedComparisonsPerGroup=2,familywiseAlpha=.05,
             powerTarget=.8,minimumDevelopmentActiveWeeks=20,
             minimumSelectionSourceWeeks=20,minimumDevelopmentCompleteSignals=100,
             minimumSelectionCompleteSignals=100),
           "ownerProspectiveInitialCashEur":300}
        rows,views=self.make_rows()
        cost=dict(centralBps=1,adverseBps=2,minimumMarginEur=30,
                  minimumNotionalEur=800,observed=12)
        q=g.power_gate(p,"USD_FUNDING_TO_US_INDEX/US500",rows,{},views,cost)
        self.assertTrue(q["passPreScoring"],q["reasons"])
        self.assertGreater(q["mechanismSpecificDevelopmentPilot"]["signedStrategyWeeklySdBps"],0)
        self.assertGreater(q["mechanismSpecificDevelopmentPilot"]["pairedIncrementalWeeklySdBps"],0)
        self.assertIsNotNone(q["mechanismSpecificDevelopmentPilot"]["mechanismSpecificMdeBps"])
        # A forced-activity/cost counterexample must fail before selection is read.
        q2=g.power_gate(p,"USD_FUNDING_TO_US_INDEX/US500",rows,{},views,
                        dict(cost,adverseBps=0.00001))
        self.assertFalse(q2["passPreScoring"])
        self.assertIn("MECHANISM_SIGNED_WEEKLY_MDE_EXCEEDS_COST_RELEVANT_EFFECT",q2["reasons"])
        self.assertIsNone(q2.get("selection"))

    def test_unknown_cost_rejects_without_price_outcome_access(self):
        p={"scientific":{}, "ownerProspectiveInitialCashEur":300}
        row=dict(development=[(0,1,1,1,2)],selection=[(1,1,1,3,4)])
        # No price view should be accessed on a missing contract.
        q=g.power_gate(p,"USD_FUNDING_TO_US_INDEX/US500",row,{},{"US500":{}},{})
        self.assertFalse(q["passPreScoring"])
        self.assertIsNone(q["mechanismSpecificDevelopmentPilot"]["mechanismSpecificMdeBps"])

    def test_registered_protocol_fences_orders_and_independence(self):
        import json
        from pathlib import Path
        p=json.loads(Path("research/gep1_protocol.json").read_text())
        self.assertTrue(p["proof"]["locked"])
        self.assertEqual(p["ownerProspectiveInitialCashEur"],300)
        self.assertEqual(sum(x["groups"] for x in p["families"]),3)
        self.assertEqual(p["scientific"]["groups"]*p["scientific"]["oneSidedComparisonsPerGroup"],6)
        self.assertFalse(p["calendar"]["independentConfirmation"])
        self.assertFalse(p["proof"]["noOrders"] is False)
        self.assertEqual(p["source"]["preexistingAuthenticatedRuns"],[41724643418,41735441128])


if __name__ == "__main__":
    unittest.main()

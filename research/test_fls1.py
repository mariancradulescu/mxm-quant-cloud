"""Offline FLS1 causal/financial guards; no broker, secrets or closed-model run."""
import math
import unittest
from datetime import datetime,timezone
from pathlib import Path
from . import fls1_research as f

class FLS1ContractTests(unittest.TestCase):
    def setUp(self):
        t=int(datetime(2025,11,3,8,tzinfo=timezone.utc).timestamp()*1000)
        self.t=t
        self.eur={t-i*f.M5:1.10000 for i in range(13)}
        self.gbp={t-i*f.M5:1.26000 for i in range(13)}
        self.eur[t]=1.10066  # ~6bps EURUSD completed H1 impulse
        self.gbp[t]=1.26013  # ~1bps lagger, smaller than predeclared 75%

    def test_completed_past_only_and_future_price_invariance(self):
        first,reason=f.signal(self.eur,self.gbp,self.t)
        self.assertEqual(reason,"CAUSAL_SIGNAL")
        self.assertEqual(first["side"],1)
        self.assertEqual(first["benchmarkSide"],1)
        e=dict(self.eur);g=dict(self.gbp)
        e[self.t+f.M5]=1e9;g[self.t+f.M5]=1.
        second,reason=f.signal(e,g,self.t)
        self.assertEqual(first,second)
        self.assertEqual(reason,"CAUSAL_SIGNAL")
        self.assertIsNone(f.signal(e,g,self.t,minimum_leader_bps=1000)[0])

    def test_missing_one_past_close_abstains(self):
        del self.gbp[self.t-7*f.M5]
        value,reason=f.signal(self.eur,self.gbp,self.t)
        self.assertIsNone(value)
        self.assertEqual(reason,"PAST_M5_GAP")

    def test_lagger_already_reacted_abstains(self):
        self.gbp[self.t]=1.262
        self.assertEqual(f.signal(self.eur,self.gbp,self.t)[1],
                         "LAGGER_NOT_UNDERREACTED")

    def test_no_future_price_imputation_for_source_eligibility(self):
        import json
        p=json.loads(Path("research/fls1_protocol.json").read_text())
        p["calendar"]["start"]=self.t
        p["calendar"]["developmentEnd"]=self.t+f.WEEK
        p["calendar"]["selectionEnd"]=self.t+2*f.WEEK
        # 13 holding marks are mandatory; an absent single mark abstains.
        for i in range(1,14):
            self.gbp[self.t+i*f.M5]=1.26013+i*.00001
        a,c=f.eligible(p,self.eur,self.gbp)
        self.assertEqual(len(a["development"]),1)
        del self.gbp[self.t+8*f.M5]
        b,c=f.eligible(p,self.eur,self.gbp)
        self.assertFalse(b["development"])
        self.assertEqual(c["development"]["missingFutureSourceClock"],1)

    def test_adverse_cost_applies_when_momentum_benchmark_flat(self):
        rows=[dict(week=0,side=1,benchmarkSide=0,entry=1,exit=2)]
        prices={1:100.,2:100.*math.exp(10/10000)}
        q={"centralBps":1.,"adverseBps":2.,"stressBps":3.}
        r=f.weekly_score(rows,prices,q,0,3)
        self.assertAlmostEqual(r["meanPerSignalBps"]["grossBps"],10.)
        self.assertAlmostEqual(r["meanPerSignalBps"]["adverseNetBps"],8.)
        self.assertAlmostEqual(r["meanPerSignalBps"]["matchedIncrementalAdverseNetBps"],8.)
        self.assertAlmostEqual(r["weekly"]["adverseNetBps"][1],0.)

    def test_weekly_uncertainty_and_no_synthetic_confidence(self):
        self.assertIsNone(f.hac_lower([2.]*13))
        self.assertIsNone(f.hac_lower([2.,3.]))
        self.assertLess(f.hac_lower([4.+i*.1 for i in range(13)]),5.)

    def test_original_source_and_no_order_boundaries(self):
        import json
        p=json.loads(Path("research/fls1_protocol.json").read_text())
        self.assertEqual(p["prospectiveInitialCapitalEur"],300)
        self.assertEqual(p["calendar"]["unscoredExposedAuditWeeks"],13)
        self.assertEqual(p["originalSource"]["expectedAuthenticatedCostContexts"],166)
        self.assertTrue(p["restrictions"]["noLiveDemoOrders"])
        src=Path("research/fls1_research.py").read_text()
        self.assertNotIn("StdlibCTraderTransport(",src)
        self.assertNotIn("collect.authenticate(",src)
        self.assertNotIn("ProtoOANewOrderReq(",src)
        self.assertNotIn("ProtoOARefreshTokenReq(",src)
        self.assertNotIn("ExecuteMarketOrder(",src)
        self.assertIn("prospective_economic_futility(",src)
        self.assertIn("if not preflight.get(\"scoreSelectionAllowed\",False)",src)

if __name__=="__main__":
    unittest.main()

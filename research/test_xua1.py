"""Offline contract tests for XUA1 non-legacy Pepperstone native H1 research."""
import copy
import json
import math
import unittest
from pathlib import Path
from . import xua1_research as r

def history(close=100.,vol=100):
    return [(r.H*(i+1),100.,101.,99.,close,vol) for i in range(25)]

class XuaOriginalSixAssetTests(unittest.TestCase):
    def test_energy_realized_impulse_volume_asof(self):
        h=history()
        h[-1]=(h[-1][0],101.,104.,100.,103.,150)
        h[-4]=(h[-4][0],100.,101.,99.,100.,100)
        self.assertEqual(r.decide(r.NAMES[0],"SpotCrude",h),1)
        self.assertEqual(r.decide(r.NAMES[0],"ETHUSD",h),0)
        low=list(h);low[-1]=(*low[-1][:-1],1)
        self.assertEqual(r.decide(r.NAMES[0],"SpotCrude",low),0)

    def test_crypto_large_daily_shock_and_counterhour(self):
        h=[(t,100.,101.,97.,98.,v) for t,o,hi,lo,cl,v in history()]
        h[0]=(h[0][0],100.,101.,99.,100.,100)
        h[-2]=(h[-2][0],98.,99.,97.,97.,100)
        h[-1]=(h[-1][0],98.,99.,97.,98.,100)
        self.assertEqual(r.decide(r.NAMES[1],"ETHUSD",h),1)
        self.assertEqual(r.decide(r.NAMES[1],"SpotCrude",h),0)

    def test_asia_index_consensus_not_inferred_from_one_market(self):
        h=history();p=history()
        h[-5]=(h[-5][0],99.,101.,98.,99.,100)
        p[-5]=(p[-5][0],99.,101.,98.,99.,100)
        h[-1]=(h[-1][0],102.,104.,100.,103.,130)
        p[-1]=(p[-1][0],101.,103.,100.,102.,140)
        self.assertEqual(r.decide(r.NAMES[2],"HK50",h,p),1)
        q=list(p);q[-1]=(q[-1][0],98.,101.,97.,98.,140)
        self.assertEqual(r.decide(r.NAMES[2],"HK50",h,q),0)

    def test_fx_current_completed_wick_rejection(self):
        h=history()
        h[-1]=(h[-1][0],100.,104.,99.,99.8,150)
        self.assertEqual(r.decide(r.NAMES[3],"GBPJPY",h),-1)
        h[-1]=(h[-1][0],100.,101.,96.,100.2,150)
        self.assertEqual(r.decide(r.NAMES[3],"GBPJPY",h),1)
        h[-1]=(h[-1][0],100.,101.,99.,100.2,1)
        self.assertEqual(r.decide(r.NAMES[3],"GBPJPY",h),0)

    def test_gap_safe_past_and_absence_of_future_imputation(self):
        h=history()
        v=r.asof_index({x[0]:x for x in h},h[-1][0])
        self.assertEqual(v,h)
        later={x[0]:x for x in h}
        later[h[-1][0]+r.H]=(1,1,1,1,1,1)
        self.assertEqual(r.asof_index(later,h[-1][0]),h)
        self.assertEqual(r.decide(r.NAMES[0],"SpotCrude",h[:-1]),0)
        missing={x[0]:x for x in h[:-1]}
        self.assertIsNone(r.asof_index(missing,h[-1][0]))

    def test_cost_unknown_is_not_zero_and_uses_genuine_positive_spread(self):
        x=r.cost_models([.2,.3,.4,.2,.5,.4])
        self.assertEqual(x["observed"],6)
        self.assertGreater(x["centralBps"],6)
        self.assertGreater(x["adverseBps"],12)
        with self.assertRaises(ValueError):r.cost_models([])
        with self.assertRaises(ValueError):r.cost_models([0.])

    def test_f2_weekly_safety_rejects_constant_synthetic_confidence(self):
        self.assertIsNone(r.hac_lower([4.]*13))
        self.assertIsNone(r.hac_lower([1.,2.]))
        rows=[dict(symbol="GBPJPY",week=0,entry=1,exit=2,side=1,benchmark=0)]
        b={"GBPJPY":{1:(1,100.,100.,100.,100.,100),2:(2,101.,101.,101.,101.,100)}}
        c={"GBPJPY":{"centralBps":6.,"adverseBps":13.,"stressBps":25.}}
        out=r.score_events(rows,b,c,0,26)
        self.assertEqual(out["signalCount"],1)
        self.assertLess(out["perSignalMeanBps"]["adverse"],out["perSignalMeanBps"]["gross"])
        self.assertEqual(out["weekly"]["gross"][1:],[0.]*25)

    def test_locked_six_nonlegacy_asset_classes_and_no_executable_orders(self):
        p=json.loads(Path("research/xua1_protocol.json").read_text())
        self.assertEqual(len(p["universe"]),6)
        self.assertNotIn("EURUSD",p["universe"])
        self.assertNotIn("US500",p["universe"])
        self.assertEqual(p["uncertainty"]["comparisonsAcrossProgramme"],8)
        self.assertEqual([x["id"] for x in p["families"]],list(r.NAMES))
        self.assertEqual(p["fundedContinuation"]["capitalOneWalletEur"],300)
        self.assertTrue(p["safety"]["noLiveOrDemoOrders"])
        self.assertEqual(p["source"]["additionalBrokerRequests"],0)
        code=Path("research/xua1_research.py").read_text()
        for forbidden in ("StdlibCTraderTransport(", "ProtoOANewOrderReq(", "ExecuteMarketOrder(",
                          "ProtoOARefreshTokenReq(", "from .erp1_research import",
                          "from .mbf1_research import"):
            self.assertNotIn(forbidden,code)
        self.assertIn("prospective_economic_futility(",code)
        self.assertIn("parity_real_original(cases)",code)
        self.assertIn('if not f2.get("scoreSelectionAllowed",False)',code)

if __name__=="__main__":
    unittest.main()

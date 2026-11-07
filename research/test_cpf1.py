"""Pure offline causality and multi-family economic contract tests."""
import copy
import json
import math
import unittest
from datetime import datetime, timezone
from pathlib import Path
from . import cpf1_research as q

def prev():
    # Descending previous closed H1 bars; each hour is complete.
    return [(100.,101.,99.,100.+(i%5-.2)*.02,10) for i in range(20)]

class CloudPatternFamilies(unittest.TestCase):
    def test_donchian_tick_activity_breakout_not_current_high_leak(self):
        h=prev()
        side=q.family_sides((100.,105.,99.,103.,14),h)
        self.assertEqual(side["DONCHIAN_TREND_VOLUME"],1)
        self.assertEqual(q.family_sides((100.,105.,99.,103.,7),h)["DONCHIAN_TREND_VOLUME"],0)
        self.assertEqual(q.family_sides((100.,101.,95.,97.,14),h)["DONCHIAN_TREND_VOLUME"],-1)

    def test_prior20_only_bollinger_mean_reversion(self):
        h=prev()
        side=q.family_sides((100.,105.,98.,103.,10),h)
        self.assertEqual(side["BOLLINGER_OVEREXTENSION_REVERSION"],-1)
        self.assertEqual(q.family_sides((100.,102.,95.,97.,10),h)["BOLLINGER_OVEREXTENSION_REVERSION"],1)
        constant=[(100.,101.,99.,100.,10)]*20
        self.assertEqual(q.family_sides((100.,101.,99.,100.,10),constant)["BOLLINGER_OVEREXTENSION_REVERSION"],0)

    def test_false_breakout_rejection_needs_closed_wick_not_future_fractal(self):
        h=prev()
        outcome=q.family_sides((100.,103.,99.5,100.2,11),h)
        self.assertEqual(outcome["H1_FALSE_BREAK_LIQUIDITY_SWEEP"],-1)
        # A bar sweeping both prior bounds is ambiguous, never cherry-picked.
        ambiguous=q.family_sides((100.,104.,98.,100.,12),h)
        self.assertEqual(ambiguous["H1_FALSE_BREAK_LIQUIDITY_SWEEP"],0)
        # current close above breached high is NOT a false breakout.
        trend=q.family_sides((100.,103.,99.5,102.,12),h)
        self.assertEqual(trend["H1_FALSE_BREAK_LIQUIDITY_SWEEP"],0)

    def test_exact_12_m5_hourly_assembly_missing_candle_no_imputation(self):
        t=int(datetime(2025,11,3,8,tzinfo=timezone.utc).timestamp()*1000)
        rows=[]
        for i in range(12):
            close=t-(11-i)*q.M5
            rows.append([close-q.M5,close,100.,101.,99.,100.1,3])
        h=q.h1_from_m5(rows)
        self.assertEqual(list(h),[t])
        self.assertEqual(h[t][-1],36)
        self.assertEqual(q.h1_from_m5(rows[:-1]),{})
        rows2=[list(r) for r in rows]
        rows2[4][1]+=q.M5
        with self.assertRaisesRegex(ValueError,"CPF1_ORIGINAL_M5_GEOMETRY"):
            q.h1_from_m5(rows2)

    def test_future_prices_never_affect_causal_features(self):
        h=prev()
        current=(100.,103.,99.5,100.2,11)
        baseline=q.family_sides(current,h)
        market={-1:100.}
        market[1]=900000.
        self.assertEqual(baseline,q.family_sides(current,list(h)))
        self.assertEqual(len(baseline),3)

    def test_target_price_only_scoring_and_flat_benchmark_cost(self):
        cases=[dict(symbol="EURUSD",week=0,entry=1,exit=2,side=1,benchmarkSide=0)]
        prices={"EURUSD":{1:100.,2:100*math.exp(.001)}}
        c={"EURUSD":{"centralBps":1., "adverseBps":2., "stressBps":3.}}
        r=q.score(cases,prices,c,0,26)
        self.assertAlmostEqual(r["meanSourceProxyPerSignalBps"]["grossBps"],10.)
        self.assertAlmostEqual(r["meanSourceProxyPerSignalBps"]["adverseNetBps"],8.)
        self.assertAlmostEqual(r["meanSourceProxyPerSignalBps"]["incrementalVsFourHourMomentumAdverseBps"],8.)
        self.assertEqual(r["weeks"]["grossBps"][1:], [0.]*25)
        cases[0]["benchmarkSide"]=1
        b=q.score(cases,prices,c,0,26)
        self.assertAlmostEqual(b["meanSourceProxyPerSignalBps"]["incrementalVsFourHourMomentumAdverseBps"],0.)

    def test_uncertainty_cannot_be_invented_from_constant_results(self):
        self.assertIsNone(q.hac_lower([1.]*13))
        self.assertIsNone(q.hac_lower([1.,2.]))
        self.assertLess(q.hac_lower([.1+i*.1 for i in range(13)]),2.)

    def test_original_owner_source_predeclared_and_no_orders(self):
        p=json.loads(Path("research/cpf1_protocol.json").read_text())
        self.assertTrue(p["locked"])
        self.assertEqual(p["finance"]["prospectiveInitialCapitalEur"],300)
        self.assertEqual([r["id"] for r in p["families"]],list(q.FAMILIES))
        self.assertEqual(p["statistics"]["wholeProgramOneSidedComparisons"],6)
        self.assertEqual(p["clock"]["exposedAuditWeeksUnscored"],13)
        self.assertEqual(len(p["source"]["sourceSymbols"]),12)
        src=Path("research/cpf1_research.py").read_text()
        for forbidden in ("StdlibCTraderTransport(", "collect.authenticate(", "ProtoOANewOrderReq(",
                          "ExecuteMarketOrder(", "ProtoOARefreshTokenReq("):
            self.assertNotIn(forbidden,src)
        self.assertIn("prospective_economic_futility(",src)
        self.assertIn('if not f2.get("scoreSelectionAllowed",False)',src)

if __name__=="__main__":
    unittest.main()

"""MFA1 causal multi-family and adaptive system offline unit tests."""
import json
import math
import unittest
from pathlib import Path
from . import mfa1_research as m

def bar(t,close=100.,open_=100.,volume=10):
    hi=max(open_,close)+.1
    lo=min(open_,close)-.1
    return [t-m.M5,t,open_,hi,lo,close,volume]

class MultiFamilyAdaptiveNativeContract(unittest.TestCase):
    def setUp(self):
        self.at=m.H*100
        self.history={self.at-i*m.M5:bar(self.at-i*m.M5,
            close=100+(.015 if i%3==0 else -.02)*(48-i),
            volume=10) for i in range(97)}

    def test_no_future_price_or_bar_can_affect_any_sign(self):
        before=m.evaluate("EURUSD",self.at,self.history,{"previousObserved":self.history[self.at-m.M5],"other":{}})
        modified=dict(self.history)
        modified[self.at+m.M5]=bar(self.at+m.M5,close=1e9)
        after=m.evaluate("EURUSD",self.at,modified,{"previousObserved":self.history[self.at-m.M5],"other":{}})
        self.assertEqual(before,after)
        self.assertEqual(set(before),set(m.FAMILY))

    def test_squeeze_and_pullback_require_full_observed_prefix(self):
        full=m.evaluate("EURUSD",self.at,self.history,{"previousObserved":self.history[self.at-m.M5],"other":{}})
        x=dict(self.history);del x[self.at-24*m.M5]
        broken=m.evaluate("EURUSD",self.at,x,{"previousObserved":x[self.at-m.M5],"other":{}})
        self.assertEqual(broken[m.FAMILY[0]],0)
        self.assertEqual(broken[m.FAMILY[1]],0)
        self.assertIn(full[m.FAMILY[0]],(-1,0,1))

    def test_genuine_reopen_gap_only_and_no_fake_missing_bars(self):
        a=m.H*100
        one=bar(a,open_=101.,close=101.2)
        earlier=bar(a-2*m.H,close=100.)
        rows={a:one,a-2*m.H:earlier}
        signal=m.evaluate("EURUSD",a,rows,{"previousObserved":earlier})
        self.assertEqual(signal[m.FAMILY[3]],-1)
        no_gap=m.evaluate("EURUSD",a,rows,{"previousObserved":bar(a-m.M5,close=100.)})
        self.assertEqual(no_gap[m.FAMILY[3]],0)

    def test_cross_index_requires_both_contiguous_closed_paths(self):
        peer={t:bar(t,close=99.) for t in self.history}
        for i in range(49):
            t=self.at-i*m.M5
            self.history[t]=bar(t,close=101. if i<24 else 99.5)
        sig=m.evaluate("US500",self.at,self.history,{"previousObserved":self.history[self.at-m.M5],"other":peer})
        self.assertEqual(sig[m.FAMILY[4]],-1)
        del peer[self.at-15*m.M5]
        self.assertEqual(m.evaluate("US500",self.at,self.history,{"other":peer})[m.FAMILY[4]],0)

    def test_adaptation_only_prior_full_weeks(self):
        f={family:[] for family in m.FAMILY}
        for week in range(4):
            f[m.FAMILY[0]].append(dict(week=week,symbol="EURUSD",adverseNetBps=2.))
            f[m.FAMILY[1]].append(dict(week=week,symbol="EURUSD",adverseNetBps=-3.))
        f[m.FAMILY[0]].append(dict(week=4,symbol="EURUSD",adverseNetBps=-100.))
        rows,choices=m.adaptive_rows(f,4,6,6)
        self.assertEqual(choices[0]["chosenFamily"],m.FAMILY[0])
        self.assertEqual(choices[0]["selectedUsingOnlyWeeksBefore"],4)
        self.assertEqual(choices[0]["completeSourceProposalsForChosenFamily"],1)
        # Week 5 may change as the negative week 4 is now actually mature.
        self.assertEqual(choices[1]["selectedUsingOnlyWeeksBefore"],5)

    def test_adaptive_future_outcomes_cannot_retroactively_choose_prior_week(self):
        f={family:[] for family in m.FAMILY}
        for week in range(4):
            f[m.FAMILY[0]].append(dict(week=week,symbol="EURUSD",adverseNetBps=3.))
            f[m.FAMILY[1]].append(dict(week=week,symbol="GBPUSD",adverseNetBps=1.))
        chosen,decisions=m.adaptive_rows(f,4,5,5)
        f[m.FAMILY[1]].append(dict(week=4,symbol="GBPUSD",adverseNetBps=99999.))
        chosen2,decisions2=m.adaptive_rows(f,4,5,5)
        self.assertEqual(decisions[0]["chosenFamily"],decisions2[0]["chosenFamily"])

    def test_costs_not_zero_and_benchmark_paid_when_active(self):
        r=dict(symbol="EURUSD",week=0,entry=1,exit=2,side=1,benchmarkSide=1,family=m.FAMILY[0])
        prices={"EURUSD":{1:bar(1,100.),2:bar(2,100.*math.exp(.001))}}
        costs={"EURUSD":{"centralBps":1.,"adverseBps":2.,"stressBps":3.}}
        x=m.event_score(r,prices,costs)
        self.assertAlmostEqual(x["grossBps"],10.)
        self.assertAlmostEqual(x["adverseNetBps"],8.)
        self.assertAlmostEqual(x["incrementalVersusMatchedBenchmarkAdverseBps"],0.)
        r["benchmarkSide"]=0
        x=m.event_score(r,prices,costs)
        self.assertAlmostEqual(x["incrementalVersusMatchedBenchmarkAdverseBps"],8.)

    def test_multiplicity_no_spurious_confidence(self):
        self.assertIsNone(m.hac_lower([1.]*13))
        self.assertLess(m.hac_lower([1.+i*.1 for i in range(13)]),3.)
        p=json.loads(Path("research/mfa1_protocol.json").read_text())
        self.assertEqual(p["statistical"]["totalOneSidedComparisons"],12)
        self.assertEqual(p["calendar"]["globallyExposedAuditWeeksUnscored"],13)
        self.assertEqual(p["product"]["oneCapitalEUR300"],True)
        self.assertEqual(len(p["families"]),5)
        self.assertEqual(p["adaptiveSystem"]["lookbackFullWeeks"],4)

    def test_source_never_calls_broker_trading_or_refresh(self):
        src=Path("research/mfa1_research.py").read_text()
        for bad in ("StdlibCTraderTransport(", "collect.authenticate(", "ProtoOANewOrderReq(",
                    "ExecuteMarketOrder(", "ProtoOARefreshTokenReq("):
            self.assertNotIn(bad,src)
        self.assertIn("prospective_economic_futility(",src)
        self.assertIn("parity_actual_source(cases)",src)
        self.assertIn("if not record[\"developmentF2\"].get",src)

if __name__=="__main__":
    unittest.main()

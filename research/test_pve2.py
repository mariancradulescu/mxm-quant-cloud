"""PVE2 synthetic causal/risk contracts. Never certify performance."""
import json
import math
import unittest
from datetime import datetime,timezone
from pathlib import Path
from .pve2_causal import causal_state,one_sided_weekly_t
from .pve2_portfolio import request,evaluate
from .rcp1_portfolio import Book,STATES,WEEK,MS,HR

class PVE2Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol=json.loads(Path("research/pve2_protocol.json").read_text())

    def test_predeclaration_and_no_historical_relabel(self):
        p=self.protocol
        self.assertEqual(p["id"],"PVE2")
        self.assertEqual(p["status"],"PREDECLARED_UNSCORED")
        self.assertEqual(len(p["sourceSymbols"]),12)
        self.assertEqual(p["fixedSignal"]["holdingMinutes"],[60,240])
        self.assertEqual(p["economicPolicy"]["initialCapitalEur"],300)
        self.assertEqual(p["statisticalPolicy"]["primaryTests"],2)
        self.assertEqual(p["statisticalPolicy"]["oneSidedComparisons"],2)
        self.assertFalse(p["qualification"]["independentConfirmation"])
        self.assertTrue(p["sourcePolicy"]["closedStrategiesRescored"] is False)
        self.assertEqual(p["sourcePolicy"]["newBrokerRequests"],0)

    def test_daily_trend_opposes_last_hour_without_seeing_future(self):
        t=int(datetime(2026,7,8,12,tzinfo=timezone.utc).timestamp()*1000)
        rows={}
        for i in range(13):
            clock=t-i*MS
            px=100.+i/12.
            rows[clock]=[clock-MS,clock,px,px,px,px,100]
        rows[t-24*HR]=[t-24*HR-MS,t-24*HR,95.,95.,95.,95.,10]
        signal=causal_state(rows,t)
        self.assertIsNotNone(signal)
        self.assertEqual(signal["side"],1)
        self.assertTrue(signal["pullback"])
        # A future return may not affect any part of this fixed signal.
        rows[t+MS]=[t,t+MS,9999.,9999.,9999.,9999.,9999]
        self.assertEqual(signal,causal_state(rows,t))
        rows.pop(t-5*MS)
        self.assertIsNone(causal_state(rows,t))
        self.assertEqual(one_sided_weekly_t([1.]*13),1.)
        self.assertGreater(one_sided_weekly_t([-1.]*8+[1.]*5),.5)
        self.assertLess(one_sided_weekly_t(
            [1.,2.,3.,2.,1.,3.,2.,4.,1.5,2.5,3.5,2.]),.0125)

    def test_fixed_eur300_book_abstention_continuity_and_hard21(self):
        r=evaluate({}, {}, {}, self.protocol)
        self.assertEqual(r["FULL"]["initialCapitalEur"],300.)
        self.assertEqual(r["FULL"]["cashEur"],300.)
        self.assertEqual(r["FULL"]["modeledRoundTrips"],0)
        self.assertEqual(r["FULL"]["netClosedEur"],0.)
        self.assertTrue(r["FULL"]["capitalContinuityReconciled"])
        self.assertEqual(r["FULL"]["prospectivelyEligibleWeeks"],13)
        self.assertEqual(r["FULL"]["eligibleWeeksPassingHard21"],0)
        self.assertIsNone(r["FULL"]["brokerCertifiedNetEur"])

    def test_accepted_path_constructs_one_common_native_eur300_proposal(self):
        p=self.protocol
        t=int(datetime(2026,9,10,12,tzinfo=timezone.utc).timestamp()*1000)
        source={t:100.}
        for w in STATES:
            old=t-w*WEEK
            for offset in (0,MS,HR,HR+MS,2*HR,2*HR+MS,
                           3*HR,3*HR+MS,4*HR,4*HR+MS):
                source[old+offset]=100.+offset/HR*.03
        views={"EURUSD":{"price":source,"observed":sorted(source)}}
        terms={"EURUSD":dict(minimumNotionalEur=1000.,
            minimumMarginEur=35.,adverseBps=2.,stressBps=4.,
            fundingKnown=True,swapMinute=1320,
            longDailyDebitBps=0.,shortDailyDebitBps=0.)}
        f=dict(symbol="EURUSD",family="DAILY_TREND_H1_PULLBACK",
            horizon=60,side=1,knownAt=t,predBps=20.)
        req,lookups=request(Book("PVE2_SYNTHETIC",initial=300.),t,
            [f],views,terms,p,"FULL")
        self.assertIsNotNone(req)
        self.assertEqual(req["Scope"],
            "PVE2_DAILY_PULLBACK_EUR300_CONDITIONAL_ONLY_NOT_CERTIFIED")
        self.assertEqual(req["Account"]["EquityEur"],300.)
        self.assertEqual(req["Account"]["PeakReferenceEur"],300.)
        self.assertEqual(req["Account"]["FreeMarginEur"],300.)
        self.assertEqual(len(req["Baseline"]),8)
        self.assertEqual(len(req["Opportunities"]),1)
        self.assertEqual(len(lookups),1)
        self.assertEqual(next(iter(lookups.values()))["family"],
                         "DAILY_TREND_H1_PULLBACK")
        self.assertFalse(req["Opportunities"][0]["ExecutionEvidenceComplete"])
        # The same shared native C# selector remains the sole allocation path.
        from .portfolio_economic_replay import native
        response=native([req],"--estimate-portfolio-opportunities-batch")
        self.assertEqual(len(response),1)
        self.assertFalse(response[0]["Qualified"])
        self.assertFalse(response[0].get("OrdersEnabled",False))
        self.assertTrue(response[0]["Status"].startswith("CONDITIONAL_RESEARCH_"))
        bad=dict(f,predBps=1.)
        empty,_=request(Book("PVE2_NO_GROSS",initial=300.),t,
            [bad],views,terms,p,"FULL")
        self.assertEqual(empty["Opportunities"],[])

if __name__=="__main__":unittest.main()

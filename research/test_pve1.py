"""Synthetic PVE1 contract checks: NO economic qualification or broker orders."""
import json
import unittest
from pathlib import Path
from datetime import datetime,timezone
from .pve1_causal import feature,measure,pvalue_from_weeks
from .pve1_portfolio import evaluate

class PVE1Checks(unittest.TestCase):
    def setUp(self):
        self.p=json.loads(Path("research/pve1_protocol.json").read_text())
    def test_universe_multiplicity_and_initial_capital(self):
        p=self.p
        self.assertEqual(p["status"],"PREDECLARED_UNSCORED")
        self.assertEqual(len(p["symbols"])*len(p["families"])*len(p["horizonsMinutes"]),48)
        self.assertEqual(p["economics"]["initialCapitalEur"],300)
        self.assertEqual(p["qualification"]["brokerCertifiedNetEur"],None)
        self.assertFalse(p["qualification"]["independentConfirmation"])
    def test_path_feature_past_only_and_activity_causality(self):
        t=int(datetime(2026,6,8,12,tzinfo=timezone.utc).timestamp()*1000)
        five=300000
        rows={}
        start=t-36*3600000
        for i in range(int((t-start)/five)+1):
            end=start+i*five
            steps=max(0,(end-(t-4*3600000))//five)
            price=10000+steps*3
            rows[end]=[end-five,end,price,price+2,price-2,price,
                200 if end>t-3600000 else 10]
        original=feature(rows,t,self.p)
        self.assertIn("VOLUME_EFFICIENT_ACCEPTANCE",original)
        self.assertEqual(original["VOLUME_EFFICIENT_ACCEPTANCE"]["side"],1)
        rows[t+five]=[t,t+five,1,999999,1,999999,1000000]
        self.assertEqual(original,feature(rows,t,self.p))
        rows.pop(t-10*five)
        self.assertEqual({},feature(rows,t,self.p))
    def test_no_anecdote_passes_multiplicity(self):
        self.assertEqual(pvalue_from_weeks([1.]*13),1.)
        empty=measure([])
        self.assertIsNone(empty["grossMeanBps"])
        self.assertEqual(empty["activeWeeks"],0)
    def test_supported_causal_candidate_preserves_its_exact_family_for_native_book(self):
        # A positive selection gate may be rare on authentic historical data.
        # Exercise the *admitted* path so an undefined family binding cannot
        # silently survive an all-rejected research run.
        from .pve1_portfolio import request
        from .rcp1_portfolio import Book,STATES,WEEK,MS,HR
        t=int(datetime(2026,6,8,12,tzinfo=timezone.utc).timestamp()*1000)
        prices={t:100.}
        for w in STATES:
            past=t-w*WEEK
            for tick in (past,past+MS,past+HR,past+MS+HR):
                prices[tick]=100.+(tick-past)/HR*.01
        views={"EURUSD":{"price":prices,"observed":sorted(prices)}}
        cost={"EURUSD":dict(minimumNotionalEur=1000.,
            minimumMarginEur=30.,adverseBps=2.,stressBps=3.,
            swapMinute=0,fundingKnown=True,longDailyDebitBps=0.,
            shortDailyDebitBps=0.)}
        forecast=dict(symbol="EURUSD",family="VOLUME_EFFICIENT_ACCEPTANCE",
            horizon=60,side=1,predBps=20.,knownAt=t)
        req,lookups=request(Book("PVE1_TEST",initial=300.),t,
            [forecast],views,cost,self.p,"FULL")
        self.assertEqual(len(req["Opportunities"]),1)
        self.assertEqual(len(lookups),1)
        self.assertEqual(next(iter(lookups.values()))["family"],
            "VOLUME_EFFICIENT_ACCEPTANCE")
        self.assertEqual(req["Account"]["EquityEur"],300.)
        self.assertEqual(req["Account"]["PeakReferenceEur"],300.)
        self.assertFalse(req["Opportunities"][0]["ExecutionEvidenceComplete"])
    def test_modelled_flat_book_starts_only_one_eur300(self):
        result=evaluate({}, {}, {}, self.p)
        self.assertEqual(result["FULL"]["initialCashEur"],300.)
        self.assertEqual(result["FULL"]["cashEur"],300.)
        self.assertEqual(result["FULL"]["netClosedEur"],0.)
        self.assertEqual(result["FULL"]["eligibleWeeks"],13)
        self.assertEqual(result["FULL"]["modeledRoundTrips"],0)
        self.assertTrue(result["FULL"]["capitalContinuityReconciled"])
        self.assertIsNone(result["FULL"]["brokerConfirmedNetEur"])
        self.assertFalse(result["FULL"]["independentConfirmation"])

if __name__=="__main__":unittest.main()

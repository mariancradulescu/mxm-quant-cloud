"""MVE1 synthetic causal, multivariate, source/cost/label separation checks.

No original historical source and no claims of predictive profitability.
"""
import unittest
from copy import deepcopy
from math import isfinite
import numpy as np
from research.mve1_event_interaction import (
    M5,COLUMNS,TAGS,strict_rows,features_at,build_events,
    label_after_original_intent,peer_past12
)
from research.mve1_multitarget_model import (
    fit_all_multitarget,admitted_research_opportunity,current_term_friction_bps,diagnostic_eur
)
from research.mve1_authentic_eur import weekly_paired_lower


def mock_price(t0,n=120,start=120000,delta=2):
    a=[]
    for i in range(n):
        end=t0+i*M5
        p=start+i*delta
        a.append([end-M5,end,p-2,p+6,p-6,p+1,100+i%11])
    return a


def protocol():
    return {"scope":{"universe":["EURUSD","XAUUSD"],
        "calendarStart":1762128000000,"trainEnd":1777852800000,
        "selectionEnd":1785715200000,"end":1793577600000},
        "targets":{"horizonsM5":[12,48]}}


class Mve1InvariantTests(unittest.TestCase):
    def setUp(self):
        self.t0=1762128000000
        self.p=protocol()

    def test_every_completed_m5_observable_event_without_three_clocks(self):
        src={"EURUSD":mock_price(self.t0),
             "XAUUSD":mock_price(self.t0,start=500000,delta=-3)}
        events,seq,runs,audit,by=build_events(src,self.p)
        self.assertEqual(audit["observedCompletedM5"],240)
        self.assertGreater(len(events),0)
        self.assertTrue(any(e["t"]%3600000 !=0 for e in events))
        self.assertTrue(all(len(e["features"])==len(COLUMNS) for e in events))
        self.assertTrue(all(any(e["tags"]) for e in events))
        self.assertEqual(len(TAGS),6)

    def test_future_price_or_label_missing_never_erases_original_intent(self):
        src={"EURUSD":mock_price(self.t0),
             "XAUUSD":mock_price(self.t0,start=500000,delta=-3)}
        before,seq,runs,_,_=build_events(src,self.p)
        saved=[(x["s"],x["t"],x["features"],x["tags"]) for x in before[:7]]
        # Changing future closes beyond all selected feature clocks
        # cannot change earlier features or event directions.
        after_sources=deepcopy(src)
        for sym in src:
            for bar in after_sources[sym][-20:]:
                bar[2]+=5;bar[3]+=5;bar[4]+=5;bar[5]+=5
        after,_,_,_,_=build_events(after_sources,self.p)
        for item in saved:
            self.assertIn(item,[(x["s"],x["t"],x["features"],x["tags"])
                                for x in after])
        labels=label_after_original_intent(before,seq,runs,self.p)
        self.assertEqual(len(labels[12]),len(before))
        self.assertTrue(any(not x["known"] for x in labels[48]))
        self.assertTrue(any(x["known"] for x in labels[12]))

    def test_source_contiguity_and_missing_forward_are_distinct(self):
        a,run=strict_rows(mock_price(self.t0))
        self.assertEqual(run[-1],len(a))
        # Features after outage require 49 truly consecutive original bars.
        gap=mock_price(self.t0)
        gap.pop(70)
        a,run=strict_rows(gap)
        self.assertEqual(run[70],1)
        self.assertIsNone(features_at(a,run,71,[]))
        # Exact duplicate source is error, not a second training label.
        dup=mock_price(self.t0)
        dup.append(dup[50])
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            strict_rows(dup)

    def test_training_only_26w_ridge_multi_target_and_ablation(self):
        p=self.p
        src={"EURUSD":mock_price(self.t0,240),
             "XAUUSD":mock_price(self.t0,240,start=500000,delta=-3)}
        events,seq,run,_,_=build_events(src,p)
        labels=label_after_original_intent(events,seq,run,p)[12]
        known=[x for x in labels if x["known"]]
        self.assertGreater(len(known),200)
        fit=fit_all_multitarget(labels,events,12)
        self.assertEqual(len(fit["variants"]),4)
        self.assertEqual(fit["trainCount"],len(known))
        self.assertEqual(fit["variants"]["FULL_INTERACTIONS"]["beta"].shape[1],4)
        self.assertTrue(np.all(np.isfinite(fit["variants"]["FULL_INTERACTIONS"]["beta"])))

    def test_no_cost_or_no_predictive_certainty_is_not_an_order(self):
        features={"features":tuple([1.]+[0.]*(len(COLUMNS)-1)),
                  "vol5":.0001,"h":12}
        pred={"target":np.array([.02,1,-1,.5]),
              "meanSE":np.array([1.,1.,1.,1.]),
              "probUp":.5,"volExpansionProb":.5}
        outcome=admitted_research_opportunity(features,pred,None)
        self.assertEqual(outcome["state"],"PREDICTIVE_ABSTAIN")
        pred["target"][0]=30.
        pred["meanSE"][0]=.01
        outcome=admitted_research_opportunity(features,pred,None)
        self.assertEqual(outcome["state"],"FINANCIAL_UNKNOWN_OR_UNFUNDED")

    def test_eur_cost_includes_conservative_directional_swap_only_if_crossed(self):
        # Proven current original fee/spread costs, modeled (not true fills).
        c={"fundingKnown":True,"swapMinute":120,
           "centralBps":2.0,"adverseBps":5.0,
           "longDailyDebitBps":3.0,"shortDailyDebitBps":6.0,
           "minimumNotionalEur":200.0,"minimumMarginEur":50.0}
        day=86400000
        row={"entryClock":2*day+119*60000,"h":12,
             "known":True,"returnBps":18.0}
        self.assertEqual(current_term_friction_bps(row,1,c,"adverse"),14.0)
        self.assertEqual(current_term_friction_bps(row,-1,c,"adverse"),23.0)
        self.assertAlmostEqual(diagnostic_eur(row,1,c,"adverse"),.08)
        # Shift to after the daily rollover: never charge an extra day.
        row2={**row,"entryClock":2*day+121*60000}
        self.assertEqual(current_term_friction_bps(row2,1,c,"adverse"),5.0)
        c["fundingKnown"]=False
        self.assertIsNone(current_term_friction_bps(row2,1,c,"adverse"))

    def test_weekwise_multiplicity_no_fabricated_independence(self):
        self.assertIsNone(weekly_paired_lower({},26))
        self.assertIsNone(weekly_paired_lower({26:{"AAA":[.1]}},26))
        x={26+k:{"AAA":[-.2,.2],"BBB":[.1,.1]}
           for k in range(13)}
        v=weekly_paired_lower(x,26)
        self.assertEqual(v["weeksCovered"],13)
        self.assertFalse(v["selectedAsIndependentHoldout"])


if __name__=="__main__":
    unittest.main()

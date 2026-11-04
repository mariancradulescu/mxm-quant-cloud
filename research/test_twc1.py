"""Pure causality / funded admission contracts, not historical strategy testing."""
import unittest
from datetime import datetime,timezone
from .twc1_causal import Bucket,key,score
from .twc1_portfolio import request
from .rcp1_portfolio import Book,HR,MS,WEEK

class Twc1Contracts(unittest.TestCase):
    def test_calendar_bucket_and_causal_maturity(self):
        t=int(datetime(2026,6,1,8,0,tzinfo=timezone.utc).timestamp()*1000)
        self.assertEqual(key(t),(0,2))
        b=Bucket(12)
        self.assertEqual(b.predict(),0.)
        b.learn(100)
        self.assertAlmostEqual(b.predict(),100/13)
        self.assertEqual(b.n,1)
        b.learn(-800,clip=500)
        self.assertAlmostEqual(b.predict(),-400/14)
    def test_future_audit_cannot_rewrite_earlier_exposed_selection(self):
        start=int(datetime(2026,6,1,tzinfo=timezone.utc).timestamp()*1000)
        prices={}
        for day in range(28):
            for k in range(24*12):
                t=start+day*24*HR+(k+1)*MS
                prices[t]=100+day*.4+k*.001
        v={"EURUSD":{"price":prices}}
        p={"phase":{"start":start,"developmentEnd":start+14*24*HR,
             "selectionEnd":start+21*24*HR,"end":start+28*24*HR,
             "firstModelWarmupWeeks":0},
           "holdingHorizonsMinutes":[60,240],
           "predictor":{"retClipAbsBps":500,"minimumMaturedLabels":1},
           "sourceSymbols":["EURUSD"]}
        a=score(v,p)
        changed={t:(q*1.4 if t>=p["phase"]["selectionEnd"] else q)
                 for t,q in prices.items()}
        b=score({"EURUSD":{"price":changed}},p)
        self.assertEqual(a["pooled"]["selection"],b["pooled"]["selection"])
        self.assertEqual(a["pooled"]["development"],b["pooled"]["development"])
        self.assertGreater(a["pooled"]["selection"]["scored"],0)
        self.assertEqual(a["models"],b["models"])
        self.assertTrue(all(t<p["phase"]["end"] for t in a["offers"]))
    def test_native_joint_request_cost_and_funding_gate(self):
        start=int(datetime(2025,11,3,tzinfo=timezone.utc).timestamp()*1000)
        t=start+13*WEEK
        prices={t:100,t+MS:100.01}
        # Eight aligned weekly historical outcomes used as native joint states.
        for w in range(2,10):
            old=t-w*WEEK
            prices[old]=100.
            prices[old+MS]=100.01
            for h in range(1,5):
                prices[old+h*HR]=100.0+h*.01
                prices[old+MS+h*HR]=100.01+h*.01
            prices[old+MS+4*HR]=100.05
        view={"EURUSD":{"price":prices}}
        cost={"EURUSD":{"minimumNotionalEur":600.,"minimumMarginEur":30.,
             "adverseBps":3.,"stressBps":6.,"fundingKnown":True,
             "swapMinute":1320,"longDailyDebitBps":0.,
             "shortDailyDebitBps":0.}}
        p={"phase":{"start":start,"developmentEnd":start+10*WEEK,
             "selectionEnd":start+15*WEEK,"end":start+20*WEEK}}
        book=Book("TWC1_TEST")
        row=dict(symbol="EURUSD",horizon=240,predBps=25.,
                 knownAt=t,observed=12)
        req,lookup=request(book,t,[row],view,cost,p,"FULL")
        self.assertEqual(req["Scope"],"TWC1_CALENDAR_CONDITIONAL_RESEARCH_NOT_CERTIFIED")
        self.assertEqual(len(req["Baseline"]),8)
        self.assertEqual(len(req["Opportunities"]),1)
        self.assertFalse(req["Opportunities"][0]["ExecutionEvidenceComplete"])
        self.assertEqual(set(req["ScenarioCompleteOpportunityIds"]),set(lookup))
        denied,_=request(Book("NO_GROSS"),t,[dict(row,predBps=1.)],
                         view,cost,p,"FULL")
        self.assertEqual(denied["Opportunities"],[])
        adverse,_=request(Book("STRESS"),t,[dict(row,predBps=4.)],
                          view,cost,p,"FULL_STRESS")
        self.assertEqual(adverse["Opportunities"],[])
        # Actual Python -> JSON -> native C# batch -> shared selector integration.
        # Synthetic causal fixtures only; no Pepperstone data or study rerun.
        from .portfolio_economic_replay import native
        outputs=native([req,denied,adverse],"--estimate-portfolio-opportunities-batch")
        self.assertEqual(len(outputs),3)
        self.assertTrue(all(not result["Qualified"] for result in outputs))
        self.assertTrue(all(result["Status"].startswith("CONDITIONAL_RESEARCH_") for result in outputs))
        self.assertEqual(outputs[1]["Allocations"],[])
        self.assertEqual(outputs[2]["Allocations"],[])
        # A deliberately profitable, causally aligned synthetic joint state must
        # actually allocate, not merely pass CLI scope admission.
        import copy
        positive=copy.deepcopy(req)
        positive["Baseline"]=[dict(s,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0)
                              for s in positive["Baseline"]]
        for opportunity in positive["Opportunities"]:
            opportunity["Scenarios"]=[dict(s,NetPerUnitEur=5.,FixedCostEur=0,
                LossPerUnitEur=.01,PeakPerUnitEur=5.) for s in opportunity["Scenarios"]]
        allocated=native([positive],"--estimate-portfolio-opportunities-batch")[0]
        self.assertFalse(allocated["Qualified"])
        self.assertTrue(any(float(a["Units"])>0 for a in allocated["Allocations"]))
if __name__=="__main__":unittest.main()

"""RCP1 prospective causal/financial contracts, never source model replay."""
import copy,json,math,unittest
from pathlib import Path
from .rcp1_causal import analytic_features,score_market,HR,MS,WEEK
from .rcp1_portfolio import Book,request,funding,path
from .integrated_predictive_funded import market_view

class Rcp1Checks(unittest.TestCase):
    @staticmethod
    def protocol():
        return json.loads(Path("research/rcp1_protocol.json").read_text())
    def fixture(self,hours=210):
        p=self.protocol()
        start=p["phase"]["start"]
        begin=(start//HR)*HR
        views={}
        for j,s in enumerate(("EURUSD","US500","NAS100","GER40")):
            rows=[]
            for i in range(hours*12):
                t=begin+i*MS
                price=100000*(1+.01*j)*math.exp(.0000004*i+.00004*math.sin(i/113+j))
                rows.append([t,t+MS,price,price*1.001,price*.999,price,100+int(10*abs(math.sin(i/100)))])
            views[s]=market_view(rows)
        return p,views

    def cost(self):
        return dict(minimumNotionalEur=1000.,minimumMarginEur=30.,
            adverseBps=2.,centralBps=1.,stressBps=5.,
            swapMinute=20,fundingKnown=True,longDailyDebitBps=1.,
            shortDailyDebitBps=2.)

    def test_features_h4_d1_fiveday_causal(self):
        p,views=self.fixture(230)
        t=p["phase"]["start"]+150*HR
        before=analytic_features(views,"EURUSD",t)
        self.assertIsNotNone(before)
        later=copy.deepcopy(views)
        for symbol,v in later.items():
            for stamp in v["price"]:
                if stamp>t:v["price"][stamp]*=1.8
            for stamp,bar in v["h"].items():
                if stamp>t:v["h"][stamp]=(bar[0],bar[1]*3,bar[2],bar[3]*2,bar[4],bar[5])
        self.assertEqual(before,analytic_features(later,"EURUSD",t))

    def test_all_unscored_exposure_phases_and_zero_prior(self):
        p,views=self.fixture(235)
        p["phase"]["firstModelWarmupWeeks"]=0
        p["model"]["minimumMaturedObservations"]=0
        scores=score_market(views,p)
        self.assertEqual(len(scores["metrics"]),3*4*3*4)
        self.assertGreater(scores["planned"],0)
        self.assertGreater(scores["decisionClocks"],0)
        self.assertTrue(all(q["knownAt"] in scores["clockForecasts"]
            for group in scores["clockForecasts"].values() for q in group))
        self.assertGreater(scores["unknownOutcomes"],0)

    def test_separate_future_entry_and_one_cash_with_existing_positions(self):
        p,_=self.fixture(100)
        # Exact M5 market extends beyond nine *full* weekly predecision
        # states; non-constant oscillating prices make open-risk scenario real.
        start=p["phase"]["start"]
        t=start+11*WEEK
        t=(t//(4*HR))*(4*HR)
        rows=[]
        for i in range(11*7*24*12+200):
            at=start+i*MS
            price=100000*math.exp(.00000005*i+.0003*math.sin(i/37))
            rows.append([at,at+MS,price,price*1.0001,price*.9999,price,100])
        v={"EURUSD":market_view(rows)}
        c={"EURUSD":self.cost()}
        book=Book("FULL")
        book.advance(t,v,c)  # Same normal predecision observation as production replay
        alloc=dict(Id="RCP1TEST/1",Units=1)
        lookup={alloc["Id"]:dict(symbol="EURUSD",family="RANGE_COMPRESSION_RELEASE",
                side=1,horizon=240)}
        self.assertTrue(book.fill_after_decision(t,alloc,lookup,v,c,"FULL",p))
        self.assertEqual(len(book.open),1)
        position=next(iter(book.open.values()))
        self.assertEqual(position["entryAt"],t+MS)
        self.assertEqual(position["entryPrice"],v["EURUSD"]["price"][t+MS])
        self.assertNotEqual(position["entryPrice"],v["EURUSD"]["price"][t])
        self.assertLess(book.cash,200.)
        self.assertTrue(book.intact())
        # At t+4h the position is still open until +4h+5min; it
        # contributes nonzero historical scenario loss/returns.
        req,_=request(book,t+4*HR,[],v,c,p,"FULL")
        self.assertIsNotNone(req)
        self.assertEqual(len(req["Baseline"]),8)
        self.assertTrue(all(z["LossEur"]>0 for z in req["Baseline"]))
        self.assertTrue(any(abs(z["NetEur"])>0 for z in req["Baseline"]))
        self.assertTrue(all(z["MarginEur"]==30. for z in req["Baseline"]))
        book.advance(t+8*HR,v,c)
        self.assertEqual(len(book.open),0)
        self.assertEqual(len(book.closed),1)
        self.assertEqual(book.closed[0]["entryAt"],t+MS)
        self.assertTrue(book.intact())

    def test_missing_next_bar_rejects_not_invents_fill(self):
        p,_=self.fixture(100)
        start=p["phase"]["start"]
        t=start+27*WEEK
        v={"EURUSD":{"price":{t:100.,t+MS+MS:100.8},"observed":[t,t+MS+MS]}}
        c={"EURUSD":self.cost()}
        book=Book("FULL")
        alloc=dict(Id="id",Units=1)
        lk={"id":dict(symbol="EURUSD",family="TAIL_VOLATILITY_UNWIND",side=-1,horizon=240)}
        self.assertFalse(book.fill_after_decision(t,alloc,lk,v,c,"FULL",p))
        self.assertEqual(book.cash,200.)
        self.assertEqual(len(book.open),0)
        self.assertEqual(book.rejectedExecutionSource,1)

    def test_unknown_historical_scenario_never_zero_filled(self):
        p,v=self.fixture(200)
        t=p["phase"]["start"]+150*HR
        self.assertIsNone(path(v,"EURUSD",t+999999,4*HR,1,1000.))
        c=self.cost();c["fundingKnown"]=False
        self.assertIsNone(funding(c,1,t,t+DAY(),1000.))
        self.assertEqual(funding(c,1,t,t+MS,1000.),0.)

def DAY():return 24*HR

if __name__=="__main__":unittest.main()

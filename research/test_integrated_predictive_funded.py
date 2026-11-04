"""IPF1 tests of causal OHLCV features, forward maturity and common cash."""
import copy,json,math,unittest
from pathlib import Path
from .integrated_predictive_funded import market_view,window,features,OnlineModel,score_market,cost_context
from .integrated_funded_book import Book,swap_debit,request_for,candidate_prediction

class IntegratedPredictiveFundedChecks(unittest.TestCase):
    def fixture(self,hours=240):
        p=json.loads(Path("research/integrated_predictive_funded_protocol.json").read_text())
        p["training"]["warmupWeeks"]=0
        p["training"]["minimumMaturedObservations"]=0
        t=p["calendar"]["start"]
        # Start at a UTC H1 boundary from actual protocol epoch.
        t=(t//3600000)*3600000
        market={}
        for k,s in enumerate(p["sourceSymbols"]):
            arr=[]
            for j in range(hours*12):
                start=t+j*300000;price=100000*(1+0.00001*k)*(1+0.00000002*(j+k))
                arr.append([start,start+300000,price,price+1,price-1,price,60+j%6])
            market[s]=market_view(arr)
        cs={s:dict(observed=4,minimumNotionalEur=1000.,minimumMarginEur=30.,
                   centralBps=1.,adverseBps=2.,stressBps=4.,
                   fundingKnown=True,swapMinute=60,longDailyDebitBps=1.,
                   shortDailyDebitBps=1.) for s in market}
        return p,market,cs

    def test_higher_timeframe_uses_only_completed_actual_ohlcv(self):
        p,v,c=self.fixture(160)
        t=p["calendar"]["start"]+96*3600000
        a=features(v,t,"EURUSD",v,p)
        self.assertIsNotNone(a)
        self.assertEqual(len(a[0]),3)
        self.assertTrue(all(len(x)==6 for x in a[0].values()))
        before=a[0]
        altered=copy.deepcopy(v)
        # Mutate only 24h in the future, which cannot enter past features.
        for hour in list(altered["EURUSD"]["h"]):
            if hour>t:
                x=altered["EURUSD"]["h"][hour]
                altered["EURUSD"]["h"][hour]=(x[0],x[1]*3,x[2],x[3]*2,x[4],x[5])
        self.assertEqual(before,features(altered,t,"EURUSD",altered,p)[0])

    def test_prequential_future_labels_cannot_change_first_forecasts(self):
        p,v,c=self.fixture(240)
        early=score_market(v,p)
        self.assertGreater(len(early["forecasts"]),0)
        t=min(early["forecasts"])
        a=early["forecasts"][t]
        altered=copy.deepcopy(v)
        symbol=p["sourceSymbols"][0]
        for clock in altered[symbol]["price"]:
            if clock>t+2*86400000:
                altered[symbol]["price"][clock]*=1.5
        later=score_market(altered,p)
        self.assertEqual(a,later["forecasts"][t])
        self.assertEqual(early["numberModels"],later["numberModels"])

    def test_same_cash_invariants_and_swap_unknown(self):
        p,v,cs=self.fixture(160)
        t=p["calendar"]["start"]+96*3600000
        book=Book("FULL")
        self.assertAlmostEqual(book.cash,200.)
        self.assertEqual(book.mark(t,v,cs)["equity"],200.)
        # An unknown swap is not silently zero across a crossing.
        c=cs["EURUSD"].copy()
        c["fundingKnown"]=False
        self.assertIsNone(swap_debit(c,1,t,t+86400000,1000.))
        self.assertEqual(swap_debit(c,1,t,t+60000,1000.),0)
        self.assertEqual(book.snapshot(p["calendar"]["end"],v,cs)["closedNetEur"],0)
        x=dict(familyWeights={x:1/3 for x in (
                "MULTISCALE_REPRICING","ACTIVITY_VOLATILITY_REGIME","CROSS_ASSET_RELATIVE")},
            familyPredBps=dict(MULTISCALE_REPRICING=6.,
                ACTIVITY_VOLATILITY_REGIME=2.,CROSS_ASSET_RELATIVE=-2.),predictedBps=2.)
        self.assertAlmostEqual(candidate_prediction(x,"FULL"),2.)
        self.assertAlmostEqual(candidate_prediction(x,"WITHOUT_CROSS_ASSET_RELATIVE"),4.)

    def test_same_native_selector_batch_no_certificate(self):
        from .portfolio_economic_replay import native
        clock=1000000
        states=[dict(StateId="IPF1/check/"+str(i),KnownAt=100+i,
            Estimation=True,NetEur=0,LossEur=0,PeakEur=0,MarginEur=0) for i in range(8)]
        scenarios=[dict(StateId="IPF1/check/"+str(i),KnownAt=100+i,
            Estimation=True,NetPerUnitEur=.8,FixedCostEur=0,
            LossPerUnitEur=.5,PeakPerUnitEur=.5) for i in range(8)]
        grid=dict(EquityEur=200,CertifiedPeakEur=0,FreeMarginEur=200,
            MinimumUnits=1,StepUnits=1,MaximumUnits=3,MarginPerUnitEur=30,
            BrokerStopoutEquityToMargin=0,Reconciled=False,
            CompleteJointRiskEvidence=False,EffectiveIndependentBlocks=4,UncertaintyMultiplier=1)
        opp=dict(Id="IPF1/modelled-1",Candidate="FUSION",Symbol="EURUSD",
            RedundancyKey="EURUSD/check",Direction=1,AvailableAt=clock,
            CalibratedThrough=200,Level=1,ExecutionEvidenceComplete=False,
            VolumeGrid=grid,Scenarios=scenarios)
        account=dict(EquityEur=200,PeakReferenceEur=200,FreeMarginEur=200,
            MinimumUnits=1,StepUnits=1,MaximumUnits=3,
            MarginPerUnitEur=30,MarginCoverageScenarioRatio=1,
            EffectiveIndependentBlocks=4,UncertaintyMultiplier=1)
        req=dict(Scope="IPF1_MULTI_HORIZON_CONDITIONAL_RESEARCH_NOT_CERTIFIED",
            CommonHorizonMinutes=0,Clock=clock,Account=account,
            Baseline=states,Opportunities=[opp],LedgerReconciled=True,
            ScenarioCompleteOpportunityIds=[opp["Id"]])
        result=native([req]*4,"--estimate-portfolio-opportunities-batch")
        self.assertEqual(len(result),4)
        self.assertTrue(all(not x["Qualified"] for x in result))
        self.assertTrue(all(x["Status"].startswith("CONDITIONAL_RESEARCH_") for x in result))
        self.assertTrue(all(x["Allocations"] for x in result))
        self.assertTrue(all(float(x["Allocations"][0]["Units"])<=3 for x in result))
        # The verified endpoint remains blocked without broker certificates.
        self.assertTrue(all(not a.get("OrdersEnabled",False) for a in result))

if __name__=="__main__":unittest.main()

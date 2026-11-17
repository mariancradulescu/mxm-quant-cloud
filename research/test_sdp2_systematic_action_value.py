import json, os, subprocess, tempfile, unittest
from pathlib import Path
import numpy as np
from . import sdp2_systematic_action_value as s

class Checks(unittest.TestCase):
    def test_complete_buckets_only(self):
        rows=[[i*s.M5,(i+1)*s.M5,1,2,.5,1.1,3] for i in range(12)]
        self.assertEqual(len(s.aggregate(rows,15)),4)
        self.assertEqual(len(s.aggregate(rows[:-1],60)),0)
        self.assertEqual(len(s.aggregate(rows[:4]+rows[5:],60)),0)

    def test_purge_and_maturity(self):
        at=s.FIRST
        rows=[dict(t=at-5*s.WEEK,due=at-4*s.WEEK-4*s.H),
              dict(t=at-5*s.WEEK,due=at-4*s.WEEK-4*s.H-1),
              dict(t=at-s.WEEK,due=at-4*s.H),
              dict(t=at-s.WEEK,due=at-4*s.H-1)]
        train,cal=s.fit_masks(rows,at)
        self.assertEqual(train.tolist(),[False,True,False,False])
        self.assertEqual(cal.tolist(),[False,False,False,True])

    def test_unknown_future_and_fx_not_zero(self):
        ps={'EURUSD':{t:1.1 for t in range(0,2*s.H+s.M5,s.M5)}}
        terms={'EURUSD':dict(units=1000,quoteAsset='USD')}
        c={'EURUSD':dict(swapMinute=1320,fundingKnown=True,observedSpreadP90Bps=2,
          spreadMeanBps=1,conversionRate=.001,centralBps=3,adverseBps=5,longDailyDebitBps=1,shortDailyDebitBps=1)}
        r=dict(t=0,s='EURUSD',due=s.H+s.M5,scaleReturn=.001)
        y=s.payoff(r,ps,c,terms)
        self.assertTrue(np.all(y[0]<0))
        del ps['EURUSD'][30*s.M5//5]
        self.assertIsNone(s.payoff(r,ps,c,terms))
        self.assertIsNone(s.conversion('EURUSD',9*s.H,ps,terms))

    def test_feature_and_model_future_independence(self):
        w=[[i*s.H,(i+1)*s.H,100+i,102+i,99+i,101+i,10+i] for i in range(8)]
        f=s.scale_features(w,s.H)
        self.assertEqual(len(f[0]),12)
        self.assertEqual(f[0][-1],0)
        rng=np.random.default_rng(12);x=rng.normal(size=(600,4));y=np.column_stack([x[:,0],-x[:,0],x[:,0]-.1,-x[:,0]-.1])
        model=s.Boost().fit(x,y,np.ones(600));before=model.predict(x[:8])
        y[599]=1e6
        np.testing.assert_array_equal(before,model.predict(x[:8]))
        self.assertGreater(np.std(before[:,0]),0)
        executable=os.environ.get('SDP2_DOTNET')
        if executable:
            exported=model.export();exported['columns']=list(range(4))
            with tempfile.TemporaryDirectory() as td:
                a=Path(td)/'in.json';b=Path(td)/'out.json'
                a.write_text(json.dumps([dict(model=exported,x=x[i].tolist(),expected=before[i].tolist()) for i in range(8)]))
                subprocess.run([executable,'src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(a),str(b),'--sdp2-parity'],check=True)
                self.assertTrue(json.loads(b.read_text())['Passed'])
                a.write_text(json.dumps([w]))
                subprocess.run([executable,'src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(a),str(b),'--sdp2-feature-parity'],check=True)
                np.testing.assert_allclose(json.loads(b.read_text())[0],f[0],rtol=1e-12,atol=1e-12)


    def test_native_funded_not_only_rejections(self):
        executable=os.environ.get('SDP2_DOTNET')
        if not executable:self.skipTest('native build not configured')
        start=s.FIRST
        def quote(t):
            bid=1+(t-start)/s.H*.01
            return dict(Symbol='TEST',At=t,Bid=bid,Ask=bid+.0001,EurCredit=1,EurDebit=1,ExitFeePerUnit=.00001,ExitFeeFloor=0,MarginPerUnit=.1)
        payload=dict(Start=start,End=start+26*s.WEEK,Scenario='adverse',
          Quotes=[quote(t) for t in range(start,start+2*s.H,s.M5)],
          Contracts=[dict(Symbol='TEST',MinimumUnits=10,StepUnits=1,SwapMinute=1320,FundingKnown=True,LongDailyDebitBps=0,ShortDailyDebitBps=0)],
          Offers=[dict(At=start+1,Symbol='TEST',HorizonHours=1,Variant='FULL',CalibratedThrough=start-5*s.H,
            Means=[1,-1,1,-1],Scenarios=[[1+i*.001 for i in range(16)],[-1]*16,[1+i*.001 for i in range(16)],[-1]*16],Risk=[1,1,1,1])])
        prices={'TEST':{q['At']:q['Bid'] for q in payload['Quotes']}}
        terms={'TEST':dict(units=10,step=1,quoteAsset='EUR')}
        costs={'TEST':dict(spreadMeanBps=1,observedSpreadP90Bps=2,centralBps=3,adverseBps=5,
           conversionRate=.001,minimumMarginEur=1,swapMinute=1320,fundingKnown=True,longDailyDebitBps=0,shortDailyDebitBps=0)}
        payload=s.native_input({},prices,costs,terms,payload['Offers'],'adverse')
        label=s.payoff(dict(t=start,s='TEST',due=start+s.M5+s.H,scaleReturn=.001),prices,costs,terms)
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'in.json';b=Path(td)/'out.json';a.write_text(json.dumps(payload))
            subprocess.run([executable,'src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(a),str(b),'--sdp2-native'],check=True)
            report=json.loads(b.read_text());full=report['FULL']
            self.assertEqual(full['Final']['CompleteRoundTrips'],1)
            self.assertGreater(full['Final']['ClosedNetEur'],0)
            self.assertAlmostEqual(full['Final']['ClosedNetEur'],float(label[0][2]*label[1]),places=10)
            self.assertEqual(report['CASH']['Final']['CashEur'],300)
            self.assertFalse(full['Qualified']);self.assertEqual(full['Final']['OpenPositions'],0)
            self.assertEqual(sum(full['WeeklyCompletions'].values()),1)
            self.assertEqual(len(full['WeeklyCompletions']),26)

if __name__=='__main__':unittest.main()

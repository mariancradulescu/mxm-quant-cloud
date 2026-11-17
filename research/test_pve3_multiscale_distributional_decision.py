"""Pre-original synthetic PVE3 causality, multiscale parity and scorecard tests."""
import unittest,math
import numpy as np
from . import pve3_multiscale_distributional_decision as p

class Pve3Tests(unittest.TestCase):
    def rows(self,n,span,last,px=100.,volume=100.):
        return [[last-(n-j)*span,last-(n-j-1)*span,
            px,px*1.02,px*.98,px*(1+.001*((j%3)-1)),volume+j] for j in range(n)]

    def test_aggregates_exact_only(self):
        m5=self.rows(12,p.M5,12*p.M5)
        self.assertEqual(len(p.aggregate(m5,15)),4)
        self.assertEqual(len(p.aggregate(m5,60)),1)
        broken=m5[:5]+m5[6:]
        self.assertEqual(len(p.aggregate(broken,60)),0)

    def test_causal_features_and_peer_interactions(self):
        end=20*24*p.H
        a=self.rows(8,15*60000,end)
        b=self.rows(16,p.H,end)
        c=self.rows(8,4*p.H,end)
        out=p.features(a,b,c,end,peer_breadth=.5,peer_coverage=.75)
        self.assertIsNotNone(out)
        self.assertEqual(len(out),17)
        self.assertAlmostEqual(out[9],.5)
        self.assertAlmostEqual(out[10],.75)
        self.assertAlmostEqual(out[13],p.clip(out[0]*out[3]))
        self.assertAlmostEqual(out[14],p.clip(out[6]*out[7]))
        self.assertAlmostEqual(out[15],p.clip(out[4]*out[9]))
        self.assertAlmostEqual(out[16],p.clip(out[8]*out[2]))
        self.assertIsNone(p.features(a,b,c,end-p.M5))
        # Future completed candle changes cannot affect an earlier endpoint.
        bb=b[:-1]+[[*b[-1][:5],250.,b[-1][-1]]]
        self.assertNotEqual(p.features(a,b,c,end),p.features(a,bb,c,end))

    def test_ridge_same_locked_penalty_and_own_ablation(self):
        rng=np.random.default_rng(123)
        X=rng.normal(size=(150,17))
        y=2*X[:,0]*X[:,3]+rng.normal(size=150)*.05
        own=p.VARIANTS["OWN"]
        full=p.VARIANTS["FULL"]
        a=p.train_ridge(X,y,np.ones(len(y)),own)
        b=p.train_ridge(X,y,np.ones(len(y)),full)
        self.assertEqual(len(a),len(own)+1)
        self.assertEqual(len(b),len(full)+1)
        self.assertTrue(np.isfinite(b).all())
        self.assertEqual(len(p.fixed_quantiles(y)),16)
        self.assertEqual(len(p.predict(X,full,b)),len(X))
        self.assertTrue(p.positive_probability(.01,np.zeros(16),-.005,1.,1)>0)

    def test_cost_conversion_and_unknown_not_zero(self):
        prices={"EURUSD":{0:1.1,p.M5:1.1,p.H:1.1}}
        terms={"EURUSD":dict(quoteAsset="USD",units=1000)}
        self.assertAlmostEqual(p.conversion("EURUSD",p.M5,prices,terms),1/1.1)
        self.assertIsNone(p.conversion("EURUSD",999999,prices,terms))
        self.assertEqual(p.cross(0,p.H,1320),0)
        r=dict(t=0,s="EURUSD",at=p.M5,due=p.H+p.M5,sig=.001)
        self.assertIsNone(p.source_label(r,prices,terms,{}))
        c=dict(spreadMeanBps=1,observedSpreadP90Bps=2,
            centralBps=3,adverseBps=5,conversionRate=.001,
            swapMinute=1320,fundingKnown=True,longDailyDebitBps=0,
            shortDailyDebitBps=0)
        prices["EURUSD"]={t:1.1 for t in range(0,p.H+2*p.M5,p.M5)}
        lab=p.source_label(r,prices,terms,{"EURUSD":c})
        self.assertIsNotNone(lab)
        self.assertTrue(all(v<0 for v in lab["net"].values()))

    def test_no_future_execution_path_in_offer(self):
        t=p.START+2*p.WEEK
        row=dict(t=t,s="EURUSD",sig=.001)
        prices={"EURUSD":{t:1.1}}
        terms={"EURUSD":dict(quoteAsset="USD",units=100,step=1)}
        c=dict(adverseBps=3,centralBps=2,longDailyDebitBps=0,shortDailyDebitBps=0,
            fundingKnown=True,swapMinute=1320)
        offer=p.offer_for(row,0.,np.zeros(16),prices,terms,{"EURUSD":c},
                          "FULL",t-5*p.H)
        self.assertIsNotNone(offer)
        self.assertTrue(all(z<=0 for z in offer["ActionScore"]))
        self.assertTrue(all(z>0 for z in offer["RiskEur"]))

if __name__=="__main__":unittest.main()

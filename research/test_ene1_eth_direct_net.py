"""ENE1: SOURCE-BLIND fixed genuine M5/H1/H4 feature and EUR finance tests."""
import math,unittest
from decimal import Decimal as D
import numpy as np
from . import ene1_eth_original_source_and_features as s
from . import ene1_direct_net_eth_original as m

class Ene1Synthetic(unittest.TestCase):
    def bars(self):
        t=s.MONDAY+10*s.WEEK+8*3600000+30*60000
        a=[]
        for j in range(289):
            start=t-s.DAY+(j-1)*s.M5
            end=t-s.DAY+j*s.M5
            price=2500.+j*.011+math.sin(j/9)*.03
            p=int(price*s.PRICE_SCALE)
            a.append([start,end,p-5,p+100,p-130,p+25,170+j])
        return a,t

    def test_exact_authentic_289_m5_m15_m30_h1_h4_and_gap(self):
        a,t=self.bars()
        f,reason=s.features_from_original_m5(a,t)
        self.assertIsNone(reason)
        self.assertEqual(len(f),14)
        self.assertAlmostEqual(f[12],s.bounded(f[6]*f[5]),places=10)
        self.assertAlmostEqual(f[13],s.bounded(f[1]*f[4]),places=10)
        self.assertEqual(s.BASE_COLS,(0,2,5,10,11))
        self.assertIsNone(s.features_from_original_m5(a[:-1],t)[0])
        broken=[x[:] for x in a]
        broken[140][1]+=s.M5
        self.assertIsNone(s.features_from_original_m5(broken,t)[0])
        future=[x[:] for x in a]
        future[-1][1]+=s.M5
        self.assertIsNone(s.features_from_original_m5(future,t)[0])

    def test_original_net_with_spread_conversion_and_missing_exit_unknown(self):
        at=s.MONDAY+10*s.WEEK+8*3600000+30*60000+1500
        q0=dict(Symbol="ETHUSD",At=at,Bid="2500.0",Ask="2500.8",
            EurCredit=".90",EurDebit=".901",ExitFeePerUnit=".3",
            ExitFeeFloor="0",MarginPerUnit="1000")
        q1=dict(q0,At=at+1800000,Bid="2510.0",Ask="2510.8")
        row=dict(entry=q0,exit=q1)
        gain=s.payoff(row,1,"central",D(".01"))
        loss=s.payoff(row,-1,"adverse",D(".01"))
        self.assertGreater(gain,0)
        self.assertLess(loss,0)
        flat=s.payoff(dict(entry=q0,exit=q0),1,"adverse",D(".01"))
        self.assertLess(flat,0)
        self.assertIsNone(s.payoff(dict(entry=q0,exit=None),1,"adverse",D(".01")))

    def test_sides_are_eur_net_not_normalized_price_mse(self):
        rng=np.random.default_rng(13)
        X=rng.normal(size=(95,14))
        y=X[:,5]*.4+X[:,1]*.15+rng.normal(size=95)*.1-.5
        beta=m.ridge(X,y,s.FULL_COLS)
        self.assertEqual(len(beta),15)
        p=m.pred(X,s.FULL_COLS,beta)
        self.assertEqual(len(p),95)
        quant=m.quantile16(y-p)
        self.assertEqual(len(quant),16)
        z=m.risk_tail(-.05,quant)
        self.assertGreater(z["risk"],0)
        self.assertLess(z["score"],0)
        self.assertEqual(len(z["scenarioEur"]),16)

if __name__=="__main__":unittest.main()

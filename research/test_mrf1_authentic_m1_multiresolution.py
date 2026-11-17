"""MRF1 synthetic source/forecast/economic checks; never reads encrypted source."""
import unittest,math
import numpy as np
from . import mrf1_authentic_m1_multiresolution as m

class MRF1Checks(unittest.TestCase):
    def fake(self,t,n,minutes,base=1.2):
        width=minutes*m.M
        return [[t-(n-i)*width,t-(n-i-1)*width,
             base*(1+.00001*i),base*(1+.00001*i)+.0002,
             base*(1+.00001*i)-.0002,base*(1+.00001*(i+1)),
             100+i] for i in range(n)]

    def pack(self,rows):
        return dict(rows=rows,ends=[x[1] for x in rows],
          byend={x[1]:x for x in rows},bystart={x[0]:x for x in rows})

    def test_genuine_m1_can_make_m5_but_not_reverse(self):
        t=m.START+3*24*m.H+9*m.H
        fine=self.fake(t,180,1)
        five=m.strict_aggregate(fine,1,5)
        self.assertEqual(len(five),36)
        self.assertEqual(five[-1][1],t)
        with self.assertRaisesRegex(ValueError,"ONLY_COARSER"):
            m.strict_aggregate(five,5,1)
        fine[30][0]+=m.M
        self.assertLess(len(m.strict_aggregate(fine,1,5)),36)
        # At an intentionally misaligned 09:00 UTC end, preserve partial
        # higher-timeframe buckets as UNKNOWN rather than inventing candles.
        self.assertEqual(len(m.strict_aggregate(self.fake(t,48,60),60,240)),11)
        self.assertEqual(len(m.strict_aggregate(self.fake(t,48,30),30,1440)),0)
        aligned=m.START+4*24*m.H
        self.assertEqual(len(m.strict_aggregate(self.fake(aligned,48,60),60,240)),12)
        self.assertEqual(len(m.strict_aggregate(self.fake(aligned,48,30),30,1440)),1)

    def test_61_m1_and_seven_timeframes_never_future(self):
        t=m.START+3*24*m.H+9*m.H
        fine=self.fake(t,180,1)
        tf={"M1":self.pack(fine),
            "M5":self.pack(m.strict_aggregate(fine,1,5)),
            "M15":self.pack(m.strict_aggregate(fine,1,15)),
            "M30":self.pack(m.strict_aggregate(fine,1,30)),
            "H1":self.pack(m.strict_aggregate(fine,1,60)),
            "H4":self.pack(m.strict_aggregate(fine,1,240)),
            "D1":self.pack([])}
        z,why=m.frame("EURUSD",{"EURUSD":tf},t)
        self.assertIsNone(why)
        self.assertEqual(len(z["features"]),26)
        self.assertTrue(z["tfAvailable"]["M1"])
        self.assertTrue(z["tfAvailable"]["M5"])
        self.assertFalse(z["tfAvailable"]["D1"])
        self.assertIsNone(m.frame("EURUSD",{"EURUSD":tf},t+m.M)[0])
        future=self.fake(t+30*m.M,30,1)
        # Exact future path is NOT a source prerequisite for features at t.
        tf["M1"]["bystart"].update({x[0]:x for x in future})
        self.assertIsNotNone(m.source_price_label(z,tf,30))
        del tf["M1"]["bystart"][t+15*m.M]
        self.assertIsNone(m.source_price_label(z,tf,30))

    def test_ridge_fixed_no_hindsight_selection(self):
        rng=np.random.default_rng(31)
        X=rng.normal(size=(250,26))
        names=np.asarray(["EURUSD","XAUUSD","US500","NAS100"]*62+["EURUSD"]*2)
        y=X[:,0]*.7+X[:,24]*.3+rng.normal(size=250)*.1
        full=m.fit_ridge(X,y,names,m.FULL_COLS)
        base=m.fit_ridge(X,y,names,m.BASE_COLS)
        self.assertEqual(len(full),27)
        self.assertEqual(len(base),13)
        self.assertEqual(len(m.HORIZONS),3)
        self.assertTrue(np.isfinite(full).all())

    def test_costed_offers_do_not_use_future_exit_or_zero_unknown(self):
        t=m.START+16*24*m.H+8*m.H+30*m.M
        q=dict(Symbol="EURUSD",At=t+1500,Bid="1.09",Ask="1.0901",
          EurCredit="0.917",EurDebit="0.918",ExitFeePerUnit="0.0000276",
          MarginPerUnit="0.03333")
        row=dict(t=t,s="EURUSD",sig=.0001)
        pred=dict(mean=0.,quantile=[0.]*16,
                  calibrationThrough=t-4*m.H)
        a=m.money_offer(row,pred,dict(entry=q,exit=None),.0001,
                        "FULL",None,t,"adverse")
        b=m.money_offer(row,pred,dict(entry=q,exit={"Bid":"100000"}),
                        .0001,"FULL",None,t,"adverse")
        self.assertEqual(a,b)
        self.assertTrue(all(x<0 for x in a["ActionScore"]))
        self.assertTrue(all(x>0 for x in a["RiskEur"]))
        self.assertIsNone(m.money_offer(row,pred,dict(entry=None),.0001,
                                       "FULL",None,t,"adverse"))

    def test_flat_quote_crossing_loses_money(self):
        q=dict(Bid="1.1000",Ask="1.1002",EurCredit=".9089",
          EurDebit=".9093",ExitFeePerUnit=".000028")
        for side in (1,-1):
            z=m.actual_original_eur_payoff(q,q,side,m.D(1000),"adverse")
            self.assertLess(z["netEur"],0)
            self.assertGreater(z["frictionEur"],0)

if __name__=="__main__":unittest.main()

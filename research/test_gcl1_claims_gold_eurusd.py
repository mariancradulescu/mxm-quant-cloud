"""GCL1 synthetic regression: DOL calendar, causal conflict, no future, EUR costs."""
from datetime import date,timedelta
import unittest
from decimal import Decimal as D
from .gcl1_claims_quote_source import day_schedule,ts,pair
from .gcl1_claims_gold_eurusd_economic_readback import feature,direction,money,POLICIES

class Gcl1(unittest.TestCase):
    def points(self,day,gold_last=103,eur_last=98):
        dates=[ts(day,8,0)+i*300000 for i in range(10)]
        g=[100]*10;e=[100]*10
        g[9]=gold_last;e[9]=eur_last
        return {"XAUUSD":dict(zip(dates,g)),"EURUSD":dict(zip(dates,e))}
    def test_fixed_43_thursdays_and_43_tuesdays(self):
        rows=day_schedule()
        self.assertEqual(len(rows),86)
        self.assertEqual(sum(arm=="DOL_THURSDAY" for _,arm,_ in rows),43)
        self.assertEqual(sum(arm=="PLACEBO_TUE" for _,arm,_ in rows),43)
        self.assertEqual(rows[0][0],date(2026,1,6))
        self.assertEqual(rows[-1][0],date(2026,10,29))
    def test_gold_fx_conflict_independent_of_future(self):
        day=date(2026,6,11);bars=self.points(day)
        f=feature(bars,day)
        self.assertEqual(f["state"],"CONFLICT")
        self.assertEqual(direction(f,"gcl1"),1)
        self.assertEqual(direction(f,"ownMomentum"),-1)
        self.assertEqual(direction(f,"goldAlways"),1)
        for s in bars:bars[s][ts(day,9,35)]=1_000_000
        self.assertEqual(f,feature(bars,day))
    def test_same_sign_does_not_force_trade(self):
        day=date(2026,6,11)
        f=feature(self.points(day,103,102),day)
        self.assertEqual(f["state"],"NO_CONFLICT")
        self.assertEqual(direction(f,"gcl1"),0)
    def test_missing_causal_bar_cannot_be_turned_to_cash(self):
        day=date(2026,6,11);bars=self.points(day)
        bars["XAUUSD"].pop(ts(day,8,10))
        f=feature(bars,day)
        self.assertEqual(f["state"],"SOURCE_UNKNOWN")
        self.assertIsNone(direction(f,"gcl1"))
    def test_fresh_quotes_and_crossing(self):
        q=pair([[980,101_000]],[[990,101_003]],1000)
        self.assertIsNotNone(q)
        self.assertIsNone(pair([[980,101_005]],[[990,101_003]],1000))
    def test_frozen_benchmark_set(self):
        self.assertEqual(set(POLICIES),
          {"gcl1","ownMomentum","goldAlways","long","short","cash"})

if __name__=="__main__":
    unittest.main()

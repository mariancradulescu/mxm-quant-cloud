"""SPL1 synthetic invariant tests (NO real market outcomes / no credential access)."""
from datetime import date,timedelta
from decimal import Decimal as D
import unittest
from .spl1_original_eurgbp_source import calendar,event_clocks,stamp,chunks,sampled
from .spl1_original_sterling_financial_readback import feature,direction,POLICIES

class TestSpl1(unittest.TestCase):
    def sample(self,day,h=9,m=30):
        t=stamp(day,h,m)
        times=list(range(t-30*60000,t+1,300000))
        # EURGBP DOWN during first 15m = sterling strength; last GBPUSD
        # 15m DOWN = contradictory own move, predicts future GBPUSD UP.
        eur=[1000,990,980,970,975,980,990]
        gbp=[1000,1000,1000,1000,990,980,970]
        return t,dict(zip(times,eur)),dict(zip(times,gbp))
    def test_52weeks_two_nonoverlap_daily_clocks(self):
        items=list(event_clocks())
        self.assertEqual(len(items),520)
        self.assertEqual(items[0][0],date(2025,11,3))
        self.assertEqual(items[-1][0],date(2026,10,30))
        self.assertEqual(items[0][3]-items[0][2],300000)
        self.assertEqual(items[0][4]-items[0][2],2100000)
        self.assertLess(items[0][4],items[1][3])
    def test_london_dst(self):
        # 09:30 London is 08:30 UTC in June, 09:30 UTC in winter.
        self.assertEqual((stamp(date(2026,6,1),9,30)//60000)%1440,510)
        self.assertEqual((stamp(date(2026,1,5),9,30)//60000)%1440,570)
    def test_causal_gbp_specific_conflict(self):
        day=date(2026,6,1)
        t,eur,gbp=self.sample(day)
        f=feature(day,t,gbp,eur)
        self.assertEqual(f,{"state":"SPL1_LEAD_CONFLICT","sideL":1,"sideM":-1})
        self.assertEqual(direction(f,"spl1"),1)
        self.assertEqual(direction(f,"ownMomentum"),-1)
        for s in (eur,gbp):s[t+300000]=1
        self.assertEqual(feature(day,t,gbp,eur),f)
    def test_missing_source_remains_unknown(self):
        day=date(2026,6,1);t,eur,gbp=self.sample(day)
        eur.pop(t-1000000+100000) if t-900000 in eur else None
        eur.pop(t-900000)
        f=feature(day,t,gbp,eur)
        self.assertEqual(f["state"],"SOURCE_UNKNOWN")
        self.assertIsNone(direction(f,"spl1"))
    def test_nonconflict_abstains(self):
        day=date(2026,6,1);t,eur,gbp=self.sample(day)
        gbp[t]=1001
        f=feature(day,t,gbp,eur)
        self.assertEqual(f["state"],"NO_LEAD_CONFLICT")
        self.assertEqual(direction(f,"spl1"),0)
    def test_quote_missing_not_fake(self):
        t=1_000_000
        self.assertIsNone(sampled([[t-60_000,100001]],[[t-60_000,100002]],t))
        self.assertIsNone(sampled([[t-1_000,100002]],[[t-1_000,100001]],t))
        self.assertIsNotNone(sampled([[t-1_000,100001]],[[t-1_000,100002]],t))
    def test_six_fixed_benchmarks(self):
        self.assertEqual(set(POLICIES),{"spl1","ownMomentum","crossAlways","long","short","cash"})
    def test_fixed_nonoverlap_M5_archive_chunks(self):
        rows=list(chunks())
        self.assertGreaterEqual(len(rows),35)
        self.assertEqual(rows[0][0],1762128000000)
        self.assertEqual(rows[-1][1],1793577600000)
        self.assertTrue(all(rows[i][1]==rows[i+1][0] for i in range(len(rows)-1)))

if __name__=="__main__":
    unittest.main()

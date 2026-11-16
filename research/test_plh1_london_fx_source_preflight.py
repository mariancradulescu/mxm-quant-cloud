"""PLH1 synthetic no-hindsight, nondegenerate cross-currency handoff invariants."""
from datetime import date,timedelta
import unittest

from .plh1_london_fx_source_preflight import (
    SYMBOLS,USD_ORIENTATION,stamp,local_feature,costs
)

class TestPlh1(unittest.TestCase):
    def sample(self,day):
        first=stamp(day,4,0)
        last=stamp(day,8,15)
        dates=list(range(first,last+1,900000))
        s={}
        for name in SYMBOLS:
            direction=USD_ORIENTATION[name]
            start=10000
            # A common USD rise into 08:00 London.
            a=[start + direction*10*min(i,16) for i in range(len(dates))]
            # First London quarter-hour: three currencies reverse, one not.
            if name!="USDJPY":
                a[-1]=a[-2]+10
            elif name=="USDJPY":
                a[-1]=a[-2]-10
            s[name]=dict(zip(dates,a))
        return s
    def test_transfer_is_cross_market_and_causal(self):
        day=date(2026,9,14)
        rows=self.sample(day)
        x=local_feature(day,8,15,rows)
        self.assertEqual(x["state"],"TRANSFER")
        self.assertEqual(x["individualIntents"],4)
        self.assertEqual(x["asiaUsdSide"],1)
        # A return from the future cannot affect decision.
        for s in SYMBOLS:
            rows[s][stamp(day,8,45)]=999999
        self.assertEqual(x,local_feature(day,8,15,rows))
    def test_one_market_missing_is_unknown_not_abstention(self):
        day=date(2026,9,14)
        rows=self.sample(day)
        rows["GBPUSD"].pop(stamp(day,7,0))
        self.assertEqual(local_feature(day,8,15,rows)["state"],"SOURCE_UNKNOWN")
    def test_complete_nontransfer_is_different_state(self):
        day=date(2026,9,14)
        rows=self.sample(day)
        for s in SYMBOLS:
            rows[s][stamp(day,8,15)]=rows[s][stamp(day,8,0)]
        self.assertEqual(local_feature(day,8,15,rows)["state"],"COMMON_NO_TRANSFER")
    def test_cloud_session_clock_dst_changes_utc_but_not_local(self):
        a=stamp(date(2026,8,17),8,15)
        z=stamp(date(2026,11,9),8,15)
        self.assertEqual((a-z)%86400000,82800000)
    def test_four_fx_min_margin_and_explicit_commission_snapshot(self):
        c=costs()
        self.assertEqual(c["allFourStaticMarginEur"],133.85)
        self.assertTrue(c["staticMarginAllowed"])
        self.assertFalse(c["allInHistoricalFxCostKnown"])

if __name__=="__main__":
    unittest.main()

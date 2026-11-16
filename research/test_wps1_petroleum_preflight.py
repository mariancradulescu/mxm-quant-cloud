"""WPS1 causal, fixed-calendar and outcome-blind preflight unit checks."""
import unittest
from datetime import date,timedelta

from .wps1_petroleum_preflight import (
    releases, stamp, presignal_feature, COST_HURDLE_BPS, OFF
)


class Wps1Tests(unittest.TestCase):
    def make(self,day,wti_ratio=1.006,brent_ratio=1.002):
        clocks=[stamp(day,10,0)+i*300000 for i in range(10)]
        def state(start,multiple):
            vals=[start]*10
            vals[9]=int(start*multiple)
            return dict(zip(map(str,clocks),vals))
        return {"SpotCrude":state(8000000,wti_ratio),
                "SpotBrent":state(8200000,brent_ratio)}

    def test_official_five_shifted_dates_not_relabelled(self):
        d=releases()
        self.assertEqual(len(d),38)
        self.assertEqual(len(set(d)),38)
        self.assertTrue(all(x.weekday()==2 for x in d))
        self.assertTrue(all(x not in d for x in OFF))
        self.assertEqual(d[0],date(2026,1,7))
        self.assertEqual(d[-1],date(2026,10,28))

    def test_dst_ny_fixed_wall_clock_no_utc_assumption(self):
        self.assertEqual((stamp(date(2026,1,7),10,30) -
                          stamp(date(2026,7,8),10,30))%86400000,3600000)

    def test_states_and_cost_scale_without_future(self):
        day=date(2026,7,8)
        f=presignal_feature(self.make(day),day)
        self.assertEqual(f["state"],"WTI_LEADS")
        self.assertEqual(f["side"],1)
        self.assertTrue(f["halfResidualOverHurdle"])
        self.assertEqual(presignal_feature(
            self.make(day,1.001,1.004),day)["state"],"OTHER")

    def test_future_bars_never_used_for_feature(self):
        d=date(2026,7,8)
        x=self.make(d)
        f=presignal_feature(x,d)
        for s in x:
            x[s][str(stamp(d,10,50))]=500000000000
            x[s][str(stamp(d,11,35))]=1
        self.assertEqual(f,presignal_feature(x,d))

    def test_incomplete_market_bar_yields_unknown_not_abstain(self):
        d=date(2026,7,8)
        b=self.make(d)
        b["SpotBrent"].pop(str(stamp(d,10,25)))
        self.assertEqual(presignal_feature(b,d)["state"],
                         "MISSING_PREDECISION_SOURCE")


if __name__=="__main__":
    unittest.main()

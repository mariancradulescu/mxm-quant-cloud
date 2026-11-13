"""RNE1: causal public-release anomaly and sampled policy, no broker access."""
import unittest
from datetime import date, timedelta
from .rne1_eia_gas_release import (NY,START,stamp,sign,paired,bps,
                                   event_decision,markout,score_one)

class Rne1Tests(unittest.TestCase):
    def _bars(self,day,post=0):
        base=stamp(day,9,30)
        bars={}
        for i in range(34):
            time=base+i*300000
            # Pre-release four 15m intervals each 3 ticks, 1pt/5m
            close=100000+i*2
            if time>=stamp(day,10,35):
                close+=75
            if time>=stamp(day,10,40):
                close+=75
            if time>=stamp(day,10,45):
                close+=75
            if time>=stamp(day,11,15):
                close+=post
            bars[time]=close
        return bars
    def test_time_zone_dst_and_26_weeks(self):
        d1=date(2026,5,7)
        d2=date(2026,10,29)
        self.assertEqual(stamp(d1,10,30)-stamp(d1,9,30),3600000)
        self.assertEqual(stamp(d2,10,30)-stamp(d2,9,30),3600000)
        self.assertEqual(START+timedelta(weeks=26),date(2026,11,2))
    def test_anomaly_detected_only_after_completed_release_bar(self):
        d=date(2026,9,17)
        bars=self._bars(d)
        q=event_decision(d,bars)
        self.assertEqual(q['state'],'RELEASE_SHOCK_CANDIDATE')
        self.assertEqual(q['side'],1)
        self.assertEqual(q['exitAt'],'12:05')
        bars.pop(stamp(d,10,40))
        self.assertEqual(event_decision(d,bars)['state'],
                         'MISSING_COMPLETED_M5_FEATURES')
    def test_no_event_when_baseline_move_dominates(self):
        d=date(2026,9,17)
        bars={stamp(d,9,30)+300000*i:100000+10*i for i in range(34)}
        self.assertEqual(event_decision(d,bars)['state'],'NO_EVENT_ANOMALY')
    def test_sampled_price_crossing_not_fill(self):
        q=markout([1000,1002],[1001,1003],1)
        self.assertGreater(q[0],q[1])
        self.assertEqual(markout([1000,1002],[1001,1003],0),[0,0])
    def test_invalidating_event_changes_exit(self):
        d=date(2026,9,17)
        bars=self._bars(d,post=-300)
        q=event_decision(d,bars)
        self.assertEqual(q['state'],'RELEASE_SHOCK_CANDIDATE')
        self.assertTrue(q['invalidatedAt1115'])
        self.assertEqual(q['exitAt'],'11:20')
    def test_own_momentum_and_comparator_same_entry(self):
        day=date(2026,9,17)
        gas=self._bars(day)
        quote={'10:50':[1000,1002],'11:20':[1001,1003],
               '12:05':[1005,1007]}
        ev={'kind':'THURSDAY_OFFICIAL_EIA_SCHEDULE','gasBars':gas,
            'day':day,'week':0}
        row=score_one(ev,{'bars':gas,'quote':quote})
        self.assertEqual(row['state'],'ADAPTIVE_PRICED')
        self.assertIn('cash',row['paired'])
        self.assertEqual(row['paired']['eia'],row['paired']['gasSameSideFixed'])
        quote['12:05']=None
        row=score_one(ev,{'bars':gas,'quote':quote})
        self.assertEqual(row['state'],'MISSING_EXIT_QUOTE')

if __name__=="__main__":
    unittest.main()

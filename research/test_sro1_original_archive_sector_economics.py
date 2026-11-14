"""SRO1 test economic causes and benchmark accounting without original pricing."""
from datetime import date
import unittest
from .sro1_original_archive_sector_economics import (
    START,WEEKS,PAIRS,FIVE,stamp,feature,scored,group)

def bars(day,first_open,first_close,entry_open,exit_open):
    start=stamp(day,9,30)
    rows=[]
    for i in range(13):
        # This is deterministic TEST-ONLY synthetic source for correctness.
        o=first_open if i==0 else (
            entry_open if i<=2 else (exit_open if i==12 else entry_open))
        c=first_close if i==0 else o
        rows.append([start+i*FIVE,start+(i+1)*FIVE,o,max(o,c),min(o,c),c,1])
    return rows

class FrozenSectorRotationTests(unittest.TestCase):
    def setUp(self):
        self.day=date(2026,9,17)
        self.high=bars(self.day,100000,100200,100100,100600)
        self.broad=bars(self.day,100000,99800,99900,99700)

    def test_frozen_calendar_and_two_economic_rationales(self):
        self.assertEqual(START,date(2026,5,4))
        self.assertEqual(WEEKS,26)
        self.assertEqual(PAIRS,(("INDEX_SECTOR_ROTATION_CONTINUATION",
                                 "NAS100","US500",1),
                                ("ETF_AUCTION_DISLOCATION_REVERSION",
                                 "QQQ.US","SPY.US",-1)))

    def test_first_bar_feature_never_uses_later_bars(self):
        data=feature(self.day,self.high[:1],self.broad[:1])
        self.assertEqual(data["state"],"CAUSAL_OPPOSITION")
        self.assertEqual(data["higherFirstSide"],1)
        self.assertEqual(data["broadFirstSide"],-1)
        self.assertEqual(scored(self.day,self.high[:1],self.broad[:1],1)["state"],
                         "CAUSAL_EVENT_INCOMPLETE_OUTCOME_PATH")
        self.assertEqual(feature(self.day,self.high[:1],self.high[:1])["state"],
                         "NO_CROSS_SECTOR_OPPOSITION")

    def test_continuation_route_and_reversion_are_fixed_opposites(self):
        a=scored(self.day,self.high,self.broad,1)
        b=scored(self.day,self.high,self.broad,-1)
        self.assertEqual(a["state"],"MATCHED_GROSS_BAR_OPEN_PROXY")
        self.assertAlmostEqual(a["grossBps"]["primary"],-b["grossBps"]["primary"])
        self.assertGreater(a["grossBps"]["primary"],0)
        self.assertEqual(a["grossBps"]["cash"],0)
        self.assertAlmostEqual(a["grossBps"]["fixedHighMinusBroad"],
                               -a["grossBps"]["fixedBroadMinusHigh"])
        self.assertAlmostEqual(a["grossBps"]["reversePrimary"],
                               -a["grossBps"]["primary"])

    def test_any_missing_5m_outcome_closes_pricing(self):
        missing=self.high[:4]+self.high[5:]
        self.assertEqual(scored(self.day,missing,self.broad,1)["state"],
                         "CAUSAL_EVENT_INCOMPLETE_OUTCOME_PATH")

    def test_no_imputed_outcomes_and_130_scheduled(self):
        first=group([{"week":0,"state":"NO_CROSS_SECTOR_OPPOSITION"}]*130)
        self.assertEqual(first["scheduledDays"],130)
        self.assertEqual(first["eventIntents"],0)
        self.assertIsNone(first["grossMeanBpsByPolicy"]["primary"])
        self.assertEqual(first["grossSumBpsByPolicy"]["primary"],0)

if __name__=="__main__":
    unittest.main()

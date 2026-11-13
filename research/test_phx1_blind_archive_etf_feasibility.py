"""Blind source coverage and no endpoint-price scoring in PHX1."""
import unittest
from datetime import date
from .phx1_blind_archive_etf_feasibility import (
    ARCHIVE_DAYS,EXACT_NAMES,MAX_CALLS,M5,stamp,source_availability)

class BlindArchiveTests(unittest.TestCase):
    def test_archive_dates_are_pre_original_rne1_and_not_holidays(self):
        self.assertEqual(len(ARCHIVE_DAYS),6)
        self.assertEqual(len(set(ARCHIVE_DAYS)),6)
        self.assertTrue(all(d.weekday()==3 for d in ARCHIVE_DAYS))
        self.assertTrue(all(d<date(2025,11,3) for d in ARCHIVE_DAYS))
        self.assertEqual(MAX_CALLS,32)
    def test_no_selection_substitution(self):
        self.assertEqual(EXACT_NAMES,("US500","SPY.US","NAS100","QQQ.US"))
    def test_only_completed_timestamp_coverage(self):
        d=date(2025,10,23)
        lo,hi=stamp(d,9,25),stamp(d,10,55)
        bars=[(lo+i*M5,lo+(i+1)*M5,1,1,1,1,1)
              for i in range((hi-lo)//M5)]
        v=source_availability(bars,lo,hi)
        self.assertEqual(v["clockSlotsExpected"],18)
        self.assertEqual(v["originalClosedM5Bars"],18)
        self.assertTrue(v["consecutiveM5SlotsPresent"])
        gap=[x for i,x in enumerate(bars) if i!=2]
        self.assertFalse(source_availability(gap,lo,hi)["consecutiveM5SlotsPresent"])
    def test_ny_wall_time_even_during_dst(self):
        self.assertEqual(stamp(date(2025,2,6),10,55)-stamp(date(2025,2,6),9,25),90*60000)
        self.assertEqual(stamp(date(2025,7,10),10,55)-stamp(date(2025,7,10),9,25),90*60000)

if __name__=="__main__":
    unittest.main()

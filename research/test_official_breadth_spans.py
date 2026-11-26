import unittest
from .guard import CaptureContractError
from .owner_official_breadth_spans import bounds
class OfficialBarSpans(unittest.TestCase):
    def test_actual_bounds_do_not_infer_a_year_from_requested_dates(self):
        day=86400000;end=400*day
        short=bounds([[end-day,1]],'H1',end)
        full=bounds([[end-390*day,1],[end-day,1]],'H1',end)
        self.assertFalse(short['ReachesTwelveMonthStart'])
        self.assertTrue(full['ReachesTwelveMonthStart'])
        self.assertFalse(full['ContinuousCoverageCertified'])
        self.assertIsNone(bounds([],'M1',end)['FirstOpenAt'])
    def test_duplicate_and_forming_bars_are_rejected(self):
        with self.assertRaises(CaptureContractError):bounds([[1],[1]],'M5',1000000)
        with self.assertRaises(CaptureContractError):bounds([[900000]],'M5',1000000)
if __name__=='__main__':unittest.main()

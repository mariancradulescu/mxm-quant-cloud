import unittest
from .owner_eer1_source import schedule,selection,covered,START,STEP,DAY
class EerSourceChecks(unittest.TestCase):
    def test_calendar(self):
        x={"scheduleTimeZone":"UTC","schedule":[{"startSecond":86400,"endSecond":6*86400}]}
        c=schedule(x,START,START+7*DAY)
        self.assertIn(START+15000,c);self.assertNotIn(START+5*DAY+15000,c)
        self.assertIsNone(schedule({},START,START+DAY))
    def test_coverage(self):
        self.assertTrue(covered([[0,4,"VERIFIED_COMPLETE_PAGE",1,1],[5,9,"PROVIDER_NO_QUOTES",1,0]],0,9))
        self.assertFalse(covered([[0,4,"VERIFIED_COMPLETE_PAGE",1,1],[6,9,"VERIFIED_COMPLETE_PAGE",1,1]],0,9))

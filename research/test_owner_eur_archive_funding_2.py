import unittest
from .owner_eur_archive_funding_2 import merge_rollover,attach_closed_clocks,DAY

class FundingRecoveryChecks(unittest.TestCase):
    def test_missing_and_conflicting_quotes(self):
        old=[dict(At=1,RequestedCoverage=False)]
        q=dict(At=1,RequestedCoverage=True,Bid="2",Ask="3",BidAt=1,AskAt=1)
        self.assertEqual(merge_rollover(old,[q]),([q],[]))
        self.assertEqual(merge_rollover([q],[old[0]]),([q],[]))
        self.assertEqual(merge_rollover([q],[dict(q,Bid="1")]),(old,[1]))
    def test_unknown_calendar_never_certifies_closure(self):
        entry={}
        attach_closed_clocks(entry,None,DAY,4*DAY,[1320])
        self.assertEqual(entry["ClosedRolloverClocks"],[])
    def test_explicit_session_closure(self):
        entry={}
        # Thursday 1970-01-01 through Sunday; daily 00-01 on Thursday only.
        fields=dict(scheduleTimeZone="UTC",schedule=[dict(startSecond=4*86400,endSecond=4*86400+3600)])
        attach_closed_clocks(entry,fields,0,DAY,[0,1320])
        self.assertEqual(entry["ClosedRolloverClocks"],[1320*60000])

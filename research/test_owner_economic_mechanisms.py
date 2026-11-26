import unittest
from .owner_economic_mechanisms import financing_plan,valid_mark,closed_session_mark,DAY

class PreventiveFunding(unittest.TestCase):
    def fixture(self):
        start=1785715200000 # Monday 3 August 2026
        entries=[];tapes=[]
        for name,kind in (("US500",1),("EURUSD",0)):
            c=dict(SwapPeriodHours=24,SwapTimeUtcMinute=1320,ChargeSwapAtWeekends=False,
                   SkipSwapPeriods=0,SwapCalculationType=kind,LongSwap=-2,ShortSwap=1,QuoteAsset="USD")
            entries.append(dict(Market=dict(Name=name,DatedDevelopment=dict(Contract=c,AccountSwapFree=False)),
                ScheduledClocks=[],ClosedRolloverClocks=[],AmbiguousCalendarClocks=[]))
            tapes.append(dict(Name=name,FundingQuotes=[],Quotes=[]))
        return dict(Start=start,End=start+7*DAY,Markets=entries,Tapes=tapes,
                    Routes=dict(USD=[dict(Symbol="EURUSD")]))
    def test_all_potential_charges_and_conversions_not_old_positions(self):
        plan=financing_plan(self.fixture())
        self.assertEqual(len(plan['Audit']),10)
        self.assertEqual(len(plan['Targets']),10)
        self.assertEqual({x['Symbol'] for x in plan['Targets']},{'US500','EURUSD'})
    def test_missing_side_stale_future_and_conflict_are_not_zero(self):
        at=10_000_000
        q=dict(RequestedCoverage=True,Bid='2',Ask='3',BidAt=at,AskAt=at)
        self.assertTrue(valid_mark(q,at,True))
        self.assertFalse(valid_mark(dict(q,Ask=None),at,True))
        self.assertFalse(valid_mark(dict(q,BidAt=at+1),at,False))
        self.assertFalse(valid_mark(dict(q,Bid='4'),at,True))
        self.assertFalse(valid_mark(dict(q,BidAt=at-7200001),at,False))
    def test_closed_session_fallback_requires_official_calendar_and_fresh_prior_mark(self):
        at=10_000_000;prior=at-900000
        q=dict(At=prior,Bid='2',Ask='3',BidAt=prior,AskAt=prior)
        entry=dict(ScheduledClocks=[prior],ClosedRolloverClocks=[at],AmbiguousCalendarClocks=[])
        self.assertIsNotNone(closed_session_mark(entry,dict(Quotes=[q]),at))
        self.assertIsNone(closed_session_mark(dict(entry,ClosedRolloverClocks=[]),dict(Quotes=[q]),at))
        self.assertIsNone(closed_session_mark(dict(entry,AmbiguousCalendarClocks=[at-1]),dict(Quotes=[q]),at))

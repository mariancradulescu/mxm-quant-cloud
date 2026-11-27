import unittest
from .owner_financing_preflight_calendar_2 import classify_window,clocks,calendar_status,preflight

class FundingCalendar(unittest.TestCase):
    def test_august_weekend(self):
        self.assertEqual(calendar_status(1786140000000,False),'ELIGIBLE_CLOCK')
        self.assertEqual(calendar_status(1786226400000,False),'NO_WEEKEND_SWAP_CONDITIONAL')
        self.assertEqual(calendar_status(1786226400000,None),'UNKNOWN_CALENDAR')
    def test_charge_window_skip_and_missing(self):
        w=dict(AccountSwapFree=False,SwapPeriodHours=24,SkipSwapPeriods=1,ChargeSwapAtWeekends=False,
            ContractRateAvailable=True,SwapCalculationType=1,ChargeEvidence=[
              dict(At=t,HasRolloverBid=False,HasRolloverConversion=False)
              for t in (1786140000000,1786226400000,1786312800000,1786399200000)])
        self.assertEqual([s for _,s in classify_window(w)],['SKIPPED_PERIOD_CONDITIONAL',
            'NO_WEEKEND_SWAP_CONDITIONAL','NO_WEEKEND_SWAP_CONDITIONAL','MISSING_EVIDENCE_ON_ELIGIBLE_CLOCK'])
    def test_utc_clock_alignment(self):
        self.assertEqual(list(clocks(1786140000000-12345,1786140000000,1320)),[1786140000000])
    def test_shared_fx_deduplicates(self):
        c=dict(SwapPeriodHours=24,SwapTimeUtcMinute=1320,ChargeSwapAtWeekends=False,SkipSwapPeriods=0,
            LongSwap=1,ShortSwap=-1,TripleSwapWeekday=3,SwapCalculationType=0,QuoteAsset='USD')
        src=dict(Start=1786140000000-1234,End=1786140000000,Routes={'USD':[{'Symbol':'EURUSD'}]},
            Markets=[dict(Market=dict(Name=n,DatedDevelopment=dict(Contract=c,AccountSwapFree=False))) for n in ('A','B')],
            Tapes=[dict(Name='EURUSD',FundingQuotes=[])])
        p=preflight(src,lambda q,a,b:False)
        self.assertEqual(len(p['Targets']),2)
        self.assertTrue(all(t['DependentSymbols']==['A','B'] for t in p['Targets']))

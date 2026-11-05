"""MBF1 synthetic causal/unknown/cost screens. Never runs historical closed models."""
import json,unittest,math
from pathlib import Path
from .mbf1_research import HOUR,WEEK,cost_bps,signals,evaluate
from .mbf1_source import windows,cost_clocks
class MBF1Checks(unittest.TestCase):
    def setUp(self):self.p=json.loads(Path('research/mbf1_protocol.json').read_text())
    def test_readonly_fixed_request_grid(self):
        p=self.p
        self.assertEqual(len(windows(p)),52)
        self.assertEqual(len(cost_clocks(p)),39)
        self.assertEqual(3+8+52*4+39*4*2,531)
        self.assertEqual(p['sourceRequestCount'],531)
        self.assertEqual(len(p['candidateFamilies'])*len(p['holdingHorizonsHours']),8)
    def test_empty_is_not_profitable(self):
        p=self.p
        x=evaluate({s:{} for s in p['universe']},{}, {},p)
        self.assertEqual(len(x['families']),8)
        self.assertEqual(x['selectionOnlyConditionalFollowupCandidates'],[])
        self.assertIsNone(x['fundedNetEur'])
        self.assertFalse(x['nativeAllocatorInvoked'])
        for family in x['families']:
            self.assertEqual(family['phases']['selection']['allWeeklyCounts'],[0]*13)
            self.assertIsNone(family['costBps'])
    def test_quote_missing_never_treated_as_zero(self):
        p=self.p
        samples={s:[] for s in p['universe']}
        self.assertTrue(all(c is None for c in cost_bps(samples,p).values()))
        samples['ETHUSD']=[10]*8
        self.assertEqual(cost_bps(samples,p)['ETHUSD'],
            {'central':21,'adverse':32,'stress':54})
    def test_friday_weekday_and_weekend_crypto_signal_are_causal(self):
        p=self.p;start=p['startUtcMs'];t=start+5*24*HOUR+8*HOUR
        eth={t-j*HOUR:int(100000*(1-.04*j/8)) for j in range(9)}
        for h in range(1,7):eth[t+h*HOUR]=int(100000*(1+.002*h))
        prices={s:{} for s in p['universe']};prices['ETHUSD']=eth
        events,_=signals(prices,p)
        rows=[e for e in events if e['family']=='CRYPTO_WEEKEND_SHOCK_DRIFT' and e['at']==t]
        self.assertEqual({e['horizon'] for e in rows},{2,4})
        self.assertTrue(all(e['side']==1 for e in rows))
    def test_fx_london_reversal_is_previous_only(self):
        p=self.p;start=p['startUtcMs'];t=start+8*HOUR
        fx={t-j*HOUR:int(102000-(2000*j/8)) for j in range(9)}
        for h in range(1,7):fx[t+h*HOUR]=102000-50*h
        prices={s:{} for s in p['universe']};prices['GBPJPY']=fx
        rows,_=signals(prices,p)
        chosen=[e for e in rows if e['family']=='TOKYO_LONDON_FX_POSITION_UNWIND']
        self.assertEqual(len(chosen),2)
        self.assertEqual({e['side'] for e in chosen},{-1})
        self.assertTrue(all(e['grossBps']>0 for e in chosen))
    def test_no_forward_lookahead_after_signal(self):
        p=self.p;start=p['startUtcMs'];t=start+8*HOUR
        fx={t-j*HOUR:int(102000-(2000*j/8)) for j in range(9)}
        fx[t+HOUR]=102100
        prices={s:{} for s in p['universe']};prices['GBPJPY']=fx
        rows,omissions=signals(prices,p)
        self.assertFalse(any(e['family']=='TOKYO_LONDON_FX_POSITION_UNWIND' for e in rows))
        self.assertTrue(omissions.get('TOKYO_LONDON_FX_POSITION_UNWIND/FORWARD_MISSING',0)>0)
if __name__=='__main__':unittest.main()

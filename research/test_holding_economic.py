import unittest,copy,shutil,json
from pathlib import Path
from decimal import Decimal as D
from .portfolio_economic_source import partial_snapshot,clocks
from .portfolio_economic_replay import day_clock,native
from .portfolio_holding_replay import run_case

class SourceAsOf(unittest.TestCase):
    def test_partial_route_survives_unrelated_asset_absence_and_future_ticks(self):
        sides={'EURUSD':[[(1000,100)],[(1100,102)]],'XAUUSD':[None,None]}
        a=partial_snapshot(sides,1500,['EURUSD','XAUUSD'])
        self.assertIn('EURUSD',a['quotes']);self.assertNotIn('XAUUSD',a['quotes'])
        sides['EURUSD'][0].append((1800,999))
        self.assertEqual(a,partial_snapshot(sides,1500,['EURUSD','XAUUSD']))
    def test_prospective_grid_budget(self):
        p=json.loads(Path('research/portfolio_holding_protocol.json').read_text())
        self.assertEqual(len(p['cohorts']),3);self.assertEqual(len(p['replayDays']),12)
        self.assertEqual(len(clocks(p)),306)
        self.assertLessEqual(12*len(clocks(p))+57,p['maxEvidenceRequests'])
        self.assertTrue(all(max(c['calibrationDays'])<min(c['replayDays']) for c in p['cohorts']))

@unittest.skipUnless(shutil.which('dotnet') and Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists(),'native replay required')
class HoldingEconomics(unittest.TestCase):
    def fixture(self):
        p=json.loads(Path('research/portfolio_holding_protocol.json').read_text());p['universe']=['EURUSD','GBPUSD']
        p['cohorts']=p['cohorts'][:1];p['cohorts'][0]['replayDays']=p['cohorts'][0]['replayDays'][:1];p['replayDays']=p['cohorts'][0]['replayDays']
        p['calibrationDays']=p['cohorts'][0]['calibrationDays'];plan={};valued={};raw={}
        b=dict(protocolSha256='SYNTHETIC_ONLY',accountSwapFreeEffective=False,riskTerms=dict(leverageInCents=100000),symbols={},snapshots=raw,decisionClocks={d:day_clock(d) for d in p['calibrationDays']+p['replayDays']})
        for s in p['universe']:
            b['symbols'][s]=dict(quoteAsset='USD',currentMarginPerUnitBoundEur='.09',maxQueriedUnits=1000,
                contract=dict(minVolume=100000,stepVolume=100000,maxVolume=100000,swapPeriod=24,swapTime=1320),
                dynamicLeverage=[dict(volume=100000000,leverage=1000)])
        for day in p['calibrationDays']+p['replayDays']:
            start=day_clock(day)
            for c in p['families']:
                for s in p['universe']:plan[c,s,start]=dict(Side=1)
            for minute in [-D(1)/3]+list(range(0,241,15)):
                for off in (0,30000):
                    t=start+(-20000 if minute<0 else int(minute*60000))+off
                    px=D('1.1')+max(D(0),D(minute))*D('.00002')
                    if day in p['replayDays'] and minute>=15:px=D('1.08')
                    valued[str(t)]=dict(At=t+11000,Quotes={s:dict(Bid=px,Ask=px+D('.0002'),EurCreditPerQuote=1,EurDebitPerQuote=1,FeeLinearEurPerUnit=0,FeeFloorEur=0) for s in p['universe']})
                    raw[str(t)]=dict(at=t+11000,quotes={s:dict(bid=int(px*100000),ask=int((px+D('.0002'))*100000),bidAt=t+10000,askAt=t+11000) for s in p['universe']})
        bounds={(d,s):D('.09') for d in p['replayDays'] for s in p['universe']}
        return b,plan,valued,p,bounds

    def test_active_exit_is_later_than_trigger_and_cash_accounting_shared(self):
        b,plan,v,p,bounds=self.fixture()
        fixed=run_case(b,plan,v,p,240,False,D('.5'),bounds)
        active=run_case(b,plan,v,p,240,True,D('.5'),bounds)
        self.assertTrue(active['completeFlatLedger'])
        self.assertGreater(active['protectiveExitDecisions'],0)
        early=[t for t in active['completedTrades'] if t['closed_at']<day_clock(p['replayDays'][0])+240*60000]
        self.assertTrue(early)
        triggers=[x['observedAt'] for x in active['holdingRiskLedger'] if x['ExitIds']]
        self.assertTrue(all(t['closed_at']>min(triggers) for t in early))
        self.assertGreater(active['minimumSampledEquityToMargin'],D('.5'))
        self.assertFalse(active['accountStopoutThresholdVerified'])
        self.assertFalse(active['economicQualification'])
        for r in [fixed,active]:
            total=sum((D(t['net_eur']) for t in r['completedTrades']),D(0))
            self.assertEqual(r['ledgerReport']['balance_eur'],D(200)+total)

    def test_future_exit_changes_cannot_change_initial_admission(self):
        b,plan,v,p,bounds=self.fixture();a=run_case(b,plan,v,p,240,False,D('.5'),bounds)
        last=str(day_clock(p['replayDays'][0])+240*60000)
        for q in v[last]['Quotes'].values():q['Bid']+=D('.001');q['Ask']+=D('.001')
        z=run_case(b,plan,v,p,240,False,D('.5'),bounds)
        self.assertEqual(a['nativeDecisionReceipts'],z['nativeDecisionReceipts'])

    def test_missing_open_route_requests_exit_without_inventing_equity(self):
        b,plan,v,p,bounds=self.fixture();key=str(day_clock(p['replayDays'][0])+15*60000)
        v[key]['Quotes'].pop('GBPUSD');b['snapshots'][key]['quotes'].pop('GBPUSD')
        r=run_case(b,plan,v,p,240,True,D('.5'),bounds)
        self.assertTrue(r['completeFlatLedger']);self.assertTrue(r['executionOutcomeUncertain'])
        unknown=[x for x in r['holdingRiskLedger'] if x['Reason']=='EVIDENCE_GAP_EXIT_AT_NEXT_OBSERVED_QUOTE']
        self.assertTrue(unknown);self.assertIsNone(unknown[0]['EquityToMargin'])

    def test_missing_final_exit_retains_unresolved_positions(self):
        b,plan,v,p,bounds=self.fixture();end=day_clock(p['replayDays'][0])+240*60000
        for off in (0,30000):
            v[str(end+off)]['Quotes']={};b['snapshots'][str(end+off)]['quotes']={}
        r=run_case(b,plan,v,p,240,False,D('.5'),bounds)
        self.assertFalse(r['completeFlatLedger']);self.assertGreater(r['ledgerReport']['open_positions'],0)
        self.assertTrue(r['executionOutcomeUncertain']);self.assertFalse(r['economicQualification'])

    def test_leverage_tier_margin_and_unknown_stopout_are_separate(self):
        req=dict(EquityEur=200,PeakReferenceEur=200,DataComplete=True,AccountLeverage=100,
            Positions=[dict(Id='x',Symbol='EURUSD',Units=3000,EntryMarginPerUnitEur=D('.01'),StressLossEur=0)],
            SourceSymbols=dict(EURUSD=dict(quoteAsset='USD',dynamicLeverage=[dict(volume=100000,leverage=100),dict(volume=1000000,leverage=10)])),
            RawQuotes=dict(EURUSD=dict(bid=100000,ask=100000)),DocumentedReferenceStopoutRatio=D('.5'))
        r=native(req,'--assess-holding-risk');self.assertEqual(r['UsedMarginEnvelopeEur'],300)
        self.assertEqual(r['ExitIds'],['x']);self.assertFalse(r['AccountStopoutThresholdVerified'])
        req['EquityEur']=100;r=native(req,'--assess-holding-risk');self.assertTrue(r['DocumentedReferenceCrossed'])
        self.assertTrue(r['OutcomeUncertain'])
        req['DataComplete']=False;req['EquityEur']=None;r=native(req,'--assess-holding-risk')
        self.assertIsNone(r['EquityToMargin']);self.assertEqual(r['ExitIds'],['x'])

if __name__=='__main__':unittest.main()

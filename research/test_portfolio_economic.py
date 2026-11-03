import copy,unittest,shutil
from pathlib import Path
from decimal import Decimal as D
from .portfolio_economic_source import synchronized_snapshot,clocks,protocol
from .portfolio_economic_replay import run_replay,day_clock,native

class SourceSynchronization(unittest.TestCase):
    def test_no_future_side_or_stale_side_is_imputed(self):
        t=10000;sides={'A': [[(t+1000,100)],[(t+1200,102)]], 'B':[[(t+1300,200)],[(t+1400,201)]]}
        q=synchronized_snapshot(sides,t,['A','B'])
        self.assertEqual(q['at'],t+1400)
        self.assertEqual(q['quotes']['A']['bidAt'],t+1000)
        sides['B'][1]=[(t+8000,201)]
        self.assertIsNone(synchronized_snapshot(sides,t,['A','B']))

    def test_fixed_economic_grid_is_bounded(self):
        p=protocol();self.assertEqual(len(clocks(p)),90)
        self.assertLess(12*len(clocks(p))+21,p['maxEvidenceRequests'])
        for d in p['replayDays']:
            self.assertLess(day_clock(d)-p['preDecisionQuoteSeconds']*1000+11000,day_clock(d))

@unittest.skipUnless(shutil.which('dotnet') and Path('src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll').exists(),'native replay required')
class IntegratedConditionalLedger(unittest.TestCase):
    def fixture(self):
        p=protocol();p['universe']=['EURUSD','GBPUSD'];p['calibrationDays']=p['calibrationDays'][:4];p['replayDays']=p['replayDays'][1:3]
        b=dict(protocolSha256='synthetic',symbols={s:dict(currentMinMarginEur='10',currentMarginPerUnitBoundEur='10',maxQueriedUnits=1,contract=dict(minVolume=100,stepVolume=100,maxVolume=100,swapPeriod=24,swapTime=1320)) for s in p['universe']})
        v={};plan={}
        for day in p['calibrationDays']+p['replayDays']:
            start=day_clock(day)
            for family in p['families']:
                for s in p['universe']:plan[family,s,start]=dict(Side=1)
            for minute in [-20/60]+list(range(0,241,30)):
                nominal=start+int(minute*60000);price=D(1)+D(str(max(0,minute)))/D(12000)
                v[str(nominal)]=dict(At=nominal+1500,Quotes={s:dict(Bid=price,Ask=price+D('.0002'),EurCreditPerQuote=1,EurDebitPerQuote=1,FeeLinearEurPerUnit=D('.001'),FeeFloorEur=0) for s in p['universe']})
        return b,plan,v,p

    def test_native_cross_currency_fees_and_current_minimum_floor(self):
        prices={'EURUSD':('1.1','1.1001'),'GBPUSD':('1.3','1.3001'),'USDJPY':('150','150.001'),
                'USDCAD':('1.35','1.3501'),'AUDUSD':('.65','.6501'),'XAUUSD':('2300','2300.1')}
        symbols={};quotes={}
        for s,(bid,ask) in prices.items():
            symbols[s]=dict(quoteAsset='JPY' if s=='USDJPY' else 'CAD' if s=='USDCAD' else 'USD',
                contract=dict(lotSize=10000000,preciseTradingCommissionRate=3000000000,
                preciseMinCommission=0,commissionType=1,minCommissionType=1,minCommissionAsset='USD',pnlConversionFeeRate=0))
            quotes[s]=dict(bid=int(D(bid)*100000),ask=int(D(ask)*100000),bidAt=11000,askAt=11500)
        source=dict(schema='mxm-epa1-source-v1',readOnly=True,depositCurrency='EUR',symbols=symbols,
                    snapshots={'10000':dict(at=11500,quotes=quotes)})
        result=native(source,'--value-portfolio-source')['Snapshots']['10000']['Quotes']
        jpy=result['USDJPY'];self.assertGreater(jpy['FeeLinearEurPerUnit'],D('.00002727'))
        self.assertLess(jpy['FeeLinearEurPerUnit'],D('.00002728'))
        self.assertLess(jpy['EurCreditPerQuote'],jpy['EurDebitPerQuote'])
        symbols['USDJPY']['contract'].update(preciseMinCommission=100000000,minCommissionAsset='EUR')
        result=native(source,'--value-portfolio-source')['Snapshots']['10000']['Quotes']
        self.assertEqual(result['USDJPY']['FeeFloorEur'],1)

    def test_shared_native_decisions_and_exact_common_ledger(self):
        b,plan,v,p=self.fixture();r=run_replay(b,plan,v,p,D(2),D('.5'))
        self.assertEqual(r['ledgerReport']['complete_round_trips'],4)
        self.assertEqual(r['ledgerReport']['closed_net_eur'],D('.0704'))
        self.assertEqual(r['ledgerReport']['balance_eur'],D('200.0704'))
        self.assertTrue(r['completeFlatLedger'])
        self.assertFalse(r['finalTradingQualification'])
        self.assertFalse(r['historicalFinancingVerified'])
        self.assertTrue(any(x['reason']=='REDUNDANT_OPPORTUNITY' for x in r['opportunityLedger']))

    def test_future_exit_cannot_change_earlier_allocations(self):
        b,plan,v,p=self.fixture();first=run_replay(b,plan,v,p,D(2),D('.5'))
        last=day_clock(p['replayDays'][-1])+4*3600000
        for q in v[str(last)]['Quotes'].values():q['Bid']+=D('.01');q['Ask']+=D('.01')
        second=run_replay(b,plan,v,p,D(2),D('.5'))
        self.assertEqual(first['nativeDecisionReceipts'],second['nativeDecisionReceipts'])
        self.assertNotEqual(first['ledgerReport']['closed_net_eur'],second['ledgerReport']['closed_net_eur'])

    def test_missing_exit_never_becomes_zero_loss_or_new_admission(self):
        b,plan,v,p=self.fixture();v.pop(str(day_clock(p['replayDays'][0])+4*3600000))
        r=run_replay(b,plan,v,p,D(2),D('.5'))
        self.assertFalse(r['completeFlatLedger'])
        self.assertGreater(r['ledgerReport']['open_positions'],0)
        self.assertTrue(any(x['reason']=='UNRESOLVED_EXPOSURE_ENTRIES_SUSPENDED' for x in r['sourceGaps']))

if __name__=='__main__':unittest.main()

"""Synthetic contract tests only; never original economic evidence."""
import json, os, subprocess, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path

class LifecycleNative(unittest.TestCase):
    def test_complete_paths_finance_and_chronology(self):
        start=int(datetime(2026,8,17,tzinfo=timezone.utc).timestamp()*1000)
        day=86400000;minute=60000
        def price(t):
            k=(t//30000)%80
            return 110000+(k if k<40 else 80-k)*4+(t//day)%5
        bars=[];days=[]
        for t in range(start-3*day,start+84*day,5*minute):
            prices=[price(x) for x in range(t,t+5*minute,30000)]
            bars.append([t,t+5*minute,prices[0],max(prices),min(prices),prices[-1],100])
        for d in range(start,start+84*day,day):
            if datetime.fromtimestamp(d/1000,timezone.utc).weekday()>=5:continue
            ticks=list(range(d+479*minute,d+725*minute,30000))
            days.append(dict(Start=d,Bid=[[t,price(t)] for t in ticks],Ask=[[t,price(t)+10] for t in ticks]))
        contract=dict(Symbol='EURUSD',QuoteAsset='USD',ObservedAtUtcMs=start+90*day,MinimumUnits=1000,
            VolumeStepUnits=1000,MaximumUnits=100000,LotUnits=100000,CommissionType=2,PreciseRateWire=350000000,
            MinimumCommissionType=1,PreciseMinimumWire=0,MinimumCommissionAsset='USD',PnlConversionFeeBps=0,
            SwapCalculationType=1,LongSwap=0,ShortSwap=0,PipPosition=4,SwapPeriodHours=24,SwapTimeUtcMinute=1320,
            TripleSwapWeekday=3,ChargeSwapAtWeekends=False,SkipSwapPeriods=0,OriginalBrokerAuthenticated=True,
            HistoricalTariffContinuityCertified=False)
        data=dict(Start=start,End=start+84*day,Contract=contract,MinMargin=34,TickSize=.00001,Bars=bars,Days=days)
        with tempfile.TemporaryDirectory() as tmp:
            inp=Path(tmp)/'source.json';out=Path(tmp)/'result.json';inp.write_text(json.dumps(data))
            proc=subprocess.run([os.environ.get('LPM1_DOTNET','dotnet'),'src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(inp),str(out),'--native-lpm1'],capture_output=True,text=True,timeout=300)
            self.assertEqual(proc.returncode,0,proc.stderr[-2000:])
            result=json.loads(out.read_text())
            self.assertEqual(len(result['Books']),18)
            self.assertTrue(all(x is not None for x in result['ContextModels']))
            fixed=0
            for key,b in result['Books'].items():
                self.assertTrue(b['FullSettlementKnown'],key)
                self.assertEqual(b['Ledger']['OpenPositions'],0)
                self.assertAlmostEqual(b['Ledger']['CashEur']-300,sum(t['NetEur'] for t in b['Trades']),places=7)
                self.assertEqual(len(b['Scorecard']['FundedCompletionsByIsoWeek']),3)
                self.assertFalse(b['Qualified'])
                for t in b['Trades']:self.assertGreater(t['ClosedAt'],t['OpenedAt'])
                if key.startswith('VOL_'):fixed+=len(b['Trades'])
            self.assertGreater(fixed,0)
            self.assertEqual(result['Books']['CASH_adverse']['Ledger']['CashEur'],300)
            self.assertFalse(result['IndependentConfirmation'])
if __name__=='__main__':unittest.main()

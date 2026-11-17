"""Synthetic verification, never broker evidence or economic qualification."""
import json,math,os,subprocess,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
class ContextValue(unittest.TestCase):
 def test_causal_books_and_common_capital(self):
  start=int(datetime(2026,5,4,tzinfo=timezone.utc).timestamp()*1000);day=86400000;minute=60000
  def price(t,m):
   return round(110000+8000*m+130*math.sin((t-start)/minute/80+m*.3)+70*math.sin((t-start)/day/2)+30*math.sin((t-start)/minute/8))
  markets=[]
  for m,name in enumerate(('EURUSD','GBPUSD','AUDUSD')):
   frames={}
   for frame,minutes,warm in [('M1',1,3),('M5',5,4),('M15',15,5),('M30',30,8),('H1',60,12),('H4',240,80),('D1',1440,100)]:
    rows=[]
    for t in range(start-warm*day,start+84*day,minutes*minute):
     ps=[price(t+j*minutes*minute//8,m) for j in range(8)]
     rows.append([t,t+minutes*minute,ps[0],max(ps)+2,min(ps)-2,ps[-1],100+(t//minute)%37])
    frames[frame]=rows
   days=[]
   for d in range(start,start+84*day,day):
    if datetime.fromtimestamp(d/1000,timezone.utc).weekday()>=5:continue
    ts=range(d+479*minute,d+665*minute,30000)
    days.append(dict(Start=d,Bid=[[t,price(t,m)] for t in ts],Ask=[[t,price(t,m)+3] for t in ts]))
   contract=dict(Symbol=name,QuoteAsset='USD',ObservedAtUtcMs=start+90*day,MinimumUnits=1000,VolumeStepUnits=1000,MaximumUnits=100000,LotUnits=100000,CommissionType=2,PreciseRateWire=350000000,MinimumCommissionType=1,PreciseMinimumWire=0,MinimumCommissionAsset='USD',PnlConversionFeeBps=0,SwapCalculationType=1,LongSwap=0,ShortSwap=0,PipPosition=4,SwapPeriodHours=24,SwapTimeUtcMinute=1320,TripleSwapWeekday=3,ChargeSwapAtWeekends=False,SkipSwapPeriods=0,OriginalBrokerAuthenticated=True,HistoricalTariffContinuityCertified=False)
   markets.append(dict(Name=name,Contract=contract,MinMargin=34,TickSize=.00001,Frames=frames,Days=days))
  with tempfile.TemporaryDirectory() as tmp:
   inp=Path(tmp)/'input.json';out=Path(tmp)/'out.json';inp.write_text(json.dumps(dict(Start=start,End=start+84*day,Markets=markets)))
   proc=subprocess.run([os.environ.get('CVP1_DOTNET','dotnet'),'src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll',str(inp),str(out),'--native-cvp1'],capture_output=True,text=True,timeout=500)
   self.assertEqual(proc.returncode,0,proc.stderr[-3000:]);r=json.loads(out.read_text());self.assertEqual(len(r['Books']),16)
   for k,b in r['Books'].items():
    self.assertTrue(b['FullSettlementKnown'],k)
    self.assertAlmostEqual(b['Ledger']['CashEur']-300,sum(t['NetEur'] for t in b['Trades']),places=7)
    self.assertEqual(len(b['Scorecard']['FundedCompletionsByIsoWeek']),3)
    self.assertFalse(b['Qualified']);self.assertEqual(b['Ledger']['OpenPositions'],0)
    for t in b['Trades']:self.assertGreater(t['ClosedAt'],t['OpenedAt'])
   self.assertGreater(len(r['Books']['SIMPLE_adverse']['Trades']),20)
   self.assertGreater(r['Books']['SIMPLE_adverse']['MaximumConcurrentPositions'],1)
   self.assertEqual(r['Books']['CASH_adverse']['Ledger']['CashEur'],300)
   self.assertFalse(r['IndependentConfirmation'])
   self.assertTrue(all(x['Transitions']>1000 for x in r['Models'].values()))
   self.assertTrue(all(x['Entry'][0] is not None for x in r['Models'].values()))
if __name__=='__main__':unittest.main()

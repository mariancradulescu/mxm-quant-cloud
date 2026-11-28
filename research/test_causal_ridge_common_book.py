"""Meaningful native causality checks: future value changes and missing labels."""
import datetime,hashlib,json,math,struct,subprocess,tempfile,unittest
from pathlib import Path
from .owner_causal_ridge_common_book import check
DAY=86400000
DLL='src/Mxm.PathResearch/bin/Release/net8.0/Mxm.PathResearch.dll'
def fixture(days=50):
    start=int(datetime.datetime(2025,11,1,tzinfo=datetime.timezone.utc).timestamp())*1000;markets=[]
    for s in range(3):
        def price(i):return 100+s+0.0003*i+.07*math.sin(i/12+s)+.03*math.cos(i/41)
        fast=[]
        for i in range(days*288):
            o,c=price(i),price(i+1);fast.append(dict(OpenAt=start+i*300000,CloseAt=start+(i+1)*300000,
                Open=o,High=max(o,c)+.01,Low=min(o,c)-.01,Close=c,TickVolume=100+i%7))
        def aggregate(width):
            return [dict(OpenAt=v[0]['OpenAt'],CloseAt=v[-1]['CloseAt'],Open=v[0]['Open'],High=max(x['High'] for x in v),
                Low=min(x['Low'] for x in v),Close=v[-1]['Close'],TickVolume=sum(x['TickVolume'] for x in v))
                for j in range(0,len(fast),width) if len(v:=fast[j:j+width])==width]
        markets.append(dict(Symbol='SYNTHETIC_'+str(s),AssetClass='SYNTHETIC',Bars=dict(M5=fast,M15=aggregate(3),H1=aggregate(12)),Quotes=[]))
    return markets,start
class RidgeMonetary(unittest.TestCase):
    def test_registered_monetary_variants(self):self.assertEqual(check()['CommonBookEvaluations'],20)
    def test_native_raw_projection_rejects_staleness_and_conflicts(self):
        start=1795564800000;at=start+15000;name='SYNTHETIC_QUOTE'
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);tape=root/'tape';tape.mkdir();source=root/'source.json';output=root/'projection.json'
            source.write_text(json.dumps(dict(Start=start,End=start+600000,Tapes=[dict(Name=name),dict(Name='NO_QUOTES')],
                Markets=[dict(Unrelated='ignored large-schema field')])));prefix=hashlib.sha256(name.encode()).hexdigest()
            for side,when,raw in [('bid',at-1000,110000),('ask',at-500,110010)]:
                (tape/(prefix+'-'+side+'-eer1.ticks')).write_bytes(struct.pack('<qq',when,raw))
                (tape/(prefix+'-'+side+'-eer1.coverage')).write_bytes(struct.pack('<qq',when,at))
            def run():
                subprocess.run(['dotnet','src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll','--owner-protection-grid-quotes',str(source),str(tape),str(output)],check=True)
                return json.loads(output.read_text())
            result=run();rows={r['Symbol']:r['Quotes'] for r in result['Rows']}
            self.assertEqual(len(rows[name]),1);self.assertEqual(rows['NO_QUOTES'],[])
            self.assertEqual(rows[name][0]['At'],at);self.assertEqual(rows[name][0]['BidAt'],at-1000)
            with (tape/(prefix+'-bid-eer1.ticks')).open('ab') as f:f.write(struct.pack('<qq',at-1000,110001))
            self.assertTrue(all(not r['Quotes'] for r in run()['Rows']))
            self.assertFalse(result['ValuationPrefixesUsedForExecution']);self.assertEqual(result['Orders'],0)
    def test_native_forecasts_ignore_changed_and_censored_future(self):
        markets,start=fixture();cut=start+35*DAY+12*3600000;edge=cut+15000
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            def run(tag,values):
                source,result,forecasts=[root/(tag+'-'+n+'.json') for n in ('source','result','forecasts')]
                source.write_text(json.dumps(values));subprocess.run(['dotnet',DLL,'--breadth-ridge-monetary-signals',str(source),str(result),str(forecasts)],check=True)
                return [r for r in json.loads(forecasts.read_text()) if r['Forecast']['DecisionAt']<=edge]
            baseline=run('full',markets);self.assertGreater(len(baseline),100)
            changed=json.loads(json.dumps(markets));truncated=json.loads(json.dumps(markets))
            for market in changed:
                for rows in market['Bars'].values():
                    for b in rows:
                        if b['OpenAt']>=cut:
                            for k in ('Open','High','Low','Close'):b[k]*=1.7
            for market in truncated:
                for tf,rows in market['Bars'].items():market['Bars'][tf]=[b for b in rows if b['CloseAt']<=cut]
            self.assertEqual(baseline,run('changed',changed))
            self.assertEqual(baseline,run('truncated',truncated))
            self.assertTrue(any(r['Forecast']['DecisionAt']==edge for r in baseline),'A prediction survives missing later labels at the source boundary')
            self.assertTrue(all(r['Forecast']['LatestTrainingAt']<r['Forecast']['FitBefore']<=r['Forecast']['DecisionAt'] for r in baseline))
if __name__=='__main__':unittest.main()

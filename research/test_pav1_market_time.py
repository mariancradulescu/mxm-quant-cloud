"""Causal common-book protocol and existing authentic-prefix reuse."""
import copy,json
from pathlib import Path
import subprocess,tempfile,unittest
from .test_owner_eur_checkpoint import fixture,START,DAY
from .owner_pav1_market_time import registered,select,add_funding_prefixes,REPLAY

class PavMarketTime(unittest.TestCase):
    def test_registration_and_fixed_hypotheses(self):
        p,_=registered()
        self.assertEqual((len(p['Variants']),len(p['Instruments'])),(13,25))
        rows={v['Id']:v['Profile'] for v in p['Variants']}
        self.assertEqual({k:v for k,v in rows['MT21_RISK_CONTROL'].items() if k!='UseMarketTimeFxValuation'},rows['STRICT21_RISK_CONTROL'])
        self.assertTrue(rows['MT25_CASH_VOLUME']['RequireMaturedCashForLargerVolume'])
        self.assertTrue(rows['MT25_ALLOC_MIN']['MinimumContractVolumeOnly'])

    def test_selection_uses_one_config_all_stresses_and_never_unknown(self):
        def row(id,score,net=1):return dict(Id=id,Monetary=dict(Score=score,GrossEur=1,NetEur=net),Result=dict(Hard21AllFullRegisteredWeeks=True,SampledDrawdown=0,MaxSampledHeldPendingMarginFraction=0))
        data=[row('A',2),row('A',1),row('A',None),row('B',1),row('B',1),row('B',1)]
        self.assertEqual(select(data)['Decision'],'B')
        self.assertEqual(select([row('A',3),row('A',2),row('A',1,-1)])['Decision'],'WAIT')
        self.assertEqual(select([row('A',3),row('A',2)])['Decision'],'WAIT')

    def test_native_common_book_with_25_synthetic_markets(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work);source=json.loads((work/'source.json').read_bytes())
            original=copy.deepcopy(source['Markets'][0]);tape=source['Tapes'][0]
            names=[f'SYNTH_{i:02}' for i in range(25)];source['Markets']=[];source['Tapes']=[]
            for name in names:
                row=copy.deepcopy(original);row['Market']['Name']=name
                row['Market']['Contract']['Symbol']=name;row['Market']['DatedDevelopment']['Contract']['Symbol']=name
                source['Markets'].append(row);source['Tapes'].append(dict(tape,Name=name))
            source.update(End=START+3*DAY,ExtendedEconomicContext=True)
            for row in source['Markets']:
                row['ScheduledClocks']=[x for x in row['ScheduledClocks'] if x<source['End']+7*DAY]
            (work/'source.json').write_text(json.dumps(source))
            p,_=registered();plan={k:p[k] for k in ('Study','Exposure','Stresses','Variants')}
            plan.update(Start=START,SelectionFrom=START+DAY,EvaluationFrom=START+2*DAY,End=START+3*DAY,
                OriginalInstruments=names[:21],SourceProtocolSha256=source['ProtocolSha256'],EvidenceManifestSha256=source['EvidenceManifestSha256'])
            (work/'plan.json').write_text(json.dumps(plan))
            subprocess.run(['dotnet',REPLAY,'--owner-pav1-market-time',str(work/'plan.json'),str(work/'source.json'),
                str(work/'result'),str(work/'verified-protection'),'0'],check=True,stdout=subprocess.DEVNULL)
            report=json.loads((work/'result/result.json').read_bytes())
            self.assertEqual((report['Orders'],report['CloudActivated'],report['SharedPortfolioEvaluations']),(0,False,15))
            self.assertEqual(report['CheckpointPhases'],2)
            self.assertEqual(len(list((work/'result/checkpoints').glob('*/*.json'))),30)
            for row in report['CommonBooks']:
                self.assertEqual(row['Result']['InitialCapitalEur'],300)
                if row['Id'].startswith('CASH_'):self.assertEqual((row['Result']['CashEur'],row['Result']['Closed']),(300,0))
                self.assertTrue(all((e['RiskChangeAtFillEur'] or 0)<=0 for e in row['Details']['Episodes']))
            self.assertGreater(sum(r['Result']['Closed'] for r in report['CommonBooks']),0)
            for row in report['Selection']:
                self.assertTrue(all(day['Day']<plan['EvaluationFrom'] for day in row['Monetary']['Daily']))

if __name__=='__main__':unittest.main()

"""Causal common-book protocol and existing authentic-prefix reuse."""
import copy,json,os
from unittest.mock import patch
from pathlib import Path
import subprocess,tempfile,unittest
from .test_owner_eur_checkpoint import fixture,START,DAY
from .owner_pav1_market_time import registered,select,add_funding_prefixes,REPLAY,download,seal_checkpoint,restore_checkpoint

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

    def test_archive_download_creates_nested_parent_before_archive_helper(self):
        p,_=registered();previous=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            def fetch(artifact,run,digest,destination):
                self.assertTrue(destination.parent.is_dir())
                destination.mkdir()
                if destination.name=='original-causal':
                    (destination/'economic-lifecycle.json').write_text(json.dumps(dict(Study='MONETARY_CAUSAL_LIFECYCLE_1')))
            try:
                os.chdir(tmp)
                with patch('research.owner_pav1_market_time.prior.registered',return_value=({},'')), \
                     patch('research.owner_pav1_market_time.prior.download'), \
                     patch('research.owner_pav1_market_time.archive.download_archive',side_effect=fetch) as called:
                    download(p)
                self.assertEqual(called.call_count,3+len(p['ExtensionArtifacts']))
            finally:os.chdir(previous)

    def test_preparation_failure_does_not_create_a_false_source_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            seal_checkpoint(root/'missing-work',root/'checkpoint')
            self.assertFalse((root/'checkpoint').exists())

    def test_fast_source_checkpoint_roundtrips_exact_source_and_binary_tapes(self):
        import hashlib
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from .custody import unseal_new
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);work=root/'work';work.mkdir();(work/'verified-protection').mkdir()
            files={'source.json':b'{"AuthoritativeSource":"SYNTHETIC"}', 'pav-market-protocol.json':b'{}',
                   'verified-protection/test.ticks':bytes(range(256))*4}
            for name,raw in files.items():(work/name).write_bytes(raw)
            with patch.dict(os.environ,GITHUB_RUN_ID='1'),patch('research.owner_pav1_market_time.custody_new.checked_public',return_value=public):
                seal_checkpoint(work,root/'checkpoint')
            expected=hashlib.sha256(files['source.json']).hexdigest()
            restore_checkpoint(root/'checkpoint',root/'restored',private,'1',expected)
            for name,raw in files.items():self.assertEqual((root/'restored'/name).read_bytes(),raw)
            receipt=json.loads((root/'checkpoint/checkpoint-receipt.json').read_bytes())
            self.assertEqual(receipt['SourceSha256'],hashlib.sha256(files['source.json']).hexdigest())
            self.assertTrue(receipt['Complete'])
            before=list((root/'checkpoint').glob('part-*.sealed'))
            with patch.dict(os.environ,GITHUB_RUN_ID='1'),patch('research.owner_pav1_market_time.custody_new.checked_public',return_value=public):
                seal_checkpoint(work,root/'checkpoint')
            self.assertEqual(before,list((root/'checkpoint').glob('part-*.sealed')))
            part=next((root/'checkpoint').glob('part-*.sealed'));part.write_bytes(part.read_bytes()+b'X')
            with self.assertRaises(Exception):restore_checkpoint(root/'checkpoint',root/'corrupt',private,'1',expected)

    def test_current_recipient_is_isolated_from_legacy_input_recipient(self):
        import hashlib
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from .custody_new import emit_public
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        previous=Path.cwd()
        with tempfile.TemporaryDirectory() as tmp:
            try:
                os.chdir(tmp);work=Path('work');work.mkdir();(work/'source.json').write_bytes(b'{}')
                emit_public(private,Path('new-recipient-output'),'1')
                emit_public(private,Path('current-checkpoint-recipient'),'2')
                with patch.dict(os.environ,GITHUB_RUN_ID='2'):seal_checkpoint(work,Path('checkpoint'))
                restore_checkpoint(Path('checkpoint'),Path('restored'),private,'2',hashlib.sha256(b'{}').hexdigest())
                self.assertEqual((Path('restored/source.json')).read_bytes(),b'{}')
            finally:os.chdir(previous)

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

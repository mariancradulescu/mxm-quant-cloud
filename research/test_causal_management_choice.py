import copy,hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from .owner_causal_management_choice import apply_overlay,variants,STUDY
from .verified_research_cache import seal_files
from .owner_pav1_market_time import restore_checkpoint
from .test_owner_eur_checkpoint import fixture,START,DAY
from .owner_competitive_families import REPLAY
from .merge_eur_scenarios import exact_json

class CausalManagementChecks(unittest.TestCase):
    def rows(self):
        return [dict(Target=dict(Symbol='AAPL.US',Side='BID',At=at),Witness=dict(
            Status='AUTHENTIC_LATEST_PREFIX',SearchThrough=at,SearchFrom=at-345600000,
            At=at-1000,Price='200',PrefixNewestFirst=True,LeadingTimestampComplete=True))
            for at in (1793656800000,1794434400000)]

    def source(self):return dict(Tapes=[dict(Name='AAPL.US',FundingQuotes=[])])

    def test_overlay_adds_only_missing_marks_and_rejects_future_or_replacement(self):
        source=self.source();rows=self.rows();apply_overlay(source,rows)
        self.assertEqual([q['LatestBidPrefix'] for q in source['Tapes'][0]['FundingQuotes']],[r['Witness'] for r in rows])
        with self.assertRaises(Exception):apply_overlay(source,rows)
        future=self.rows();future[0]['Witness']['At']=future[0]['Target']['At']+1
        with self.assertRaises(Exception):apply_overlay(self.source(),future)
        existing=self.source();existing['Tapes'][0]['FundingQuotes']=[dict(At=rows[0]['Target']['At'],Bid='100',
            BidAt=rows[0]['Target']['At'],RequestedCoverage=True)]
        with self.assertRaises(Exception):apply_overlay(existing,rows)
        stale=self.source();stale['Tapes'][0]['FundingQuotes']=[dict(At=rows[0]['Target']['At'],Bid='100',
            BidAt=rows[0]['Target']['At']-7200001,RequestedCoverage=True)]
        apply_overlay(stale,rows)
        self.assertEqual(stale['Tapes'][0]['FundingQuotes'][0]['Bid'],'100')

    def test_generic_source_cache_restores_exact_bytes_and_detects_tampering(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        private=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        public=key.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);files={'source.json':b'{"Synthetic":true}', 'pav-market-protocol.json':b'{}',
                'verified-protection/test.ticks':bytes(range(256))}
            inputs=[]
            for name,raw in files.items():
                path=root/'input'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);inputs.append((path,name))
            expected=hashlib.sha256(files['source.json']).hexdigest()
            seal_files(inputs,root/'cache',public,'1','SYNTHETIC',expected)
            restore_checkpoint(root/'cache',root/'restored',private,'1',expected,source_only=True)
            for name,raw in files.items():self.assertEqual((root/'restored'/name).read_bytes(),raw)
            part=next((root/'cache').glob('part-*.sealed'));part.write_bytes(part.read_bytes()+b'X')
            with self.assertRaises(Exception):restore_checkpoint(root/'cache',root/'bad',private,'1',expected)

    def test_new_native_common_book_uses_four_books_and_strictly_matured_fits(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work);source=json.loads((work/'source.json').read_bytes())
            original=copy.deepcopy(source['Markets'][0]);tape=source['Tapes'][0]
            names=[f'SYNTH_{i:02}' for i in range(29)];source['Markets']=[];source['Tapes']=[]
            source.update(End=START+3*DAY,ExtendedEconomicContext=True)
            for name in names:
                row=copy.deepcopy(original);row['Market']['Name']=name
                row['Market']['Contract']['Symbol']=name;row['Market']['DatedDevelopment']['Contract']['Symbol']=name
                row['ScheduledClocks']=[t for t in row['ScheduledClocks'] if t<source['End']+7*DAY]
                source['Markets'].append(row);source['Tapes'].append(dict(tape,Name=name))
            (work/'source.json').write_text(json.dumps(source))
            plan=dict(Study=STUDY,Exposure='PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT',Start=START,
                SelectionFrom=START+DAY,EvaluationFrom=START+2*DAY,End=START+3*DAY,
                Stresses=[0,.5,1],Variants=variants(),OriginalInstruments=names[:21],
                SourceProtocolSha256=source['ProtocolSha256'],EvidenceManifestSha256=source['EvidenceManifestSha256'])
            (work/'plan.json').write_text(exact_json(plan))
            subprocess.run(['dotnet',REPLAY,'--owner-causal-management',str(work/'plan.json'),str(work/'source.json'),
                str(work/'result'),str(work/'verified-protection'),'0'],check=True,stdout=subprocess.DEVNULL)
            result=json.loads((work/'result/result.json').read_bytes())
            self.assertEqual((result['SharedPortfolioEvaluations'],result['Orders'],result['CloudActivated']),(4,0,False))
            self.assertEqual(len(result['ObserverReceipts']),2)
            for fit in result['Fits']:self.assertLess(fit['ObservationThrough'],fit['AvailableBefore'])
            self.assertTrue(any(fit['Id']=='JOINT_CAUSAL_MANAGEMENT' for fit in result['Fits']))
            for book in result['CommonBooks']:
                self.assertEqual(book['Result']['InitialCapitalEur'],300)
                if book['Id']=='CASH_MARKET_TIME':self.assertEqual(book['Result']['Closed'],0)

if __name__=='__main__':unittest.main()

import json,subprocess,tempfile,unittest
from pathlib import Path
from .owner_breadth57_causal_ridge import check,normalized_quotes

class Breadth57(unittest.TestCase):
    def test_registration_and_quotes(self):
        self.assertEqual(len(check()['Universe']),57)
        q=dict(At=100000,BidAt=99999,AskAt=99999,Bid='1.2',Ask='1.3')
        self.assertEqual(len(normalized_quotes([q,q])[0]),1)
        self.assertEqual(normalized_quotes([q,dict(q,Bid='1.1')]),([],1))
        self.assertEqual(normalized_quotes([dict(q,BidAt=100001)]),([],0))
    def test_empty_native_is_explicit_cash(self):
        p=check()
        with tempfile.TemporaryDirectory() as d:
            src,out=Path(d)/'source.json',Path(d)/'out.json'
            src.write_text(json.dumps([dict(Symbol=s,AssetClass=None,Bars={k:[] for k in ('M5','M15','H1')},Quotes=[]) for s in p['Universe']]))
            subprocess.run(['dotnet','run','--project','src/Mxm.PathResearch','-c','Release','--no-build','--','--breadth57-ridge',str(src),str(out)],check=True)
            r=json.loads(out.read_text())
            self.assertEqual(r['Labels'],0)
            self.assertTrue(all(x['Method']=='CASH' for x in r['Choices']))
            self.assertFalse(r['PortfolioEvaluated'])
if __name__=='__main__':unittest.main()

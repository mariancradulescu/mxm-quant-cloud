import json,subprocess,tempfile,unittest
from pathlib import Path
class PeerCausality(unittest.TestCase):
 def test_future_truncation_does_not_change_the_same_closed_peer_context(self):
  start=1761955200000
  def bars(hours,multiplier):
   return {tf:[[start+i*w,start+(i+1)*w,10000000+multiplier*i,10001000+multiplier*i,9999000+multiplier*i,10000050+multiplier*i,100]
     for i in range(hours*3600000//w)] for tf,w in [('M5',300000),('M15',900000),('H1',3600000)]}
  with tempfile.TemporaryDirectory() as root:
   results=[]
   for truncate in (False,True):
    source=Path(root)/('input'+str(truncate)+'.json');out=Path(root)/('result'+str(truncate)+'.json')
    source.write_text(json.dumps([dict(Symbol='SYNTHETIC_'+str(i),AssetClass='SYNTHETIC',Bars=bars(4 if truncate and i==4 else 5,10+i)) for i in range(5)]))
    subprocess.run(['dotnet','src/Mxm.PathResearch/bin/Release/net8.0/Mxm.PathResearch.dll','--distribution-causal',str(source),str(out)],check=True,capture_output=True)
    results.append(json.loads(out.read_bytes()))
   full,truncated=results
   self.assertGreater(full['Labels'],truncated['Labels'])
   self.assertEqual(full['FirstPeerContextAt'],truncated['FirstPeerContextAt'])
   self.assertEqual(full['FirstPeerContext'],truncated['FirstPeerContext'])
   self.assertEqual(len(truncated['FirstPeerContext']),5)
   self.assertIsNotNone(truncated['FirstPeerContext'][0]['Features'][8])
   self.assertTrue(truncated['PeerMembershipUsesClosedContextsOnly'])
   self.assertEqual(truncated['SelectionMultiplicity'],6)
if __name__=='__main__':unittest.main()

import hashlib,json,subprocess,tempfile,unittest
from pathlib import Path
from .owner_distribution_path import normalized_arrays
class NativeInputContract(unittest.TestCase):
 def test_quarantined_source_arrays_are_consumed_by_native_annual_driver(self):
  start=1761955200000;bars={}
  for tf,width in [('M5',300000),('M15',900000),('H1',3600000)]:
   raw=[[start+i*width,start+(i+1)*width,10000000,10000100,9999900,10000050,100] for i in range(4)]
   normalized,_=normalized_arrays(raw);self.assertEqual(raw,normalized);bars[tf]=normalized
  with tempfile.TemporaryDirectory() as root:
   source=Path(root)/'source.json';out=Path(root)/'result.json'
   source.write_text(json.dumps([dict(Symbol='SYNTHETIC_'+str(i),AssetClass='SYNTHETIC',Bars=bars) for i in range(5)]))
   subprocess.run(['dotnet','src/Mxm.PathResearch/bin/Release/net8.0/Mxm.PathResearch.dll','--distribution',str(source),str(out)],check=True,capture_output=True)
   result=json.loads(out.read_bytes());self.assertEqual(result['SourceSha256'],hashlib.sha256(source.read_bytes()).hexdigest())
   self.assertEqual(result['Labels'],0);self.assertFalse(result['PortfolioEvaluated']);self.assertEqual(result['Orders'],0)
if __name__=='__main__':unittest.main()

"""Exact serialization and shard quarantine must survive bounded restoration."""
import io,tempfile,tracemalloc,unittest
from decimal import Decimal
from pathlib import Path
from .bounded_exact_json import write,write_arrays
from .merge_eur_scenarios import exact_json,read
from .owner_estate_recovery import merge_series,merge_series_parts
from .owner_estate_staged_recovery import check,market_rows
class BoundedEstate(unittest.TestCase):
 def test_decimal_bytes_and_single_pass_arrays_match_original(self):
  value={'unicode':'Șelimbăr','Markets':[{'n':Decimal('1.00'),'v':[True,None,1e-20]}],
   'Tapes':[{'Name':'x','Quotes':[]}],'end':Decimal('1E-20')}
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'x.json';write(path,value)
   self.assertEqual(path.read_text(),exact_json(value)+'\n')
   write_arrays(path,dict(value,Markets=[],Tapes=[]),dict(Markets=iter(value['Markets']),Tapes=iter(value['Tapes'])))
   self.assertEqual(path.read_text(),exact_json(value)+'\n')
 def test_peak_writer_allocation_is_bounded(self):
  rows=[dict(OpenAt=i,Open=Decimal('1.000001'),High=Decimal('2.0'),Low=Decimal('.5'),Close=Decimal('1.2')) for i in range(40000)]
  with tempfile.TemporaryDirectory() as d:
   tracemalloc.start();write(Path(d)/'large.json',dict(Bars=rows));_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
   self.assertLess(peak,2_000_000)
   self.assertEqual(read(Path(d)/'large.json')['Bars'],rows)
 def test_conflict_cannot_reappear_in_a_later_shard(self):
  bar=dict(OpenAt=0,CloseAt=60000,Open='1',High='2',Low='1',Close='2',TickVolume=3)
  shards=[[bar],[dict(bar,Close='1.9')],[bar]]
  rows,q=merge_series_parts(iter(shards));self.assertEqual(rows,[]);self.assertEqual(q['ConflictingOpens'],1)
  self.assertEqual((rows,q),merge_series(*shards))
 def test_staged_registration_retains_original_policies(self):
  p=check();self.assertEqual(len(p['Fragments']),10);self.assertFalse(p['EconomicPolicyChanged'])
if __name__=='__main__':unittest.main()

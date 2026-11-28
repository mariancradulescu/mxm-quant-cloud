"""Exact serialization and shard quarantine must survive bounded restoration."""
import io,tempfile,tracemalloc,unittest,hashlib,json,zipfile,os
from unittest.mock import patch
from decimal import Decimal
from pathlib import Path
from .bounded_exact_json import write,write_arrays
from .merge_eur_scenarios import exact_json,read
from .owner_estate_recovery import merge_series,merge_series_parts
from .owner_estate_staged_recovery import check,market_rows,restore_artifact,resume_fragments,pinned_fragments
from .owner_earlier_lifecycle_digest_recovery import normalized_run_id,verified_download
from . import owner_earlier_lifecycle_digest_recovery as downloader
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
 def test_run_id_normalizes_int_and_string_and_rejects_invalid(self):
  self.assertEqual(normalized_run_id(46150207165),normalized_run_id('46150207165'))
  for value in (True,False,0,-1,1.0,'',' 1','01','1.0','-1','１',None):
   with self.subTest(value=value),self.assertRaisesRegex(Exception,'EARLIER_RECOVERY_RUN_ID'):
    normalized_run_id(value)
 def test_verified_download_checks_run_and_archive(self):
  stream=io.BytesIO()
  with zipfile.ZipFile(stream,'w') as z:z.writestr('receipt.json','{}')
  payload=stream.getvalue();digest=hashlib.sha256(payload).hexdigest()
  def download(args,stdout,check):stdout.write(payload)
  for expected,actual,good in [(12,12,True),('12',12,True),(12,'12',True),('12',13,False)]:
   with self.subTest(expected=expected,actual=actual),tempfile.TemporaryDirectory() as d:
    destination=Path(d)/'output'
    record=dict(id=34,workflow_run=dict(id=actual),expired=False,digest='sha256:'+digest)
    inventory=json.dumps([dict(artifacts=[record])]).encode()
    with patch.dict(os.environ,{'GITHUB_REPOSITORY':'owner/repo'}),patch.object(downloader.subprocess,'check_output',return_value=inventory),patch.object(downloader.subprocess,'run',side_effect=download) as request:
     if good:
      verified_download(34,expected,digest,destination);self.assertEqual((destination/'receipt.json').read_text(),'{}')
     else:
      with self.assertRaisesRegex(Exception,'EARLIER_RECOVERY_RUN_ID'):verified_download(34,expected,digest,destination)
      request.assert_not_called();self.assertFalse(destination.exists())
 def test_resume_pins_origin_not_current_run(self):
  p=resume_fragments();spec=p['Fragments']['base']['sealed']
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,{'GITHUB_RUN_ID':'999','R3_CUSTODY_PRIVATE_KEY_PEM':'fixture'}):
   dest=Path(d)/'base'
   module='research.owner_estate_staged_recovery.'
   with patch(module+'verified_download') as download,patch(module+'read',return_value={'RunId':str(p['OriginRun']),'SourceSha256':'fixture'}),patch(module+'restore_checkpoint') as restore:
    restore_artifact(spec,dest)
    self.assertEqual(download.call_args.args[1],str(p['OriginRun']))
    self.assertEqual(restore.call_args.args[3],str(p['OriginRun']))
   with patch(module+'artifacts',return_value=[s for x in p['Fragments'].values() for s in x.values()]):
    self.assertEqual(pinned_fragments(),p['Fragments'])
   with patch(module+'artifacts',return_value=[]):
    with self.assertRaisesRegex(Exception,'STAGED_RESUME_PIN_MISMATCH'):pinned_fragments()
if __name__=='__main__':unittest.main()

import os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from . import owner_held_equity_readback as module
from .merge_eur_scenarios import exact_json
class DownloadParents(unittest.TestCase):
 def test_nested_plan_download_and_source_only_reuse(self):
  names=['held-recovery-plan-earlier','held-recovery-plan-recent','held-recovery-protected']
  run=45973360072;artifacts=[dict(id=i+1,name=n,workflow_run=dict(id=run),expired=False,digest='sha256:abc') for i,n in enumerate(names)]
  def download(artifact,run,sha,destination):
   self.assertTrue(destination.parent.is_dir());destination.mkdir()
   if destination.name!='held-recovery-protected':(destination/(destination.name+'.json')).write_text('{}')
  previous=Path.cwd()
  with tempfile.TemporaryDirectory() as root:
   try:
    os.chdir(root)
    def verify(*args,**kw):
     self.assertTrue(kw['sources_only']);module.recovery.REPORT.mkdir()
    with patch.object(module,'api',return_value=dict(head_sha='f4dfb9afe4ce07d4d95d9f665e504adc3329325d',head_branch='main')),patch.object(module.subprocess,'check_output',return_value=exact_json([dict(artifacts=artifacts)]).encode()),patch.object(module,'verified_download',side_effect=download),patch.object(module.recovery,'verify',side_effect=verify),patch.dict(os.environ,{'GITHUB_REPOSITORY':'mariancradulescu/mxm-quant-cloud','GITHUB_RUN_ID':'test','GITHUB_SHA':'test'}),patch.object(module,'check',return_value=dict(OriginalCaptureRun=run,OriginalCaptureHead='f4dfb9afe4ce07d4d95d9f665e504adc3329325d',Study='OWNER_HELD_EQUITY_READBACK_1')):
     module.execute(None,None,sources_only=True)
    self.assertTrue((module.recovery.PLAN/'held-recovery-plan-earlier.json').is_file())
    self.assertTrue((module.recovery.REPORT/'readback-provenance.json').is_file())
   finally:os.chdir(previous)
if __name__=='__main__':unittest.main()

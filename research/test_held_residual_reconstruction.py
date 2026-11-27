import tempfile,unittest
from pathlib import Path
from .owner_held_residual_check import residual_demands
from .merge_eur_scenarios import exact_json
from .verified_research_cache import sha
from .guard import CaptureContractError
class HeldResidualReconstruction(unittest.TestCase):
 def fixture(self,root,wrong=False):
  original=root/'original';prior=root/'prior';original.mkdir();prior.mkdir()
  book=dict(Id='CASE',Result=dict(CashEur=300,EventChainHash='a'*64),Details=dict(
   Admissions=[dict(PositionId='A',Symbol='X',FillAt=10),dict(PositionId='B',Symbol='Y',FillAt=20),dict(PositionId='PENDING',Symbol='Z',FillAt=None)],
   Episodes=[dict(PositionId='A',CloseAt=30),dict(PositionId='B',CloseAt=40)],
   EquityPath=[dict(At=5,Held=0,EquityEur=300),dict(At=10,Held=1,EquityEur=None),
    dict(At=20,Held=1 if wrong else 2,EquityEur=None),dict(At=30,Held=1,EquityEur=None),dict(At=40,Held=0,EquityEur=300)]))
  for s in range(3):
   path=original/f'S{s}-result.json';path.write_text(exact_json(dict(CommonBooks=[book] if s==0 else [])))
  baseline=dict(Id='CASE',OriginalReportSha256=sha(original/'S0-result.json'),CashEur=300,EventChainHash='a'*64,
   Orders=0,OriginalPoliciesReplayed=0,Changes=[dict(At=10)],UnknownAfter=2)
  (prior/'recent-NET_HORIZON-S0-CASE.json').write_text(exact_json(baseline))
  return original,prior
 def test_filled_positions_only_and_exact_close_boundary(self):
  with tempfile.TemporaryDirectory() as path:
   original,prior=self.fixture(Path(path));rows,books,points=residual_demands({'NET_HORIZON':original},prior,'recent')
   self.assertEqual([(r['Symbol'],r['At']) for r in rows],[('X',20),('Y',20),('Y',30)])
   self.assertEqual((books,points),(1,2))
 def test_held_count_disagreement_refuses_inferred_recovery_targets(self):
  with tempfile.TemporaryDirectory() as path:
   original,prior=self.fixture(Path(path),True)
   with self.assertRaises(CaptureContractError):residual_demands({'NET_HORIZON':original},prior,'recent')
if __name__=='__main__':unittest.main()

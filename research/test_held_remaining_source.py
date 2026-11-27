import unittest
from .owner_held_remaining_source import pending_targets
class MinimalRecoveryPlan(unittest.TestCase):
 def row(self,group,lo,hi,missing,side='BID',mode='OPEN_INTERVAL'):
  return dict(Group=group,Symbol='X',Side=side,Mode=mode,From=lo,Through=hi,Complete=not missing,AuthenticAbsence=False,MissingWindows=missing)
 def test_other_complete_groups_and_prefixes_are_not_recollected(self):
  coverage={'Rows':[self.row(0,100,200,[[100,200]]),self.row(1,150,180,[])]}
  prefix=dict(Symbol='X',Side='BID',Witness=dict(At=145,SearchThrough=190))
  rows=pending_targets(coverage,[prefix]);self.assertEqual([(r['From'],r['Through']) for r in rows],[(100,144),(191,200)])
 def test_quote_sides_remain_distinct(self):
  coverage={'Rows':[self.row(0,100,200,[[100,200]])]}
  rows=pending_targets(coverage,[dict(Symbol='X',Side='ASK',Witness=dict(At=100,SearchThrough=200))]);self.assertEqual(len(rows),1)
 def test_existing_latest_prefix_satisfies_a_closed_session_target(self):
  coverage={'Rows':[self.row(0,0,400,[[0,400]],mode='CLOSED_PREFIX')]}
  rows=pending_targets(coverage,[dict(Symbol='X',Side='BID',Witness=dict(At=390,SearchThrough=500))]);self.assertEqual(rows,[])
if __name__=='__main__':unittest.main()

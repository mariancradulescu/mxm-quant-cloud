"""JFC1 broker source geometry and causal quote tests; NO original broker."""
import json
import unittest
from pathlib import Path
from datetime import datetime,timezone
from .cma2_cost_preflight import asof_spread

class FrozenJpn225SourceTests(unittest.TestCase):
    def test_frozen_exact_requests(self):
        p=json.loads(Path("research/jfc1_exact_jpn_source_protocol.json").read_text())
        self.assertEqual(p["id"],"JFC1")
        self.assertEqual(p["universe"],["JPN225"])
        self.assertEqual(p["expectedReadOnlySourceRequests"],11)
        self.assertEqual(p["quoteClocksUtcMillis"],
             [int(datetime.fromisoformat(s.replace("Z","+00:00")).timestamp()*1000)
              for s in p["quoteClocksUtc"]])
        self.assertEqual(len(set(p["quoteClocksUtcMillis"])),3)
        self.assertTrue(all(t<int(datetime(2026,11,18,20,0,
                      tzinfo=timezone.utc).timestamp()*1000)
                      for t in p["quoteClocksUtcMillis"]))
        self.assertEqual(p["originalPepperstoneBrokerOrders"],0)
    def test_paired_asof_no_future_no_stale(self):
        t=1700000000000
        yes=asof_spread([(t-1000,1000000),(t+100,999900)],
                       [(t-500,1000200)],t,10000,5000)
        self.assertEqual(yes["status"],"CAUSAL_PAIRED_SPREAD_OBSERVED")
        no=asof_spread([(t-15000,1000000)],[(t-500,1000200)],t,10000,5000)
        self.assertEqual(no["spreadBps"],None)
        partial=asof_spread([(t-1000,1000000)],[(t-500,1000200)],t,
                           10000,5000,complete=False)
        self.assertEqual(partial["status"],"PAGINATION_TRUNCATED")

if __name__=="__main__": unittest.main()

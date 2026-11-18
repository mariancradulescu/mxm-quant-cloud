"""No-market-data XMH2 original source protocol geometry checks."""
import json
import unittest
from pathlib import Path
from datetime import datetime,timezone
from .hxc1_historical_source import planned_requests


class Xmh2SourceTests(unittest.TestCase):
    def test_fixed_all_1644_requests(self):
        x=json.loads(Path("research/xmh2_complete_earlier_m15_source_protocol.json")
                     .read_text())
        req=planned_requests(x)
        self.assertEqual(x["id"],"XMH2_COMPLETE_EARLIER_M15_NEW_AUTHENTIC_SOURCE")
        self.assertEqual(len(req),1644)
        self.assertEqual(len(set(req)),1644)
        self.assertEqual(len({s for s,p,_,_ in req}),12)
        self.assertTrue(all(p=="M15" and
            0<(last-first)<=48*3600000 for _,p,first,last in req))
        left=int(datetime(2025,11,16,tzinfo=timezone.utc).timestamp()*1000)
        right=int(datetime(2026,8,17,tzinfo=timezone.utc).timestamp()*1000)
        self.assertEqual(min(q[2] for q in req),left)
        self.assertEqual(max(q[3] for q in req),right)
        self.assertTrue(all(q[2]>=left and q[3]<=right for q in req))


if __name__=="__main__":
    unittest.main()

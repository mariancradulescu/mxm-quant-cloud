"""Price-outcome-blind XMH1 fixed-geometry control, NOT broker research."""
import json
import unittest
from pathlib import Path
from datetime import datetime,timezone
from .hxc1_historical_source import planned_requests

P=Path("research/xmh1_m15_probe_source_protocol.json")


class SourceFrozenProbeTests(unittest.TestCase):
    def test_fixed_new_source_windows(self):
        plan=json.loads(P.read_text())
        requests=planned_requests(plan)
        self.assertEqual(plan["id"],"XMH1_CUMULATIVE_M15_OLD_SOURCE_PROBE")
        self.assertEqual(len(requests),36)
        self.assertEqual(len(set(requests)),36)
        self.assertEqual(len({(s,p) for s,p,_,_ in requests}),12)
        self.assertTrue(all(p=="M15" and end-first==48*3600*1000
            for _,p,first,end in requests))
        self.assertTrue(all(end<=int(datetime(2026,8,17,tzinfo=timezone.utc).timestamp()*1000)
            for _,_,first,end in requests))
        self.assertFalse(any("2026-08-17" in x["fromUtc"]
            for x in plan["ranges"]))


if __name__=="__main__":
    unittest.main()

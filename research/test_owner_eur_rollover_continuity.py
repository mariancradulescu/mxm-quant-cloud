import unittest

from . import owner_eur_rollover_continuity as rollover
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e


class RolloverEvidenceTests(unittest.TestCase):
    def test_split_inclusive_windows_without_overlap(self):
        calls=[]
        def request(q):
            lo,hi=q.fromTimestamp,q.toTimestamp
            calls.append((lo,hi))
            r=m.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=hi-lo>1)
            if hi-lo<=1:
                r.tickData.add(timestamp=hi,tick=123456)
            return r,100,rollover.src.ATTEMPTED
        rows,leaves=rollover.tick_window(request,7,9,e.BID,10,13,[10])
        self.assertEqual(calls,[(10,13),(10,11),(12,13)])
        self.assertEqual(rows,[[11,123456],[13,123456]])
        report=rollover.describe(rows,leaves,12)
        self.assertTrue(report["complete"])
        self.assertEqual(report["lastAtOrBefore"],11)
        self.assertEqual(report["firstAfter"],13)
        self.assertTrue(report["fresh30s"])

    def test_truncated_single_ms_and_budget_are_not_complete(self):
        def request(q):
            return m.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=True),100,rollover.src.ATTEMPTED
        rows,leaves=rollover.tick_window(request,7,9,e.ASK,10,10,[1])
        self.assertEqual(leaves[0][2],"TRUNCATED_SINGLE_MILLISECOND")
        self.assertFalse(rollover.describe(rows,leaves,10)["complete"])
        rows,leaves=rollover.tick_window(request,7,9,e.ASK,10,13,[1])
        self.assertFalse(rollover.describe(rows,leaves,12)["complete"])
        self.assertEqual([p[2] for p in leaves],["PENDING_BUDGET","PENDING_BUDGET"])

    def test_empty_verified_page_is_not_a_quote(self):
        def request(q):
            return m.ProtoOAGetTickDataRes(ctidTraderAccountId=7,hasMore=False),100,rollover.src.ATTEMPTED
        rows,leaves=rollover.tick_window(request,7,9,e.BID,10,13,[1])
        report=rollover.describe(rows,leaves,12)
        self.assertTrue(report["complete"])
        self.assertFalse(report["fresh30s"])
        self.assertIsNone(report["lastAtOrBefore"])

    def test_wrong_account_is_not_verified(self):
        def request(q):
            return m.ProtoOAGetTickDataRes(ctidTraderAccountId=8,hasMore=False),100,rollover.src.ATTEMPTED
        rows,leaves=rollover.tick_window(request,7,9,e.BID,10,13,[1])
        self.assertFalse(rollover.describe(rows,leaves,12)["complete"])


if __name__=="__main__":
    unittest.main()

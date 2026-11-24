import unittest
from . import source_history_universe as s
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_transport import encode_envelope
from .guard import CaptureContractError, require_read_only_request

class FakeSocket:
    def __init__(self):
        self.sent=[]
    def sendall(self,data):
        self.sent.append(data)

class SourceHistoryUniverseChecks(unittest.TestCase):
    def test_exact_bounded_deal_permission_only_on_new_transport(self):
        q=m.ProtoOADealListReq(ctidTraderAccountId=123,fromTimestamp=s.START,
                              toTimestamp=s.START+s.WEEK-1,maxRows=1000)
        s.bounded_deal(q,123)
        with self.assertRaises(CaptureContractError):
            require_read_only_request(q)
        t=s.SourceHistoryTransport()
        t.bound=123
        t._sock=FakeSocket()
        t._send_bytes(encode_envelope(q))
        self.assertEqual(len(t._sock.sent),1)
        for bad in (m.ProtoOADealListReq(ctidTraderAccountId=124,fromTimestamp=s.START,toTimestamp=s.START,maxRows=1),
                    m.ProtoOADealListReq(ctidTraderAccountId=123,fromTimestamp=s.START,toTimestamp=s.START+s.WEEK,maxRows=1),
                    m.ProtoOADealListReq(ctidTraderAccountId=123,fromTimestamp=s.START,toTimestamp=s.START,maxRows=1001)):
            with self.assertRaises(CaptureContractError):
                t._send_bytes(encode_envelope(bad))
        with self.assertRaises(CaptureContractError):
            t.request(m.ProtoOANewOrderReq())
        self.assertEqual(len(t._sock.sent),1)

    def test_weekly_pages_and_splits_cover_exact_interval(self):
        windows=s.deal_windows()
        self.assertEqual(windows[0][0],s.START)
        self.assertEqual(windows[-1][1],s.END-1)
        self.assertEqual(sum(b-a+1 for a,b in windows),s.END-s.START)
        self.assertTrue(all(a[1]+1==b[0] for a,b in zip(windows,windows[1:])))
        self.assertEqual(s.split_window(1,4),[(1,2),(3,4)])
        self.assertEqual(s.split_window(1,1),[])

    def test_tranche_is_category_diverse_not_symbol_whitelist(self):
        roster={5:dict(visible=True,category=1),1:dict(visible=True,category=1),
                9:dict(visible=True,category=2),2:dict(visible=False,category=2),
                77:dict(visible=True,category=None)}
        self.assertEqual(s.selected_ids(roster,3),[77,1,9])
        self.assertEqual(set(s.selected_ids(roster,20)),{1,5,9,77})
        self.assertEqual(len(roster),5)

    def test_readback_keeps_missing_distinct_from_not_requested(self):
        q=m.ProtoOADealListReq(ctidTraderAccountId=123,fromTimestamp=s.START,toTimestamp=s.START,maxRows=1)
        rec=dict(reqType=type(q).__name__,req=s.encode(q),requestAt=1,availableAt=2,res=None)
        j=s.ReadbackJournal([rec])
        self.assertEqual(j.query(q),(None,2,s.NO_RESPONSE))
        self.assertEqual(j.query(q),(None,None,s.UNCOLLECTED))
        self.assertEqual(j.index,1)
        self.assertNotEqual(s.ATTEMPTED,s.UNCOLLECTED)

if __name__=="__main__":
    unittest.main()

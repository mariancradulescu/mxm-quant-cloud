import unittest
from .owner_eer1_source import schedule,selection,covered,START,STEP,DAY
class EerSourceChecks(unittest.TestCase):
    def test_focused_stop_reuses_original_request_journal(self):
        from unittest.mock import patch
        from . import source_history_universe as src
        from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
        from .owner_eer1_stop_source import ROOT_SPAN, focused_ticks
        from .guard import CaptureContractError

        fill = START + 60_000
        with patch.object(src, "original_account", return_value=True):
            packets = []
            for side, price in ((e.BID,320000),(e.ASK,320100)):
                req = m.ProtoOAGetTickDataReq(ctidTraderAccountId=1,symbolId=7,type=side,
                                              fromTimestamp=START,toTimestamp=START+ROOT_SPAN-1)
                res = m.ProtoOAGetTickDataRes(ctidTraderAccountId=1,hasMore=False)
                res.tickData.add(timestamp=fill,tick=price)
                packets.append(dict(reqType=type(req).__name__,req=src.encode(req),
                                    resType=type(res).__name__,res=src.encode(res),
                                    requestAt=fill+300_000,availableAt=fill+301_000))
            self.assertEqual(focused_ticks({"id":7,"packets":packets},fill,fill+60_000),
                             {e.BID:[[fill,320000]],e.ASK:[[fill,320100]]})
            with self.assertRaisesRegex(CaptureContractError,"EER1_STOP_CUSTODY_WINDOW_INCOMPLETE"):
                focused_ticks({"id":7,"packets":packets[:1]},fill,fill+60_000)

    def test_calendar(self):
        x={"scheduleTimeZone":"UTC","schedule":[{"startSecond":86400,"endSecond":6*86400}]}
        c=schedule(x,START,START+7*DAY)
        self.assertIn(START+15000,c);self.assertNotIn(START+5*DAY+15000,c)
        self.assertIsNone(schedule({},START,START+DAY))
    def test_coverage(self):
        self.assertTrue(covered([[0,4,"VERIFIED_COMPLETE_PAGE",1,1],[5,9,"PROVIDER_NO_QUOTES",1,0]],0,9))
        self.assertFalse(covered([[0,4,"VERIFIED_COMPLETE_PAGE",1,1],[6,9,"VERIFIED_COMPLETE_PAGE",1,1]],0,9))

    def test_multiday_capture_readback_request_identity(self):
        from unittest.mock import patch
        from . import owner_eer1_source as eer
        from . import source_history_universe as src
        from .ctrader_proto import OpenApiMessages_pb2 as m
        from .guard import CaptureContractError
        # Actual Journal and ReadbackJournal; synthetic complete empty tick pages
        # trigger the old side-label shadowing branch even without a price.
        class Transport:
            connected=True
            def request(self,q):
                self.last=q
                return m.ProtoOAGetTickDataRes(ctidTraderAccountId=q.ctidTraderAccountId,hasMore=False)
        account=1
        charges=[22*60]
        for name in ("EURUSD","GBPUSD","BTCUSD"):
            with self.subTest(symbol=name), patch.object(eer,"END",eer.START+3*eer.DAY), patch.object(src.time,"sleep"):
                live=src.Journal(Transport(),account)
                capture=eer.collect_market(live,account,7,{},False,charges,False,name)
                replay=src.ReadbackJournal(live.packets)
                reconstructed=eer.collect_market(replay,account,7,{},False,charges,True,name)
                self.assertEqual(capture[0],reconstructed[0])
                self.assertEqual(replay.index,len(live.packets))
                self.assertEqual(len(reconstructed[3]),3)
                self.assertTrue(all(q["RequestedCoverage"] for q in reconstructed[3]))
                self.assertEqual(len(live.packets),6 if name in eer.PRIOR_FULL else 36)
                # Exact identity, not a permissive decoder.
                altered=[dict(p) for p in live.packets]
                altered[1]["req"]=altered[0]["req"]
                with self.assertRaisesRegex(CaptureContractError,"HISTORY_READBACK_REQUEST_OR_CLOCK"):
                    eer.collect_market(src.ReadbackJournal(altered),account,7,{},False,charges,True,name)

    def test_reused_rollover_boundary_and_new_days(self):
        from unittest.mock import patch
        from . import owner_eer1_source as eer
        from . import source_history_universe as src
        from .ctrader_proto import OpenApiMessages_pb2 as m
        class Transport:
            connected=True
            def request(self,q):
                return m.ProtoOAGetTickDataRes(ctidTraderAccountId=q.ctidTraderAccountId,hasMore=False)
        with patch.object(eer,"START",eer.PRIOR_ROLL_START-eer.DAY), patch.object(eer,"END",eer.integrated.END+eer.DAY), patch.object(src.time,"sleep"):
            capture=src.Journal(Transport(),1)
            original=eer.collect_market(capture,1,7,{},False,[1320],False,"EURUSD")
            j=src.ReadbackJournal(capture.packets)
            reconstructed=eer.collect_market(j,1,7,{},False,[1320],True,"EURUSD")
            self.assertEqual(original[0],reconstructed[0])
            self.assertEqual(j.index,len(capture.packets))
            self.assertEqual(len(capture.packets),14)

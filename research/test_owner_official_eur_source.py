import unittest
import json
from datetime import date, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from . import owner_eur_gap_evidence as gaps
from . import owner_official_eur_source as o
from .ctrader_proto import OpenApiMessages_pb2 as m


class OfficialEurSourceChecks(unittest.TestCase):
    def test_gap_matrix_preserves_originals_and_counts_real_overlap(self):
        minute = o.MINUTE
        start = 86_400_000
        width = {p: n*minute for p,n in o.source.PERIODS.items()}
        bar_series = {p:o.observed_bar_span(p,{start-width[p],start,start+width[p]}) for p in width}
        market_a = dict(symbol="A",timeframes=dict(bar_series,M1=None),warmup={})
        market_b = dict(symbol="B",timeframes=bar_series,warmup={})
        with TemporaryDirectory() as folder:
            src = Path(folder)/"original.json"
            src.write_text(json.dumps(dict(matrix=[market_a,market_b])))
            filled = o.observed_bar_span("M1",{start,start+minute})
            with patch.object(gaps.dated,"MATRIX",src):
                merged = gaps.integrate_coverage({"A":{"M1":filled}},start,start+2*minute,"fixture")
                self.assertEqual(merged["addedClosedBarsByTimeframe"],{"M1":2})
                self.assertEqual(merged["overlapSummary"]["marketsWithSevenTimeframesInWindow"],2)
                self.assertEqual(merged["simultaneousSevenTimeframePriceMinutesAtLeastTwoMarkets"],2)
                self.assertEqual(merged["matrix"][1]["registeredWindow"]["previousClosedBars"]["D1"],1)
                self.assertIsNone(json.loads(src.read_text())["matrix"][0]["timeframes"]["M1"])
                with self.assertRaisesRegex(Exception,"EUR_GAP_MATRIX_DUPLICATE_CELL"):
                    gaps.integrate_coverage({"B":{"M1":filled}},start,start+2*minute,"fixture")

    def test_last_wire_guard_intercepts_only_account_bound_reads(self):
        transport=o.OfficialEvidenceTransport()
        transport.bound=314
        transport.watch_ids={512}
        good=m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=314,symbolId=[512],
            subscribeToSpotTimestamp=True)
        with patch.object(o.StdlibCTraderTransport,"_send_bytes") as send:
            frame=o.encode_envelope(good)
            transport._send_bytes(frame)
            send.assert_called_once_with(transport,frame)
            for invalid in (
                m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=88,symbolId=[512],subscribeToSpotTimestamp=True),
                m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=314,symbolId=[999],subscribeToSpotTimestamp=True),
                m.ProtoOASubscribeSpotsReq(ctidTraderAccountId=314,symbolId=[512]),
                m.ProtoOANewOrderReq(ctidTraderAccountId=314,symbolId=512,orderType=1,tradeSide=1,volume=100)
            ):
                with self.assertRaises(Exception):
                    transport._send_bytes(o.encode_envelope(invalid))
            self.assertEqual(send.call_count,1)

    def test_contract_window_checks_relevant_holiday_and_session(self):
        at=int(datetime(2026,11,24,15,0,tzinfo=timezone.utc).timestamp()*1000)
        holiday_day=(date(2021,11,24)-date(1970,1,1)).days
        calendar=dict(scheduleTimeZone="UTC",schedule=[dict(startSecond=0,endSecond=604800)],
            holiday=[dict(scheduleTimeZone="UTC",holidayDate=holiday_day,isRecurring=False)])
        self.assertEqual(o.next_scheduled_witness(calendar,at),at+o.STEP)
        calendar["holiday"][0]["isRecurring"]=True
        self.assertIsNone(o.next_scheduled_witness(calendar,at))
        calendar["holiday"][0].update(startSecond=16*3600,endSecond=17*3600)
        self.assertEqual(o.next_scheduled_witness(calendar,at),at+o.STEP)
        calendar["schedule"][0]["endSecond"]=2*86400+15*3600+120
        self.assertIsNone(o.next_scheduled_witness(calendar,at))

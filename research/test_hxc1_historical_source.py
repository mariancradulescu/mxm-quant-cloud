"""HXC1 source-only protocol tests. No credentials, endpoints or market fixtures."""
import copy
import json
import unittest

from .decode import need
from .guard import CaptureContractError, require_read_only_request
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .hxc1_historical_source import (PROTOCOL, PERIOD_MINUTES, planned_requests,
                                     decode_response, stamp)


class Hxc1SourceContract(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads(PROTOCOL.read_text())

    def test_original_frozen_geometry_and_request_limit(self):
        requests = planned_requests(self.plan)
        self.assertEqual(len(requests), 1444)
        self.assertEqual(len(set(requests)), len(requests))
        self.assertLessEqual(len(requests), self.plan["maximumMarketDataRequests"])
        counts = {}
        grouped = {}
        for symbol, period, left, right in requests:
            self.assertLess(left, right)
            step = PERIOD_MINUTES[period] * 60000
            self.assertEqual(left % step, 0)
            self.assertEqual(right % step, 0)
            counts[period] = counts.get(period, 0) + 1
            grouped.setdefault((symbol, period), []).append((left, right))
        self.assertEqual(counts, {"H1": 444, "M15": 552, "M1": 448})
        for stream in grouped.values():
            self.assertTrue(all(stream[i][1] == stream[i+1][0]
                                for i in range(len(stream)-1)))

    def test_no_unbounded_request_expansion(self):
        p = copy.deepcopy(self.plan)
        p["maximumMarketDataRequests"] = 40
        with self.assertRaises(CaptureContractError):
            planned_requests(p)

    def test_timezones_and_alignment_fail_closed(self):
        with self.assertRaises(CaptureContractError):
            stamp("2026-11-16T00:00:00+02:00")
        p = copy.deepcopy(self.plan)
        p["ranges"][0]["fromUtc"] = "2025-11-16T00:05:00Z"
        with self.assertRaises(CaptureContractError):
            planned_requests(p)

    def test_source_only_protobuf_allowlist(self):
        good = m.ProtoOAGetTrendbarsReq(
            ctidTraderAccountId=1, symbolId=1, period=e.M15,
            fromTimestamp=100000, toTimestamp=200000)
        require_read_only_request(good)
        bad = m.ProtoOANewOrderReq()
        with self.assertRaises(CaptureContractError):
            require_read_only_request(bad)

    def test_incomplete_broker_pages_cannot_be_silently_scored(self):
        response = m.ProtoOAGetTrendbarsRes(ctidTraderAccountId=1, period=e.M15)
        with self.assertRaises(CaptureContractError):
            decode_response(response, 0, 900000, 15)
        response.hasMore = True
        with self.assertRaises(CaptureContractError):
            decode_response(response, 0, 900000, 15)
        response.hasMore = False
        self.assertEqual(decode_response(response, 0, 900000, 15), [])

    def test_original_bar_time_and_future_censoring(self):
        response = m.ProtoOAGetTrendbarsRes(ctidTraderAccountId=1, period=e.M5,
                                             hasMore=False)
        bar = response.trendbar.add()
        bar.utcTimestampInMinutes = 5
        bar.low = 100000
        bar.deltaOpen = 4
        bar.deltaHigh = 10
        bar.deltaClose = 6
        bar.volume = 23
        self.assertEqual(decode_response(response, 0, 600000, 5),
                         [[300000, 600000, 100004, 100010, 100000, 100006, 23]])
        self.assertEqual(decode_response(response, 0, 300000, 5), [])


if __name__ == "__main__":
    unittest.main()

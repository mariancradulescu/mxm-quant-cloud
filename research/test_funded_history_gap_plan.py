"""Offline tests: gap deduplication, bound checks and original-response retention."""
import json
import unittest
from unittest.mock import Mock

from . import funded_history_gap_plan as p
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .guard import CaptureContractError
from .integrated_market_source import FUNDED_HISTORY


class GapPlanTests(unittest.TestCase):
    def setUp(self):
        self.start = FUNDED_HISTORY.start
        self.row = {"Market": "NAS100", "Timeframe": "TICKS", "Side": "ASK",
                    "From": self.start, "ToExclusive": self.start + 3_600_000,
                    "Reason": "PROVIDER_ERROR", "ProviderCode": "UNKNOWN_ERROR"}
        self.plan = {"OriginalRun": "44824462289", "Status": "PREPARED_NOT_AUTHORIZED_FOR_BROKER_ACCESS",
                     "NewOpenApiRequests": 0, "Requests": [self.row]}

    def test_gap_has_no_duplicates_and_cannot_recollect_complete_side(self):
        query, blocked = p.validate_plan(self.plan)
        self.assertEqual(query, [self.row])
        self.assertEqual(blocked, [])
        self.plan["Requests"].append(dict(self.row))
        with self.assertRaisesRegex(CaptureContractError, "RECOVERY_GAP_DUPLICATE"):
            p.validate_plan(self.plan)
        self.plan["Requests"][1]["ToExclusive"] -= 1
        with self.assertRaisesRegex(CaptureContractError, "RECOVERY_GAP_OVERLAP"):
            p.validate_plan(self.plan)

    def test_abnormal_market_grid_or_unverified_activity_is_blocked(self):
        self.plan["Requests"][0]["ToExclusive"] = FUNDED_HISTORY.end + 1
        with self.assertRaisesRegex(CaptureContractError, "RECOVERY_GAP_TICK_BOUNDS"):
            p.validate_plan(self.plan)
        self.plan["Requests"] = [{
            "Market": "NAS100", "Timeframe": "TICKS", "Side": "BID_ASK",
            "From": FUNDED_HISTORY.start, "ToExclusive": FUNDED_HISTORY.end,
            "Reason": "BAR_ACTIVITY_UNVERIFIED"}]
        runnable, blocked = p.validate_plan(self.plan)
        self.assertEqual(runnable, [])
        self.assertEqual(len(blocked), 1)

    def test_bounded_retry_keeps_original_unknown_error_and_success(self):
        req = m.ProtoOAGetTickDataReq(ctidTraderAccountId=61, symbolId=37,
            type=e.ASK, fromTimestamp=self.start, toTimestamp=self.start+1000)
        answers = iter([
            m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="UNKNOWN_ERROR"),
            m.ProtoOAGetTickDataRes(ctidTraderAccountId=61, hasMore=False)])
        retained, pauses = [], []
        result = p.bounded_read_only_request(req, lambda _: next(answers),
                    retained.append, authorized=True, sleep=pauses.append)
        self.assertIsInstance(result, m.ProtoOAGetTickDataRes)
        self.assertEqual(len(retained), 2)
        self.assertEqual(retained[0]["OriginalPacket"][2], "ProtoOAErrorRes")
        self.assertGreaterEqual(pauses[0], 0.25)

    def test_no_authorization_and_no_quotes_behaviour(self):
        req = m.ProtoOAGetTickDataReq(ctidTraderAccountId=61, symbolId=37,
            type=e.BID, fromTimestamp=self.start, toTimestamp=self.start+1000)
        send = Mock(return_value=m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="NO_QUOTES"))
        with self.assertRaisesRegex(CaptureContractError, "RECOVERY_NEW_OPEN_API_NOT_AUTHORIZED"):
            p.bounded_read_only_request(req, send, lambda _: None)
        send.assert_not_called()
        retained = []
        result = p.bounded_read_only_request(req, send, retained.append, authorized=True)
        self.assertEqual(result.errorCode, "NO_QUOTES")
        self.assertEqual(len(retained), 1)

    def test_provider_error_is_never_relabelled_no_quotes(self):
        req = m.ProtoOAGetTickDataReq(ctidTraderAccountId=61, symbolId=37,
            type=e.BID, fromTimestamp=self.start, toTimestamp=self.start+1000)
        retained = []
        with self.assertRaisesRegex(CaptureContractError, "RECOVERY_PROVIDER_REQUEST_REJECTED"):
            p.bounded_read_only_request(req,
                lambda _: m.ProtoOAErrorRes(ctidTraderAccountId=61, errorCode="UNKNOWN_ERROR"),
                retained.append, authorized=True, sleep=lambda _: None)
        self.assertEqual(len(retained), 3)
        self.assertTrue(all(r["OriginalPacket"][2] == "ProtoOAErrorRes" for r in retained))


if __name__ == "__main__":
    unittest.main()

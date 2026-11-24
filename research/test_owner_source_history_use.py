import unittest

from .ctrader_proto import OpenApiMessages_pb2 as messages, OpenApiModelMessages_pb2 as models
from .owner_source_history_use import calculation_type, fields_of, inspect_bars


class OriginalSourceUseChecks(unittest.TestCase):
    def test_has_field_distinguishes_default_zero_and_unknown_wire_enum(self):
        contract = models.ProtoOASymbol(symbolId=1, digits=3, pipPosition=2)
        self.assertEqual(calculation_type(contract), ("ABSENT_ON_WIRE", None, []))
        contract.swapCalculationType = models.PIPS
        self.assertEqual(calculation_type(contract), ("PIPS", 0, []))
        self.assertEqual(fields_of(contract)["swapCalculationType"], 0)
        contract.ClearField("swapCalculationType")
        # Field 29, wire type 0. An unrecognized enum is retained as unknown.
        contract.MergeFromString(bytes([0xe8, 0x01, 0x09]))
        self.assertEqual(calculation_type(contract), ("UNKNOWN_WIRE_ENUM", None, [9]))

    def request(self):
        return messages.ProtoOAGetTrendbarsReq(ctidTraderAccountId=1, symbolId=3, period=models.H4,
            fromTimestamp=600 * 60_000, toTimestamp=1_320 * 60_000 - 1)

    def reply(self, *minutes):
        reply = messages.ProtoOAGetTrendbarsRes(ctidTraderAccountId=1, symbolId=3,
            period=models.H4, timestamp=0, hasMore=False)
        for minute in minutes:
            reply.trendbar.add(utcTimestampInMinutes=minute, volume=5, low=100000,
                deltaOpen=5, deltaHigh=11, deltaClose=10)
        return reply

    def test_window_keeps_offsets_and_drops_adjacent_or_unclosed_bars(self):
        request = self.request()
        diagnostic, rows = inspect_bars(request, self.reply(480, 720, 960, 1_200), 1_600 * 60_000)
        self.assertEqual(diagnostic["status"], "CLOSED_ROWS_VERIFIED")
        self.assertEqual(diagnostic["exclusions"], {"ADJACENT_BEFORE": 1, "CLOSE_AFTER_CUTOFF": 1})
        self.assertEqual([r[0] // 60_000 for r in rows], [720, 960])
        self.assertEqual(diagnostic["nominalOffsetMinutes"], {"0": 4})

    def test_distinguishes_empty_page_incomplete_page_missing_fields_and_bad_geometry(self):
        request = self.request()
        receipt, rows = inspect_bars(request, self.reply(), 1_600 * 60_000)
        self.assertEqual(receipt["status"], "EXPECTED_RESPONSE_WITH_EMPTY_SERIES")
        self.assertFalse(rows)
        reply = self.reply(720, 960)
        reply.hasMore = True
        reply.trendbar[0].ClearField("deltaOpen")
        reply.trendbar[1].deltaClose = 99
        receipt, rows = inspect_bars(request, reply, 1_600 * 60_000)
        self.assertFalse(rows)
        self.assertEqual(receipt["reasons"], {"BAR_FIELDS_MISSING": 1, "BAR_GEOMETRY": 1, "PAGINATION_HAS_MORE": 1})

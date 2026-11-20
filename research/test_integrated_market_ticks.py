"""Synthetic original-packet fixtures for full-session source integrity."""
import gzip
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from . import integrated_market_readback as readback
from . import integrated_market_source as source
from .ctrader_proto import OpenApiMessages_pb2 as m
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .guard import CaptureContractError

ACCOUNT = 61
SYMBOL = 37


def tick_packet(side, first, last, more=False, stamps=(), code=None):
    request = m.ProtoOAGetTickDataReq(ctidTraderAccountId=ACCOUNT, symbolId=SYMBOL, type=side,
                                    fromTimestamp=first, toTimestamp=last)
    if code:
        response = m.ProtoOAErrorRes(ctidTraderAccountId=ACCOUNT, errorCode=code)
    else:
        response = m.ProtoOAGetTickDataRes(ctidTraderAccountId=ACCOUNT, hasMore=more)
        prior_stamp = 0
        for stamp in reversed(stamps):
            response.tickData.add(timestamp=stamp-prior_stamp, tick=10_000_000 if not prior_stamp else 0)
            prior_stamp = stamp
    return source.pack(request, response)


class TickPaginationTests(unittest.TestCase):
    def test_terminal_partition_with_different_bid_and_ask_shapes(self):
        raw = [
            tick_packet(e.BID, 100, 107, True, [107]),
            tick_packet(e.BID, 100, 103, True, [103]),
            tick_packet(e.BID, 100, 101, stamps=[101]),
            tick_packet(e.BID, 102, 103, code="NO_QUOTES"),
            tick_packet(e.BID, 104, 107, stamps=[104, 107]),
            tick_packet(e.ASK, 100, 107, stamps=[100, 107]),
            tick_packet(e.BID, 110, 111), tick_packet(e.ASK, 110, 111, code="NO_QUOTES"),
        ]
        sides, stats = readback.reconcile_tick_pages(raw, ACCOUNT, SYMBOL, [(100, 107), (110, 111)])
        self.assertEqual([row[0] for row in sides[e.BID]], [101, 104, 107])
        self.assertEqual([row[0] for row in sides[e.ASK]], [100, 107])
        self.assertEqual(stats["Bid"], dict(Requests=6, TruncatedParents=2, TerminalPages=4, NoQuotesPages=1,
            EmptyTerminalPages=1, TerminalMilliseconds=10, NoQuotesMilliseconds=2))
        self.assertEqual(stats["Ask"]["TerminalMilliseconds"], 10)
        self.assertEqual(stats["Ask"]["TruncatedParents"], 0)
        self.assertTrue(source.unpack(raw[0])[1].hasMore)

    def test_collector_archives_parent_and_children_in_readback_order(self):
        raw = []

        def reply(request):
            first, last, side = request.fromTimestamp, request.toTimestamp, request.type
            row = tick_packet(side, first, last, more=last-first >= 2, stamps=[last])
            raw.append(row)
            return source.unpack(row)[1]

        for side in (e.BID, e.ASK):
            self.assertEqual(source.collect_tick_window(ACCOUNT, SYMBOL, side, 100, 107, reply), 4)
        self.assertEqual(len(raw), 14)
        _, stats = readback.reconcile_tick_pages(raw, ACCOUNT, SYMBOL, [(100, 107)])
        self.assertEqual(stats["Ask"]["TruncatedParents"], 3)
        self.assertEqual(stats["Ask"]["TerminalPages"], 4)

    def test_missing_child_and_missing_quote_side_fail_with_exact_interval(self):
        parent = tick_packet(e.BID, 100, 103, more=True)
        left = tick_packet(e.BID, 100, 101)
        right = tick_packet(e.BID, 102, 103)
        for rows, side, first in [([parent, left], "BID", 102), ([parent, left, right], "ASK", 100)]:
            with self.subTest(side=side), self.assertRaisesRegex(
                    readback.TickPageIntegrityError, "INTEGRATED_TICK_PAGE_MISSING") as caught:
                readback.reconcile_tick_pages(rows, ACCOUNT, SYMBOL, [(100, 103)])
            self.assertEqual(caught.exception.context, {"Side": side, "From": first, "To": 103})

    def test_overlap_extra_page_and_unexpected_provider_error_fail(self):
        wrong_partition = [
            tick_packet(e.BID, 100, 103, more=True), tick_packet(e.BID, 100, 102),
            tick_packet(e.BID, 102, 103), tick_packet(e.ASK, 100, 103),
        ]
        with self.assertRaisesRegex(CaptureContractError, "INTEGRATED_TICK_PAGE_ORDER_OR_INTERVAL"):
            readback.reconcile_tick_pages(wrong_partition, ACCOUNT, SYMBOL, [(100, 103)])
        complete = [tick_packet(e.BID, 100, 103), tick_packet(e.ASK, 100, 103)]
        with self.assertRaisesRegex(CaptureContractError, "INTEGRATED_TICK_UNEXPECTED_EXTRA_PAGE"):
            readback.reconcile_tick_pages(complete + complete[:1], ACCOUNT, SYMBOL, [(100, 103)])
        rejected = [tick_packet(e.BID, 100, 103, code="MARKET_DATA_ERROR")]
        with self.assertRaisesRegex(readback.TickPageIntegrityError, "INTEGRATED_TICK_SOURCE_ERROR") as caught:
            readback.reconcile_tick_pages(rejected, ACCOUNT, SYMBOL, [(100, 103)])
        self.assertEqual(caught.exception.context["ProviderCode"], "MARKET_DATA_ERROR")

    def test_unresolved_single_millisecond_is_not_terminal_evidence(self):
        raw = [tick_packet(e.BID, 102, 102, more=True, stamps=[102])]
        with self.assertRaisesRegex(CaptureContractError, "INTEGRATED_TICK_SAME_MS_SERVER_TRUNCATION"):
            readback.reconcile_tick_pages(raw, ACCOUNT, SYMBOL, [(102, 102)])
        with self.assertRaisesRegex(CaptureContractError, "INTEGRATED_TICK_SAME_MS_SERVER_TRUNCATION"):
            source.collect_tick_window(ACCOUNT, SYMBOL, e.BID, 102, 102, lambda _: source.unpack(raw[0])[1])


class SourceCollectionTests(unittest.TestCase):
    names = ("EXPENSIVE", "RESTRICTED", "DISABLED", "NO_VOLUME")
    base = source.FUNDED_HISTORY.start
    scope = replace(source.FUNDED_HISTORY, warmup=base, start=base, end=base+source.DAY,
                    universe=tuple(("FIXTURE", (name,)) for name in names))

    def api_response(self, request):
        if isinstance(request, m.ProtoOATraderReq):
            return m.ProtoOATraderRes(ctidTraderAccountId=ACCOUNT,
                trader=e.ProtoOATrader(ctidTraderAccountId=ACCOUNT, balance=0, depositAssetId=1, brokerName="Pepperstone"))
        if isinstance(request, m.ProtoOAAssetListReq):
            return m.ProtoOAAssetListRes(ctidTraderAccountId=ACCOUNT, asset=[
                e.ProtoOAAsset(assetId=i, name=name) for i, name in enumerate(("EUR", "USD", "JPY"), 1)])
        if isinstance(request, m.ProtoOASymbolsListReq):
            return m.ProtoOASymbolsListRes(ctidTraderAccountId=ACCOUNT, symbol=[
                e.ProtoOALightSymbol(symbolId=i, symbolName=name, enabled=name != "DISABLED",
                                     quoteAssetId=3 if name == "DISABLED" else 2)
                for i, name in enumerate(self.names, 1)])
        if isinstance(request, m.ProtoOASymbolByIdReq):
            i = request.symbolId[0]
            return m.ProtoOASymbolByIdRes(ctidTraderAccountId=ACCOUNT, symbol=[
                e.ProtoOASymbol(symbolId=i, digits=5, pipPosition=4, minVolume=0 if i == 4 else 100,
                                maxVolume=400, stepVolume=100, tradingMode=1 if i == 2 else 0)])
        if isinstance(request, m.ProtoOAExpectedMarginReq):
            if request.symbolId == 2:
                return m.ProtoOAErrorRes(ctidTraderAccountId=ACCOUNT, errorCode="SYMBOL_NOT_TRADABLE")
            return m.ProtoOAExpectedMarginRes(ctidTraderAccountId=ACCOUNT, moneyDigits=2, margin=[
                e.ProtoOAExpectedMargin(volume=v, buyMargin=40_000, sellMargin=40_000) for v in request.volume])
        if isinstance(request, m.ProtoOAGetTrendbarsReq):
            if request.symbolId == 4 and request.period != e.M1:
                return m.ProtoOAErrorRes(ctidTraderAccountId=ACCOUNT, errorCode="NO_QUOTES")
            return m.ProtoOAGetTrendbarsRes(ctidTraderAccountId=ACCOUNT, period=request.period, trendbar=[
                e.ProtoOATrendbar(volume=10, low=10_000_000, deltaOpen=0, deltaHigh=10, deltaClose=0,
                                  utcTimestampInMinutes=request.fromTimestamp//source.MINUTE)])
        if isinstance(request, m.ProtoOAGetTickDataReq):
            return m.ProtoOAGetTickDataRes(ctidTraderAccountId=ACCOUNT, hasMore=False, tickData=[
                e.ProtoOATickData(timestamp=request.fromTimestamp+15_000,
                                  tick=10_000_020 if request.type == e.ASK else 10_000_000)])
        raise AssertionError(type(request))

    def capture(self, directory, responders=None):
        cipher = Path(directory)/"cipher"
        public = Path(directory)/"public"
        with (patch.object(source, "CIPHER_DIR", cipher), patch.object(source, "PUBLIC_DIR", public),
              patch.object(source, "validate_environment"), patch.object(source, "checked_public"),
              patch.object(source, "authenticate", return_value=ACCOUNT),
              patch.object(source, "seal_new", side_effect=lambda data, *_: data),
              patch.object(source.time, "sleep"),
              patch.object(source, "StdlibCTraderTransport") as transport,
              patch.dict(source.os.environ, {"GITHUB_RUN_ID": "1234"})):
            transport.return_value.request.side_effect = responders or self.api_response
            source.collect(self.scope)
        return cipher, json.loads((public/"source.json").read_text())

    def test_all_market_data_retained_separately_from_current_funding(self):
        with tempfile.TemporaryDirectory() as directory:
            cipher, receipt = self.capture(directory)
            with (patch.object(readback, "CIPHER_DIR", cipher),
                  patch.object(readback, "unseal_new", side_effect=lambda data, *_: data)):
                rows = readback.readback(receipt, b"", interval=30_000, scope=self.scope)
            by_name = {m["Name"]: m for m in rows}
            self.assertEqual(set(by_name), set(self.names))
            for name, row in by_name.items():
                self.assertEqual(row["RequestedTickHours"], 1, name)
                self.assertEqual(len(row["Quotes"]), 2, name)
                self.assertEqual({q["BidAt"] for q in row["Quotes"]}, {self.base + 15_000})
                self.assertEqual(row["TickPages"]["Bid"]["TerminalPages"], 1)
            self.assertFalse(by_name["EXPENSIVE"]["Funding"]["MinimumMarginBelowEur300AtCapture"])
            self.assertIn("CURRENT_TRADING_MODE_RESTRICTED", by_name["RESTRICTED"]["Funding"]["Restrictions"])
            self.assertEqual(by_name["RESTRICTED"]["Funding"]["ExpectedMarginProviderCode"], "SYMBOL_NOT_TRADABLE")
            self.assertFalse(by_name["DISABLED"]["EnabledAtCapture"])
            self.assertEqual(by_name["DISABLED"]["Contract"]["QuoteAsset"], "JPY")
            self.assertEqual(by_name["NO_VOLUME"]["Funding"]["ExpectedMarginStatus"], "BROKER_VOLUME_GRID_UNAVAILABLE")
            self.assertEqual(by_name["NO_VOLUME"]["BarNoQuotesPages"]["M5"], 1)

    def test_failure_leaves_the_original_page_and_context_in_custody(self):
        def unsupported_ask(request):
            if isinstance(request, m.ProtoOAGetTickDataReq) and request.type == e.ASK:
                return m.ProtoOAErrorRes(ctidTraderAccountId=ACCOUNT, errorCode="HISTORICAL_PAGE_REJECTED")
            return self.api_response(request)

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SystemExit):
                self.capture(directory, unsupported_ask)
            receipt = json.loads((Path(directory)/"public/source.json").read_text())
            self.assertEqual(receipt["Status"], "SOURCE_FAILED_CLOSED")
            self.assertEqual(receipt["FailureAt"]["Side"], "ASK")
            self.assertEqual(receipt["FailureAt"]["ProviderCode"], "HISTORICAL_PAGE_REJECTED")
            name = f"EXPENSIVE-{self.base}-ticks.enc"
            self.assertIn(name, {shard["File"] for shard in receipt["Shards"]})
            saved = json.loads(gzip.decompress((Path(directory)/"cipher"/name).read_bytes()))
            self.assertEqual(source.unpack(saved["Raw"][-1])[1].errorCode, "HISTORICAL_PAGE_REJECTED")

    def test_registered_budget_allows_one_split_per_root_and_reserve(self):
        capacity = source.request_capacity(source.FUNDED_HISTORY)
        self.assertEqual(capacity["RequestsIfEveryRootSplitsOnce"], 54_875)
        self.assertGreaterEqual(capacity["RequestLimit"] - capacity["RequestsIfEveryRootSplitsOnce"], 9_000)
        self.assertLess(capacity["RequestLimit"] * (1534/5581) / 60, capacity["DeadlineMinutes"])

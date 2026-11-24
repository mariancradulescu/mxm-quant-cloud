import unittest

from . import owner_source_history_expand as extension
from .ctrader_proto import OpenApiMessages_pb2 as m


class HistoryExtensionChecks(unittest.TestCase):
    def test_excludes_covered_and_previously_attempted_symbols(self):
        def contract(sid, name, category):
            return dict(symbolId=sid, name=name, category=category, visible=True, tradingMode=0,
                        contractStatus=extension.source.VERIFIED, minVolume=100)
        base = dict(timeframeProbeIds=[1], contractRoster=[contract(1, "Tranche1", 1),
            contract(2, "P05", 1), contract(3, "EURUSD", 1), contract(4, "New1", 3),
            contract(5, "New2", 2), contract(6, "PreviouslyAttempted", 2)])
        self.assertEqual([row["symbolId"] for row in extension.plan(base, {"P05"}, [6])], [5, 4])

    def test_pages_reconcile_and_keep_a_closed_bar_across_query_boundary(self):
        first = extension.START
        class Journal:
            windows = []
            def query(self, q):
                self.windows.append((q.fromTimestamp, q.toTimestamp))
                reply = m.ProtoOAGetTrendbarsRes(ctidTraderAccountId=1, symbolId=2,
                    period=q.period, timestamp=0, hasMore=len(self.windows) == 1)
                if q.fromTimestamp == first and not reply.hasMore:
                    reply.trendbar.add(utcTimestampInMinutes=q.toTimestamp // 60_000,
                        volume=1, low=100000, deltaOpen=0, deltaHigh=20, deltaClose=10)
                return reply, extension.END + extension.source.DAY, extension.source.ATTEMPTED
        journal = Journal()
        bars, diagnostics = extension.timeframe(journal, 1, 2, "H4")
        self.assertEqual(len(journal.windows), 3)
        self.assertEqual(journal.windows[1][1] + 1, journal.windows[2][0])
        self.assertEqual(diagnostics["counts"], {"PAGINATION_SPLIT": 1, "CLOSED_ROWS_VERIFIED": 1,
                                                    "EXPECTED_RESPONSE_WITH_EMPTY_SERIES": 1})
        self.assertEqual(len(bars), 1)

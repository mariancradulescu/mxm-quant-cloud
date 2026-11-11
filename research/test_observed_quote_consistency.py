"""Prospective observed BID/ASK consistency; no broker calls or closed study replay."""
import unittest
from decimal import Decimal as D
from types import SimpleNamespace

from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .mef1 import latest
from .contract_eur_cost import IncompleteCostEvidence, attribute_costs
from .test_contract_eur_cost import contract


class LockedQuoteReadOnlyChecks(unittest.TestCase):
    STAMP = 1_800_000

    @staticmethod
    def quote(bid=100000, ask=100001, age_bid=20000, age_ask=20000,
              truncated=None, missing=None):
        calls = []
        def request(query, expected):
            calls.append(query)
            side = query.type
            price, age = (bid, age_bid) if side == e.BID else (ask, age_ask)
            rows = [] if side == missing else [
                SimpleNamespace(timestamp=LockedQuoteReadOnlyChecks.STAMP-age, tick=price)]
            return SimpleNamespace(hasMore=side == truncated, tickData=rows)
        return request, calls

    def test_locked_quote_is_observed_not_filled(self):
        request, calls = self.quote(bid=100000, ask=100000)
        pair = latest(request, 22, 35, self.STAMP)
        self.assertEqual(pair, [D("1"), D("1")])
        self.assertEqual(len(calls), 2)
        self.assertEqual([call.type for call in calls], [e.BID, e.ASK])
        self.assertTrue(all(
            call.ctidTraderAccountId == 22 and call.symbolId == 35
            and call.fromTimestamp == self.STAMP-20000
            and call.toTimestamp == self.STAMP for call in calls))

    def test_positive_spread_retained_and_crossed_rejected(self):
        request, _ = self.quote(bid=100000, ask=100005)
        self.assertEqual(latest(request, 22, 35, self.STAMP),
                         [D("1"), D("1.00005")])
        request, _ = self.quote(bid=100010, ask=100000)
        self.assertIsNone(latest(request, 22, 35, self.STAMP))

    def test_nonpositive_or_missing_side_fails_closed(self):
        for bid, ask in ((0, 100000), (-1, 100000)):
            with self.subTest(bid=bid):
                req, _ = self.quote(bid=bid, ask=ask)
                # Invalid raw cumulative protobuf tick must not be silently accepted.
                with self.assertRaises(Exception):
                    latest(req, 22, 35, self.STAMP)
        for side in (e.BID, e.ASK):
            req, _ = self.quote(missing=side)
            self.assertIsNone(latest(req, 22, 35, self.STAMP))
            req, _ = self.quote(truncated=side)
            self.assertIsNone(latest(req, 22, 35, self.STAMP))

    def test_age_boundary_and_future_side_fail_closed(self):
        req, _ = self.quote(age_bid=20000, age_ask=20000)
        self.assertEqual(latest(req, 22, 35, self.STAMP),
                         [D("1"), D("1.00001")])
        # Decoder fails closed on a payload containing a tick outside the requested window.
        req, _ = self.quote(age_bid=20001)
        with self.assertRaises(Exception):
            latest(req, 22, 35, self.STAMP)
        req, _ = self.quote(age_ask=-1)
        with self.assertRaises(Exception):
            latest(req, 22, 35, self.STAMP)

    def test_eur_cost_zero_spread_not_zero_total_cost_or_fill(self):
        symbol = contract(rate=0, minimum=100000000)
        a = attribute_costs(
            symbol, "USD", 1000, D("1"), D("1"),
            {"USD": D(".9")}, slippage_eur=D(".2"),
            financing_eur=D("0"), gross_realized_eur=D("5"))
        self.assertEqual(D(a["spreadObservedEur"]), D(0))
        self.assertEqual(D(a["additionalSpreadBookedEur"]), D(0))
        self.assertEqual(D(a["roundTripCurrentContractCommissionEur"]), D("1.8"))
        self.assertGreater(D(a["completeConditionalCostEur"]), D("1.8"))
        self.assertIsNone(a["fundedBrokerNetEur"])
        self.assertFalse(a["historicalTermsCertified"])
        with self.assertRaisesRegex(IncompleteCostEvidence, "INVALID_BID_ASK"):
            attribute_costs(symbol, "USD", 1000, D("1.00001"), D("1"),
                            {"USD": D(".9")})


if __name__ == "__main__":
    unittest.main()

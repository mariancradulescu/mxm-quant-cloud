"""No-network CSP1 causal BID/ASK spread and protocol regression."""
import unittest
from decimal import Decimal as D
from .csp1_cost_preflight import asof_spread,protocol

class Csp1Tests(unittest.TestCase):
    def test_fresh_asof_pair(self):
        r=asof_spread([[999,100000]],[[1000,100200]],1000,2000,2000)
        self.assertEqual(r["status"],"CAUSAL_PAIRED_SPREAD_OBSERVED")
        self.assertEqual(D(r["spreadBps"]),D("19.980020"))
    def test_future_quote_cannot_reprice_past(self):
        r=asof_spread([[999,100000],[1001,99000]],[[999,100100],[1001,99010]],
                     1000,2000,2000)
        self.assertEqual(r["status"],"CAUSAL_PAIRED_SPREAD_OBSERVED")
        self.assertGreater(D(r["spreadBps"]),D(0))
        self.assertEqual(r["ageBidMs"],1)
    def test_no_bid_is_unknown(self):
        self.assertEqual(asof_spread([],[[1000,101]],1000,2000,2000)["status"],
                         "QUOTE_SIDE_MISSING")
    def test_future_only_quote_is_missing(self):
        self.assertEqual(asof_spread([[1001,100]],[[1001,101]],1000,2000,2000)["status"],
                         "QUOTE_SIDE_MISSING")
    def test_stale_is_not_zero_spread(self):
        r=asof_spread([[10,100]],[[10,101]],5000,1000,1000)
        self.assertEqual(r["status"],"STALE_OR_ASYNCHRONOUS")
        self.assertIsNone(r["spreadBps"])
    def test_skew_is_not_valid(self):
        self.assertEqual(asof_spread([[900,100]],[[1000,101]],1000,2000,50)["status"],
                         "STALE_OR_ASYNCHRONOUS")
    def test_crossed_book_rejected(self):
        self.assertEqual(asof_spread([[1000,101]],[[1000,100]],1000,2000,100)["status"],
                         "CROSSED_OR_INVALID")
    def test_incomplete_page_blocks_price(self):
        self.assertEqual(asof_spread([[1000,100]],[[1000,110]],1000,2000,100,False)["status"],
                         "PAGINATION_TRUNCATED")
    def test_protocol_fixed_before_broker_requests(self):
        p=protocol()
        self.assertTrue(p["researchOnly"])
        self.assertEqual(p["id"],"CSP1")
        self.assertEqual(len(p["universe"]),12)
        self.assertEqual(len(p["observationUtcMillis"]),3)
        self.assertEqual(p["maxSourceRequests"],105)
        self.assertEqual(p["ordersSubmitted"],0)
        self.assertFalse(p["closedStudiesRescored"])
        self.assertEqual(p["inventorySourceRunId"],41939175379)
if __name__=="__main__":unittest.main()

"""CMA2 contract/cost preflight remains uns cored and independently bounded."""
import unittest
from .cma2_cost_preflight import protocol, asof_spread, need

class Cma2PreflightChecks(unittest.TestCase):
    def test_universe_is_outcome_blind_and_distinct(self):
        p=protocol()
        self.assertEqual(p["id"],"CMA2")
        self.assertEqual(p["universe"],["NatGas","JPYX","USDX","AMD.US"])
        self.assertEqual(p["expectedSourceRequests"],3+8*len(p["universe"]))
        self.assertEqual(len(p["observationUtcMillis"]),3)
        self.assertEqual(len(set(p["observationUtcMillis"])),3)
        self.assertFalse(p["noLiveDemoOrders"] is False)
        self.assertTrue(p["noClosedStudyRerun"])
    def test_causal_quotes_require_two_fresh_sides(self):
        self.assertEqual(asof_spread([(1000,10000)],[(1000,10002)],1001,2000,2000)["status"],
                         "CAUSAL_PAIRED_SPREAD_OBSERVED")
        self.assertEqual(asof_spread([(1000,10000)],[(1000,10002)],5000,2000,2000)["status"],
                         "STALE_OR_ASYNCHRONOUS")
        self.assertEqual(asof_spread([(1000,10000)],[],1000,2000,2000)["status"],
                         "QUOTE_SIDE_MISSING")
        self.assertEqual(asof_spread([(1000,10000)],[(1000,10002)],1000,2000,2000,complete=False)["status"],
                         "PAGINATION_TRUNCATED")
    def test_worse_side_not_marked_favorable(self):
        self.assertEqual(asof_spread([(1000,10004)],[(1000,10002)],1000,2000,2000)["status"],
                         "CROSSED_OR_INVALID")
    def test_margins_cannot_be_funding_certificates(self):
        p=protocol()
        self.assertEqual(p["ownerCapitalProspectiveEur"],300)
        self.assertTrue(p["hard21OnlySystemFinancedRoundTrips"])
        self.assertTrue(p["noOutcomeDataScoring"])

if __name__=="__main__":unittest.main()

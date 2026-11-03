"""No source prices in repository: only deterministic temporal contract tests."""
import math
import unittest
from .relative_gross import score, DAY, H4, PAIRS

END=1762200000000

def fixture():
    start=END-370*DAY
    bars=[]
    for k,s in enumerate(PAIRS):
        price=120000+k*9000
        for i in range(370*6):
            price=int(price*(1+0.00007*math.sin(i*.14+k*1.6)))
            price=max(price,100)
            bars.append({"symbol":s,"resolution":"H4","openTime":start+i*H4,
                         "availableTime":start+(i+1)*H4,"close":price})
    return {"schema":"mxm-econ-source-v2","readOnly":True,"captureEnd":END,"bars":bars}

class TestRelativeGross(unittest.TestCase):
    def test_causal_holdout_not_scored(self):
        tape=fixture()
        before=score(tape)
        cutoff=END-370*DAY+296*DAY
        for bar in tape["bars"]:
            if bar["openTime"]>cutoff:bar["close"]*=2
        after=score(tape)
        self.assertEqual(before,after)

    def test_no_broker_profit_claim_and_all_complete_weeks(self):
        report=score(fixture())
        self.assertTrue(report["final20PctNotScored"])
        self.assertIsNone(report["fundedEur200Net"])
        self.assertIsNone(report["fundedDrawdownPct"])
        self.assertFalse(report["realBrokerHard21"])
        self.assertEqual(report["ordersSubmitted"],0)
        self.assertGreaterEqual(report["eligibleFullWeeks"],8)
        self.assertEqual(report["plannedRoundTripLegsNOTExecuted"],2*report["completeGrossPairObservations"])

    def test_fail_closed_if_year_missing(self):
        tape=fixture()
        tape["bars"]=[x for x in tape["bars"] if x["symbol"]!="USDJPY"]
        with self.assertRaises(ValueError):score(tape)

if __name__=="__main__":
    unittest.main()

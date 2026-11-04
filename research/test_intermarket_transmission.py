"""Synthetic causal/coverage contract for IMT1; no authentic model scoring."""
import copy
import json
import math
import unittest
from pathlib import Path
from .intermarket_transmission import assess, complete_pair, costs_by_symbol

class IntermarketContract(unittest.TestCase):
    def source(self):
        p=json.loads(Path("research/intermarket_transmission_protocol.json").read_text())
        start=p["start"]
        bars={}
        for symbol in set(p["sourceIndices"])|set(p["targets"]):
            rows=[]
            for j in range(576):
                t=start+j*300000
                # Indices are consistently rising (>5bps for a complete hour).
                factor=(1.00017 if symbol in p["sourceIndices"] else 1.00001)
                c=100000*factor**j
                rows.append([t,t+300000,c,c,c,c,100])
            bars[symbol]=rows
        costs=[]
        for s in p["targets"]:
            for j in range(4):
                costs.append(dict(Symbol=s,SpreadBps=1+j*.1,CommissionBps=.5,
                                  PastVolBps=.2,CurrentMinimumMarginEur=30))
        return p,dict(bars=bars,costs=costs)

    def test_full_disclosure_no_funding_claim(self):
        p,data=self.source()
        output=assess(data,p)
        self.assertEqual(output["groupCount"],108)
        self.assertTrue(output["nativeFundedAllocationNotRun"])
        self.assertIsNone(output["fundedNetEur"])
        self.assertGreater(output["sourceGates"]["usableIndexBreadthClocks"],0)
        self.assertTrue(any(x["proposed"]>0 for x in output["groups"] if x["phase"]=="development"))

    def test_exact_missing_horizon_never_becomes_zero_return(self):
        p,data=self.source()
        s=p["targets"].keys().__iter__().__next__()
        data["bars"][s][100][5] *= 2
        rows={row[1]:row[5] for row in data["bars"][s]}
        t=data["bars"][s][60][1]
        self.assertIsNotNone(complete_pair(rows,t,60))
        del rows[t+300000]
        self.assertIsNone(complete_pair(rows,t,60))

    def test_broker_cost_scenarios_monotone(self):
        _,data=self.source()
        for c in costs_by_symbol(data["costs"]).values():
            self.assertGreater(c["adverseBps"],c["centralBps"])
            self.assertGreater(c["stressBps"],c["adverseBps"])

if __name__=="__main__":
    unittest.main()

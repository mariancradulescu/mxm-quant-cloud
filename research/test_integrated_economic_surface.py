"""Pure IES1 causal diagnostic checks; never an old predictive-study replay."""
import copy
import json
import math
import unittest
from pathlib import Path
from .integrated_economic_surface import _predictive_calibration,M5,HOUR,WEEK

class IntegratedEconomicSurfaceChecks(unittest.TestCase):
    def setUp(self):
        self.p=json.loads(Path("research/integrated_economic_surface_protocol.json").read_text())
    def test_immutable_exposed_calendar_and_source(self):
        p=self.p
        self.assertEqual(p["sourceWeeks"],52)
        self.assertEqual(p["originalSourceRunId"],41724643418)
        self.assertEqual(p["newBrokerRequests"],0)
        self.assertIn("USDJPY",p["sourceUniverse"])
        self.assertEqual(p["calendar"]["selectionEndUtcMs"]-p["calendar"]["developmentEndUtcMs"],13*WEEK)
    def test_only_complete_previous_hour_and_next_hour_label(self):
        start=self.p["calendar"]["startUtcMs"]
        t=start+2*HOUR
        rows=[]
        for offset in range(-13,12):
            at=t+offset*M5
            value=100000+50*(offset+13)
            rows.append([at,at+M5,value,value,value,value,1])
        b={"bars":{symbol:copy.deepcopy(rows) for symbol in self.p["sourceUniverse"]}}
        result=_predictive_calibration(b,self.p)
        x=result["EURUSD"]["phase"]["development"]
        self.assertEqual(x["completeCausalLabelPairs"],1)
        self.assertEqual(x["neutralChanceBrierBenchmark"],.25)
        self.assertEqual(x["meanDiagnosticBrier"],0)
        self.assertGreater(x["meanOneHourSignedGrossBps"],0)
        incomplete=copy.deepcopy(b)
        for symbol in self.p["sourceUniverse"]:
            incomplete["bars"][symbol]=[r for r in incomplete["bars"][symbol] if r[0]!=t+3*M5]
        y=_predictive_calibration(incomplete,self.p)
        self.assertEqual(y["EURUSD"]["phase"]["development"]["completeCausalLabelPairs"],0)
    def test_mutating_future_label_changes_score_but_not_previous_feature(self):
        start=self.p["calendar"]["startUtcMs"]
        t=start+2*HOUR
        def build(drop):
            rows=[]
            for offset in range(-13,12):
                at=t+offset*M5
                value=100000+50*(offset+13) if offset<0 else (
                    100000+50*12 + (offset+1)*( -250 if drop else 50))
                rows.append([at,at+M5,value,value,value,value,1])
            return {"bars":{symbol:copy.deepcopy(rows) for symbol in self.p["sourceUniverse"]}}
        up=_predictive_calibration(build(False),self.p)
        down=_predictive_calibration(build(True),self.p)
        self.assertEqual(up["EURUSD"]["phase"]["development"]["meanDiagnosticBrier"],0)
        self.assertEqual(down["EURUSD"]["phase"]["development"]["meanDiagnosticBrier"],1)
        self.assertFalse(up["EURUSD"]["phase"]["globallyExposedAudit"]["qualification"])
if __name__=="__main__":unittest.main()

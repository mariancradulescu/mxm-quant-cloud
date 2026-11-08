"""SFX1: ex-ante protocol, price scaling, causal feature and no-cost fabrication."""
import unittest,math
from .sfx1_economics import (JPY,NZD,python_decide,outcome_path,source_event_cost,
                             phase_summary,hac_lower)
from .sfx1_source import protocol,expected_requests,windows,quote_clocks

class Sfx1ResearchChecks(unittest.TestCase):
    def test_fixed_original_source_budget(self):
        p=protocol()
        self.assertEqual(p["id"],"SFX1")
        self.assertEqual(expected_requests(p),486)
        self.assertEqual(len(windows(p)),53)
        self.assertEqual(len(quote_clocks(p)),26)
        self.assertEqual(p["source"]["historicalWeeks"],52)
        self.assertEqual(p["source"]["newDaysChronologicallyAfterLastExposed"],5)

    def test_completed_jpy_h4_dispersion_and_momentum(self):
        t=1793780100000
        def bars(first,last):
            return [{"CloseAt":t-900000*(17-i),"Close":first+(last-first)*i/16,
                     "TickVolume":100} for i in range(17)]
        frame={"Mechanism":JPY,"Symbol":"EURJPY","Clock":t,
               "Target":bars(100,99.8),"PeerA":bars(100,100.3),
               "PeerB":bars(100,100.25)}
        x=python_decide(frame)
        self.assertEqual(x["Side"],1)
        self.assertEqual(x["MomentumBenchmarkSide"],-1)
        self.assertTrue(x["HistoryComplete"])

    def test_source_missing_does_not_forward_fill(self):
        marks={i*900000:(i*900000,0,0,0,100+i,100) for i in range(5)}
        self.assertEqual(outcome_path(marks,0,60),(100,104))
        del marks[2*900000]
        self.assertIsNone(outcome_path(marks,0,60))

    def test_current_tariff_is_not_synthetic_zero_fee(self):
        t=1793765701009
        sample=[(t-3*86400000,2.),(t-2*86400000,3.),(t-86400000,4.)]
        source={"EURUSD":{t:(t,0,0,0,110000,0)},
                "EURJPY":{t:(t,0,0,0,160000,0)},
                "AUDJPY":{t:(t,0,0,0,102000,0)}}
        terms={"EURUSD":{"digits":5},"EURJPY":{"digits":3},
               "AUDJPY":{"digits":3,"minimumUnits":"1000",
               "commissionType":2,"rateWire":300000000,
               "minimumWire":0,"pnlConversionBps":0,"lotSizeUnits":100000}}
        priced=source_event_cost("AUDJPY",t,source,{"AUDJPY":sample},terms,"central")
        self.assertIsNotNone(priced)
        self.assertEqual(priced["spreadBps"],3)
        self.assertGreater(priced["currentTermTwoSideCommissionBps"],0)
        self.assertFalse(priced["tariffHistoricallyCertified"])
        self.assertFalse(priced["executionFillCertified"])
        missing=source_event_cost("AUDJPY",t,source,{"AUDJPY":sample[:2]},terms,"central")
        self.assertIsNone(missing)
        missingroute={k:v for k,v in source.items() if k!="EURUSD"}
        self.assertIsNone(source_event_cost("AUDJPY",t,missingroute,{"AUDJPY":sample},terms,"central"))

    def test_sparse_cost_does_not_create_a_net_estimate(self):
        event={"week":0,"gross":2,"benchmarkGross":1,"incrementalGross":1,
               "central":None,"adverse":None,"benchmarkAdverse":None,
               "incrementalAdverse":None}
        x=phase_summary([event],0,13)
        self.assertEqual(x["modelSignals"],1)
        self.assertEqual(x["emptyWeeks"],12)
        self.assertIsNone(x["netAdverseMeanBpsConditional"])
        self.assertIsNone(x["adverseWeeklyHacBonferroniLower"])
        self.assertIsNone(hac_lower([1,2,3]))

if __name__=="__main__":unittest.main()

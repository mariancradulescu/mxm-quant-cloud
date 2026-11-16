"""HSD1 contract and isolation tests: technical fixtures only, never economics."""
import copy
import json
import math
import unittest
from .decode import need
from .guard import CaptureContractError
from .hsd1_structure_research import (
    PROTOCOL, HOUR, WEEK, frozen_plan, causal_events, price_route_eur,
    split_decision, weekly_gate, candidate_train_gate, exposed_multiresolution_paths)


class Hsd1Contract(unittest.TestCase):
    def setUp(self):
        self.p,self.sha,self.bounds=frozen_plan()

    def test_scope_and_pre_registration(self):
        self.assertEqual(len(self.p["universe"]),12)
        self.assertEqual(len(self.p["mechanisms"]),6)
        self.assertEqual(self.p["horizonsH"],[1,4])
        self.assertEqual(6*4*2,48)
        self.assertEqual(self.bounds[1]-self.bounds[0],26*WEEK)
        self.assertTrue(self.p["chronologicalSplit"]["noIndependentConfirmation"])

    def test_session_missing_bars_are_not_imputed(self):
        bars=[]
        for i in range(100):
            start=i*HOUR
            o=100000+i*10
            bars.append([start,start+HOUR,o,o+30,o-30,o+10,100+i])
        event,mo=causal_events(bars,50,self.p)
        # A later OHLCV bar cannot modify already-completed decision features.
        bars2=copy.deepcopy(bars)
        bars2[51][5]+=10000000
        self.assertEqual(causal_events(bars2,50,self.p),(event,mo))
        # Fifty existing historical bars with a session gap remain valid
        # observation history, no fabricated price is added.
        bars[40][0]-=2*HOUR
        bars[40][1]-=2*HOUR
        self.assertTrue(len(causal_events(bars,50,self.p))==2)

    def test_maturity_excludes_cross_phase_label(self):
        a=self.bounds
        self.assertEqual(split_decision(a[1]-HOUR,a[1]+HOUR,a)[0],"CROSS_PHASE")
        self.assertEqual(split_decision(a[1]+HOUR,a[1]+2*HOUR,a)[0],"SELECTION")

    def test_original_native_eur_vs_jpy_conversion(self):
        gross,floor=price_route_eur("EURUSD",1,110000,110100,{"EURUSD":110000},1000,0.06)
        self.assertAlmostEqual(gross,1000*(100/100000)/1.1)
        self.assertLess(floor,gross)
        jpygross,jpyfloor=price_route_eur("USDJPY",1,15000000,15010000,
                                {"EURUSD":110000},1000,0.06)
        self.assertAlmostEqual(jpygross,1000*(10000/100000)/150.1/1.1)
        self.assertLess(jpyfloor,jpygross)

    def test_no_retroactive_admission_with_zero_support(self):
        self.assertFalse(candidate_train_gate([],self.p))
        a=weekly_gate([],0,26,critical=3.30)
        self.assertEqual(a["lowerWeeklyEur"],0)
        self.assertEqual(a["weeksWithEvents"],0)

    def test_m15_m1_censored_unknown_is_not_a_zero_drawdown(self):
        example={
          "phase":"EXPOSED","family":"CHANNEL_BREAKOUT_BODY",
          "h":1,"symbol":"EURUSD","at":123*HOUR,
          "entryPriceRaw":110000,"side":1}
        out=exposed_multiresolution_paths({"bars":{}},[example],self.p)
        row=next(x for x in out["M15"] if x["family"]=="CHANNEL_BREAKOUT_BODY" and x["horizonHours"]==1)
        self.assertEqual(row["exposedSignalsWithForwardH1Label"],1)
        self.assertEqual(row["forwardMicroPathsComplete"],0)
        self.assertIsNone(row["meanMaxAdverseBps"])


if __name__=="__main__":
    unittest.main()

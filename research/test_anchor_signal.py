"""Causality and source-size invariant tests only, never trading evidence."""
import math, unittest
from datetime import datetime,timezone
from .anchor_signal import signals,Q,MODEL
from .tick_volume_net import eligible_weeks,DAY

END=int(datetime(2026,11,3,tzinfo=timezone.utc).timestamp()*1000)

def fixture():
    first=END-370*DAY
    price=110000;bars=[]
    for i in range(370*96):
        move=int(18*math.sin(i*.41)+11*math.cos(i*.16)+3*math.sin(i*.07))
        c=max(30000,price+move)
        bars.append({"t":first+i*Q,"o":price,"h":max(c,price)+12,
                    "l":min(c,price)-12,"c":c,
                    "v":72+i%17+int(5*(1+math.sin(i*.22)))})
        price=c
    return {"start":first,"end":END,"bars":bars}

class AnchoredCausality(unittest.TestCase):
    def test_last20_cannot_change_frozen_selection(self):
        b=fixture()
        before=signals(b)
        cut=b["start"]+296*DAY
        for row in b["bars"]:
            if row["t"]>cut:
                row["v"]*=9
                row["c"]=row["o"]
        after=signals(b)
        self.assertEqual(before,after)
        self.assertEqual(len(before["eligibleMondayUtcMs"]),10)
        self.assertGreater(before["trainingExamples"],450)
        self.assertGreater(before["selectionWindows"],130)

    def test_no_bar_close_future_needed_for_entry(self):
        b=fixture();x=signals(b)
        self.assertEqual(MODEL,"EURUSD_M15_SESSION_ANCHORED_TICK_BALANCE_V1")
        self.assertTrue(all(p["exit"]-p["signal"]==3*Q for p in x["plan"]))
        self.assertTrue(all(p["signal"]>=x["trainingCutMs"] and p["exit"]<x["selectionEndMs"] for p in x["plan"]))

if __name__=="__main__":unittest.main()

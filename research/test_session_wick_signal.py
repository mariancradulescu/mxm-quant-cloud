"""Separate wick-mechanism chronology tests; synthetic fixtures never profitability."""
import unittest
from .test_anchor_signal import fixture
from .session_wick_signal import signals,Q,MODEL
from .tick_volume_net import DAY

class M15WickCausality(unittest.TestCase):
    def test_holdout_mutation_never_changes_train_or_selection(self):
        b=fixture()
        first=signals(b)
        cut=b["start"]+296*DAY
        for x in b["bars"]:
            if x["t"]>=cut:x["h"]+=10000;x["v"]*=7
        second=signals(b)
        self.assertEqual(first,second)
        self.assertGreaterEqual(first["trainingExamples"],125)
        self.assertGreaterEqual(first["selectionWindows"],35)

    def test_wick_entry_is_09_and_exit_is_15_utc(self):
        from datetime import datetime,timezone
        b=fixture();p=signals(b)
        self.assertEqual(MODEL,"EURUSD_M15_EARLY_SESSION_WICK_REJECTION_TO_15UTC_V1")
        self.assertTrue(all(datetime.fromtimestamp(x["signal"]/1000,timezone.utc).hour==9 for x in p["plan"]))
        self.assertTrue(all(x["exit"]-x["signal"]==24*Q for x in p["plan"]))
        self.assertEqual(len(p["eligibleMondayUtcMs"]),10)

if __name__=="__main__":unittest.main()

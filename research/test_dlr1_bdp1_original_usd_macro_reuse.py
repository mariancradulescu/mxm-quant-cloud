"""DLR1 frozen causal first M5 and full-calendar benchmark tests."""
from datetime import date
import unittest
from .dlr1_bdp1_original_usd_macro_reuse import (
    START,WEEKS,M5,SYMBOLS,stamp,source_day,report)

def mk(day,open_,close_,entry,exit_):
    t=stamp(day,9,30)
    output={}
    for i in range(13):
        op=(open_ if i==0 else
            entry if i<=2 else
            exit_ if i==12 else entry)
        cl=close_ if i==0 else op
        output[t+i*M5]=[t+i*M5,t+(i+1)*M5,op,max(op,cl),min(op,cl),cl,1]
    return output

class Dlr1Tests(unittest.TestCase):
    def setUp(self):
        self.day=date(2026,9,17)
        self.m={
            "EURUSD":mk(self.day,100000,99800,99900,99600),
            "USDJPY":mk(self.day,100000,100100,100200,100500),
            "XAUUSD":mk(self.day,100000,99900,99700,99500)}

    def test_calendar_and_symbol_triplet(self):
        self.assertEqual(START,date(2025,11,3))
        self.assertEqual(WEEKS,52)
        self.assertEqual(SYMBOLS,("EURUSD","USDJPY","XAUUSD"))
        self.assertEqual(stamp(date(2026,3,8),9,30)-stamp(date(2026,3,8),9,25),300000)

    def test_first_bar_coherence_not_later_sign(self):
        result=source_day(self.day,self.m)
        self.assertTrue(result["coherentEvent"])
        self.assertEqual(result["usdDirection"],1)
        self.assertGreater(result["grossBps"]["coherentUsdOpening"],0)
        self.assertEqual(result["grossBps"]["cash"],0.0)
        self.assertAlmostEqual(result["grossBps"]["fixedLongUsd"],
                               -result["grossBps"]["fixedShortUsd"])
        self.assertAlmostEqual(result["grossBps"]["coherentUsdOpening"],
                               result["grossBps"]["dollarFirstBarUnfiltered"])

    def test_no_coherence_is_cash_but_unfiltered_reports(self):
        discord={k:v.copy() for k,v in self.m.items()}
        discord["XAUUSD"]=mk(self.day,100000,100100,99700,99500)
        x=source_day(self.day,discord)
        self.assertEqual(x["state"],"MATCHED_COMPLETE_M5_OPEN_PROXY")
        self.assertFalse(x["coherentEvent"])
        self.assertEqual(x["grossBps"]["coherentUsdOpening"],0)
        self.assertNotEqual(x["grossBps"]["dollarFirstBarUnfiltered"],0)

    def test_missing_bar_is_unknown_and_never_cash_zero(self):
        m={k:v.copy() for k,v in self.m.items()}
        del m["EURUSD"][stamp(self.day,10,10)]
        x=source_day(self.day,m)
        self.assertEqual(x["state"],"MISSING_FUTURE_M5_PATH")
        self.assertNotIn("grossBps",x)

    def test_missing_first_bar_is_unknown(self):
        m={k:v.copy() for k,v in self.m.items()}
        del m["USDJPY"][stamp(self.day,9,30)]
        self.assertEqual(source_day(self.day,m)["state"],
                         "MISSING_OR_INVALID_CAUSAL_FIRST_M5")

    def test_incomplete_260day_benchmark_not_assumed_0(self):
        s=report([{"week":0,"state":"MISSING_OR_INVALID_CAUSAL_FIRST_M5"}]*260)
        self.assertIsNone(s["sameDenominatorGrossMeanBps"]["coherentUsdOpening"])
        self.assertIsNone(s["scheduledDayMeanPrimaryBpsWithMissingNotImputed"])
        self.assertEqual(s["sourceCompleteComparisonDays"],0)

if __name__=="__main__":
    unittest.main()

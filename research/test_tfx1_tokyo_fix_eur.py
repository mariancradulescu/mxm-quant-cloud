"""TFX1 fixed Tokyo corporate fixing: causal intent and JPY EUR valuation."""
import unittest
from datetime import date
from decimal import Decimal as D
from .ctrader_proto import OpenApiModelMessages_pb2 as e
from .tfx1_tokyo_fix_eur import (
    event,stamp,M5,partition,exit_at,own_reversal,
    paired,jpy_to_eur,net_eur,report_group,scheduled
)

def bar(day,minute,op,hi,lo,cl):
    at=stamp(day,minute//60,minute%60)
    return [at,at+M5,op,hi,lo,cl]

def contract():
    return e.ProtoOASymbol(
        symbolId=7,digits=3,pipPosition=2,
        minVolume=100000,stepVolume=100000,maxVolume=100000000,
        lotSize=10000000,preciseTradingCommissionRate=300000000,
        preciseMinCommission=0,commissionType=2,minCommissionType=1,
        minCommissionAsset="USD",pnlConversionFeeRate=0,
        swapTime=1320,swapPeriod=24,tradingMode=0,enableShortSelling=True)

class TokyoFixTests(unittest.TestCase):
    def test_whole_calendar_exact_and_gotobi_not_weekend_shifted(self):
        rows=list(scheduled())
        self.assertEqual(len(rows),260)
        self.assertEqual(rows[0][1],date(2025,11,3))
        self.assertEqual(rows[-1][1],date(2026,10,30))
        self.assertEqual(event(date(2026,1,5)),"FIXING_UNWIND_INTENT")
        self.assertEqual(event(date(2026,1,6)),"ABSTAIN_CALENDAR")
        self.assertEqual(event(date(2026,1,30)),"FIXING_UNWIND_INTENT")
        with self.assertRaises(ValueError):
            event(date(2026,1,10))

    def test_predecision_and_monitoring_separate(self):
        day=date(2026,1,5)
        pre=[bar(day,25+i*5,100,101,99,100) for i in range(6)]
        post=[bar(day,55+i*5,100,100,99,100) for i in range(3)]
        # post clock list 00:55,01:00,01:05.
        p=partition(day,pre+post)
        self.assertIsNotNone(p["pre"])
        self.assertIsNotNone(p["monitor"])
        self.assertEqual(exit_at(p),"10:35")
        self.assertEqual(own_reversal(p),0)
        q=partition(day,pre)
        self.assertIsNotNone(q["pre"])
        self.assertIsNone(q["monitor"])
        self.assertEqual(event(day),"FIXING_UNWIND_INTENT")
        self.assertIsNone(exit_at(q))

    def test_missing_middle_monitor_not_faked(self):
        day=date(2026,1,5)
        pre=[bar(day,25+i*5,100,101,99,100) for i in range(6)]
        post=[bar(day,55,100,100,100,100),
              bar(day,65,100,100,100,100)]
        q=partition(day,pre+post)
        self.assertIsNone(q["monitor"])
        self.assertEqual(event(day),"FIXING_UNWIND_INTENT")

    def test_quote_age_and_crossed_not_executable(self):
        t=100000
        self.assertIsNone(paired([(t-22000,15000000)],
                                 [(t-100,15001000)],t))
        self.assertIsNone(paired([(t,15002000)],[(t,15001000)],t))
        self.assertIsNone(paired([(t+1,15000000)],[(t+1,15001000)],t))
        self.assertEqual(paired([(t-1000,15000000)],
                                [(t-1500,15001000)],t),
                         [15000000,15001000])

    def test_true_signed_jpy_to_usd_to_eur(self):
        usd=[15000000,15001000]
        eur=[110000,110010]
        positive=jpy_to_eur(D(165),usd,eur)
        negative=jpy_to_eur(D(-165),usd,eur)
        self.assertGreater(positive,D(0))
        self.assertLess(negative,D(0))
        self.assertGreater(abs(negative),positive)

    def test_current_broker_fee_and_slippage_reduce_net(self):
        day=date(2026,1,5)
        usd={"10:00":[15000000,15001000],
             "10:15":[14996000,14997000],
             "10:35":[14990000,14991000]}
        fx={k:[110000,110010] for k in usd}
        cen=net_eur(contract(),usd,fx,-1,"10:35",0.5,day)
        adv=net_eur(contract(),usd,fx,-1,"10:35",2.0,day)
        self.assertGreater(cen["grossEur"],0)
        self.assertGreater(cen["feesEur"],0)
        self.assertGreater(cen["modeledSlippageEur"],0)
        self.assertGreater(cen["netEur"],adv["netEur"])
        self.assertGreater(adv["feesEur"],0)

    def test_non_gotobi_is_not_promoted_from_placebo(self):
        rows=[{"week":0,"intent":"FIXING_UNWIND_INTENT",
               "state":"INTENT_OUTCOME_UNKNOWN_MONITOR_BARS","fixed":None},
              {"week":0,"intent":"ABSTAIN_CALENDAR",
               "state":"ABSTAIN_CALENDAR",
               "fixed":{"central":{"netEur":-0.1},
                        "adverse":{"netEur":-0.2}}}]
        out=report_group(rows)
        self.assertEqual(out["intents"],1)
        self.assertEqual(out["matchedPriced"],0)
        self.assertIsNone(out["adverseMatchedMeanNetEur"]["primary"])
        self.assertEqual(out["adversePricedFixedShortMeanNetEur"],-0.2)

if __name__=="__main__":
    unittest.main()

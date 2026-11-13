"""RNE1 original signed USD->EUR conversion must obey original quote sides."""
import unittest
from decimal import Decimal as D
from datetime import date,datetime,timezone
from .rne1_eur_protected_exact_reconciliation import (
    current_eur,quote,no_swap,summary
)

class Contract:
    minVolume=10000
    maxVolume=10000000
    stepVolume=10000
    lotSize=100000
    tradingMode=0
    commissionType=2
    minCommissionType=2
    preciseTradingCommissionRate=0
    preciseMinCommission=0
    pnlConversionFeeRate=0
    swapTime=1320
    swapPeriod=24
    def HasField(self,x):
        return x not in set()

class TestRne1Euro(unittest.TestCase):
    def test_asymmetric_fx_credit_debit(self):
        c=Contract()
        entry=(D("3.000"),D("3.001"))
        exit_=(D("3.010"),D("3.011"))
        fx0=(D("1.08"),D("1.09"))
        fx1=(D("1.10"),D("1.11"))
        long=current_eur(c,entry,exit_,fx0,fx1,1,0.0)
        self.assertAlmostEqual(long["grossEur"],0.9/1.11)
        bad_exit=(D("2.990"),D("2.991"))
        losing=current_eur(c,entry,bad_exit,fx0,fx1,1,0.0)
        self.assertAlmostEqual(losing["grossEur"],-1.1/1.10)
        self.assertLess(losing["netEur"],0)
    def test_slippage_not_silent_zero(self):
        c=Contract()
        e=(D("3.000"),D("3.001"))
        z=(D("3.010"),D("3.011"))
        fx=(D("1.1"),D("1.101"))
        a=current_eur(c,e,z,fx,fx,1,0.5)
        b=current_eur(c,e,z,fx,fx,1,2.0)
        self.assertGreater(a["netEur"],b["netEur"])
        self.assertGreater(b["modeledSlippageEur"],a["modeledSlippageEur"])
    def test_future_quote_unavailable(self):
        at=123456
        v={"symbols":{"EURUSD":{str(at):{"clock":at,"pair":{
            "bid":{"raw":110000,"at":at-5000,"ageMs":5000},
            "ask":{"raw":110010,"at":at-10000,"ageMs":10000}}}}}}
        self.assertIsNotNone(quote(v,"EURUSD",at))
        v["symbols"]["EURUSD"][str(at)]["pair"]["ask"]["at"]=at+10
        with self.assertRaises(ValueError):
            quote(v,"EURUSD",at)
    def test_intraday_no_rollover(self):
        c=Contract()
        a=int(datetime(2026,10,1,15,tzinfo=timezone.utc).timestamp()*1000)
        b=int(datetime(2026,10,1,16,tzinfo=timezone.utc).timestamp()*1000)
        no_swap(c,a,b)
        z=int(datetime(2026,10,1,23,tzinfo=timezone.utc).timestamp()*1000)
        with self.assertRaises(ValueError):
            no_swap(c,a,z)
    def test_summary_no_favorable_filter(self):
        rows=[{"week":0,"adverse":{"rne1":{"netEur":1,"grossEur":2,"feesEur":0.5,"modeledSlippageEur":0.5}}},
              {"week":1,"adverse":{"rne1":{"netEur":-3,"grossEur":-2,"feesEur":0.5,"modeledSlippageEur":0.5}}}]
        x=summary(rows)
        self.assertEqual(x["number"],2)
        self.assertEqual(x["conditionalNetEurSum"],-2)

if __name__=="__main__":
    unittest.main()

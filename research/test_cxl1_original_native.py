"""CXL1 source-first full authenticity; synthetic tests never read broker."""
import unittest
from datetime import date
from decimal import Decimal as D
from .cxl1_original_feasibility import calendar,crypto_features,classification
from .cxl1_original_275_source import earlier
from .cxl1_original_native_eur_readback import side,no_swap,margins_equal

class TestCxl1FullOriginal(unittest.TestCase):
    def test_exact_calendar_is_pilot_union_earlier(self):
        all_=list(calendar())
        early=earlier()
        later=[x for x in all_ if x[0]>=date(2026,11,2)]
        self.assertEqual(len(all_),325)
        self.assertEqual(len(early),275)
        self.assertEqual(len(later),50)
        self.assertEqual(early+later,all_)
        self.assertEqual(len({d for d,_ in all_}),65)
        self.assertTrue(all(d.weekday()<5 for d,t in all_))

    def test_research_causal_policy_and_benchmarks_differ(self):
        x=dict(signal=1,own=-1,pre={"BTCUSD":(2.,10.),"ETHUSD":(-1.,5.)})
        self.assertEqual(side(x,"cxl1"),1)
        self.assertEqual(side(x,"ownEth15"),-1)
        self.assertEqual(side(x,"btcAlways"),1)
        self.assertEqual(side(x,"long"),1)
        self.assertEqual(side(x,"short"),-1)
        self.assertEqual(side(x,"cash"),0)
        x["signal"]=0
        self.assertEqual(side(x,"cxl1"),0)
        self.assertEqual(side(x,"ownEth15"),-1)
        x["signal"]=None
        self.assertIsNone(side(x,"cxl1"))
        self.assertTrue(margins_equal([D("8.28")],[D("8.28")]))

    def test_unknown_swap_not_faked(self):
        class Obj:
            def HasField(self,name):return False
        with self.assertRaises(Exception):
            no_swap(Obj(),Obj(),10_000,20_000)

if __name__=="__main__":
    unittest.main()

"""BWR1-F1 verifies the one-literal detector/finance correction.

Technical scoped correction only; exact original 52-week protocol frozen.
"""
from datetime import date
import unittest
from .bwr1_brent_wti_paired_eur import (
    MARKETS,M5,stamp,first_signal,book)
from .bwr1_original_protected_money_correction import (
    ORIGINAL_RUN,ORIGINAL_CIPHER,ORIGINAL_PLAIN,ORIGINAL_PUBLIC)

class Bwr1OriginalFinanceFixTests(unittest.TestCase):
    def test_original_immutable_receipt_ids(self):
        self.assertEqual(ORIGINAL_RUN,"43576022822")
        self.assertEqual(len(ORIGINAL_CIPHER),64)
        self.assertEqual(len(ORIGINAL_PLAIN),64)
        self.assertEqual(len(ORIGINAL_PUBLIC),64)

    def test_causal_intent_enters_financial_path_not_state_label_noop(self):
        d=date(2026,6,17)
        start=stamp(d,8,30)
        brent={start+i*M5:8000000 for i in range(40)}
        crude={start+i*M5:7800000 for i in range(40)}
        brent[stamp(d,9,45)]=8100000
        brent[stamp(d,10,0)]=8000000
        bars={"SpotBrent":brent,"SpotCrude":crude}
        self.assertEqual(first_signal(d,bars)["state"],"CAUSAL_REJECTED_BASIS")
        # This test must proceed beyond the first-signal check to the
        # original broker quote/fee gates. Missing quotes now trigger
        # an actual unpriced outcome, not the string false-branch.
        res=book(d,{"bars":bars,"quotes":{}},{},{})
        self.assertEqual(res["state"],"BASIS_EVENT_SOURCE_QUOTE_OR_FX_MISSING")
        self.assertNotEqual(res["state"],"CAUSAL_REJECTED_BASIS")

    def test_unchanged_feature_noncausal_abstention(self):
        d=date(2026,6,17)
        start=stamp(d,8,30)
        bars={name:{start+i*M5:(8000000 if name=="SpotBrent"
                                 else 7800000) for i in range(40)}
              for name in MARKETS}
        self.assertEqual(book(d,{"bars":bars,"quotes":{}},{},{})["state"],
                         "NO_REJECTED_BASIS_SWEEP")

if __name__=="__main__":
    unittest.main()

"""HRC1 design/causal positive-negative tests only; secret source is protected."""
import json,unittest
from pathlib import Path
from .hrc1_source_pilot import side

class Hrc1PilotChecks(unittest.TestCase):
    def test_protocol_is_new_registered_and_never_closed(self):
        p=json.loads(Path("research/hrc1_protocol.json").read_text())
        self.assertEqual(p["id"],"HRC1")
        self.assertEqual(p["status"],"REGISTERED_UNSCORED")
        self.assertTrue(p["noClosedStudyRerun"])
        self.assertEqual(p["initialCapitalEur"],300)
        self.assertEqual(len(p["sourceSymbols"]),12)
        self.assertFalse(p["calendar"]["independentConfirmation"])
        self.assertTrue(p["scientific"]["developmentOnlyPilot"])
        self.assertEqual(p["scientific"]["oneSidedComparisons"],2)
        self.assertFalse(p["financial"]["nativeFundingAdmitted"])
    def test_serial_regime_can_reverse_h1_momentum_without_future(self):
        alternating=[1 if i%2==0 else -1 for i in range(21)]
        persistent=list(range(1,22))
        self.assertEqual(side(alternating),-1)
        self.assertEqual(side(persistent),1)
        self.assertEqual(side([1]*21),0)
        self.assertEqual(side(alternating[:-1]),0)
        self.assertEqual(side(alternating),side((alternating+[999999])[:21]))
    def test_invalid_and_missing_predictors_cannot_be_scored(self):
        self.assertEqual(side([0]*21),0)
        self.assertEqual(side([float("nan")]*21),0)
        self.assertEqual(side([1,-1]*10),0)
if __name__=="__main__":unittest.main()

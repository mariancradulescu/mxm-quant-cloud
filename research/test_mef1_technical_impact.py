"""MEF1 postclosure delta diagnostics, synthetic only (no broker calls)."""
import unittest
from copy import deepcopy
from .mef1_technical_impact import compare

PROTOCOL = "0ae6bc874b6064d7e92495b4f870a75ab71ed94303f6750abb02bb18efb020bd"


def receipt():
    return {
        "protocolSha256": PROTOCOL,
        "orders": 0, "cloudActivated": False, "fundedNetEur": None,
        "readOnlyRequestsAfterAuth": 12,
        "candidates": {"AUDUSD": {
            "observations": [
                {"date":"2026-10-06","spreadBps":None,"commissionBps":None},
                {"date":"2026-10-13","spreadBps":0.2,"commissionBps":None},
            ],
            "validQuotePairs": 1,"costedQuotePairs": 0,"medianSpreadBps": 0.2,
            "medianCurrentFeePlusSampledSpreadBps": None,
            "terms":{"currentMinimumMarginEur":{"buy":30.0,"sell":30.0}},
        }}
    }


class TechnicalImpactChecks(unittest.TestCase):
    def test_locked_and_new_fee_attributions_separated(self):
        a,b=receipt(),receipt()
        b["candidates"]["AUDUSD"]["observations"]=[
            {"date":"2026-10-06","spreadBps":0,"commissionBps":0.7},
            {"date":"2026-10-13","spreadBps":0.2,"commissionBps":0.8},
        ]
        b["candidates"]["AUDUSD"]["validQuotePairs"]=2
        b["candidates"]["AUDUSD"]["costedQuotePairs"]=2
        x=compare(a,b)
        row=x["candidates"]["AUDUSD"]
        self.assertEqual(row["newlyAcceptedLockedQuoteDates"],["2026-10-06"])
        self.assertEqual(row["feeAttributionAddedToPreviouslyAcceptedQuoteDates"],
                         ["2026-10-13"])
        self.assertEqual(row["previouslyAcceptedSpreadChangedDates"],[])
        self.assertEqual(row["observedQuotePairs"],[1,2])
        self.assertIsNone(x["fundedNetEur"])
        self.assertFalse(x["economicPromotion"])

    def test_changed_protocol_and_invalid_claims_fail(self):
        a,b=receipt(),receipt()
        b["protocolSha256"]="changed"
        with self.assertRaisesRegex(ValueError,"PROTOCOL_CHANGED"):
            compare(a,b)
        b=receipt()
        b["orders"]=1
        with self.assertRaisesRegex(ValueError,"UNSAFE_OR_FINANCED"):
            compare(a,b)
        b=receipt()
        b["candidates"]["AUDUSD"]["observations"][0]["date"]="2026-01-01"
        with self.assertRaisesRegex(ValueError,"CALENDAR_CHANGED"):
            compare(a,b)

    def test_old_nonzero_spread_changed_is_not_silently_called_quote_unlock(self):
        a,b=receipt(),receipt()
        b["candidates"]["AUDUSD"]["observations"][1]["spreadBps"]=0.3
        x=compare(a,b)
        row=x["candidates"]["AUDUSD"]
        self.assertEqual(row["previouslyAcceptedSpreadChangedDates"],["2026-10-13"])
        self.assertEqual(row["newlyAcceptedLockedQuoteDates"],[])


if __name__=="__main__":
    unittest.main()

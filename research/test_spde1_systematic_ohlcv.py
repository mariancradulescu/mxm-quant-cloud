"""SPDE1 synthetic invariants: new predictive economics are NOT scored here."""
import unittest
from math import isfinite
from research.spde1_systematic_ohlcv import (
    FAM,M5,feature_states,fit_training,forecast,outcomes,session_clocks,
    build_tape,state_phase,Z_SELECT,weekly_bound,sign
)
from datetime import datetime, timezone


def bars_to(t, length=49, scale=5000, drift=1):
    a={}
    for i in range(length):
        end=t-(length-1-i)*M5
        price=scale+drift*i
        a[end]=[end-M5,end,price-1,price+3,price-3,price,i+1]
    return a


def protocol():
    return {"universe":["AAA","BBB"],
            "calendar":{"start":1762128000000,"trainEnd":1777852800000,
                        "selectionEnd":1785715200000,"end":1793577600000,
                        "decisionUtcHours":[8,12,16]},
            "horizonsMinutes":[60,240]}


class SystematicOHLCVTests(unittest.TestCase):
    def test_seven_complete_feature_family_states(self):
        t=1762156800000
        f=feature_states(bars_to(t),t)
        self.assertIsNotNone(f)
        self.assertEqual(len(f["state"]),6)
        self.assertEqual(f["state"]["IMPULSE_PERSISTENCE"],1)
        self.assertEqual(f["state"]["CLOSED_BAR_INDICATOR"],1)
        self.assertTrue(f["scale60"]>0)
        self.assertTrue(all(v in (-1,0,1) for v in f["state"].values()))

    def test_missing_or_future_bars_do_not_substitute_past(self):
        t=1762156800000
        a=bars_to(t)
        f=feature_states(a,t)
        a.pop(t-2*M5)
        a[t+M5]=[t,t+M5,1,2,1,2,0]
        self.assertIsNone(feature_states(a,t))
        del a[t+M5]
        self.assertIsNone(feature_states(a,t))
        self.assertIsNotNone(f)

    def test_original_future_label_never_erases_predecision_feature(self):
        p=protocol()
        t=session_clocks(p)[0]
        source={"AAA":list(bars_to(t).values()),"BBB":[]}
        slots,maps=build_tape(source,p)
        original=next(x for x in slots if x["t"]==t and x["symbol"]=="AAA")
        self.assertIsNotNone(original["f"])
        scored=outcomes(slots,maps,p)
        first=next(x for x in scored if x["t"]==t and x["s"]=="AAA"
                   and x["h"]==60)
        self.assertTrue(first["featureKnown"])
        self.assertFalse(first["labelKnown"])
        # Add a future *scoring* price and verify all forecast inputs unchanged.
        for at in (t+M5,t+65*60000):
            maps["AAA"][at]=[at-M5,at,5100,5102,5098,5101,0]
        second=outcomes(slots,maps,p)
        now=next(x for x in second if x["t"]==t and x["s"]=="AAA"
                 and x["h"]==60)
        self.assertEqual(first["f"],now["f"])
        self.assertTrue(now["labelKnown"])

    def test_training_is_restricted_to_matured_training_labels(self):
        train={"phase":"training","s":"AAA","h":60,
               "f":{"state":{k:1 for k in FAM}},
               "labelKnown":True,"normalizedTarget":2.0,"targetBps":1.0}
        audit={**train,"phase":"exposed_audit","normalizedTarget":-6.0,
               "targetBps":-300.0}
        fit,prior=fit_training([train,audit])
        self.assertEqual(fit[("AAA",60,FAM[0],1)]["n"],1)
        self.assertEqual(fit[("AAA",60,FAM[0],1)]["mu"],2/17)
        self.assertGreater(prior[("AAA",60)],.5)

    def test_no_proven_prediction_for_sparse_or_unknown_history(self):
        r={"phase":"selection","s":"AAA","h":60,
           "f":{"state":{k:1 for k in FAM},"scale60":1.0}}
        x=forecast(r,FAM[0],{}, {}, None)
        self.assertEqual(x["state"],"TRAINING_SUPPORT_UNKNOWN")
        x=forecast({**r,"f":None},FAM[0],{}, {}, None)
        self.assertEqual(x["state"],"SOURCE_UNKNOWN")
        self.assertEqual(sign(0),0)
        self.assertTrue(weekly_bound([0]*13)<=0)
        self.assertTrue(isfinite(Z_SELECT))

    def test_global_clock_calendar_and_validation_are_not_independent(self):
        p=protocol()
        clock=session_clocks(p)
        self.assertEqual(len(clock),780)
        self.assertEqual(state_phase(clock[0],p["calendar"]),"training")
        self.assertEqual(state_phase(clock[390],p["calendar"]),"selection")
        self.assertEqual(state_phase(clock[585],p["calendar"]),"exposed_audit")


if __name__=="__main__":
    unittest.main()

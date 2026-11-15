"""Synthetic invariants for the ex-ante RDE1 risk study. No broker sources."""
import math
import unittest
from research.rde1_risk_distribution import (
    causal_clocks,realized_labels,fit_training,forecast,
    paired_weekly,mandatory_economic_gate,validated,TAU
)

SCOPE=dict(calendarStart=1762128000000,trainEnd=1777852800000,
           selectionEnd=1785715200000,end=1793577600000)

def synthetic(count=420):
    start=SCOPE["calendarStart"]-200*300000
    out=[];price=100000
    for i in range(count):
        opening=price
        price+=3+int(17*math.sin(i/11))
        end=start+(i+1)*300000
        out.append([end-300000,end,opening,max(opening,price)+10,
                    min(opening,price)-10,price,100+i%13])
    return out


class Rde1SafetyTests(unittest.TestCase):
    def test_causality_future_mutation(self):
        a=synthetic()
        intents,_,_=causal_clocks("EURUSD",a,SCOPE)
        self.assertGreater(len(intents),0)
        ref=next(x for x in intents if x["index"]<300)
        mutated=[list(x) for x in a]
        for i in range(ref["index"]+1,len(mutated)):
            shift=10000
            mutated[i][2]+=shift;mutated[i][3]+=shift
            mutated[i][4]+=shift;mutated[i][5]+=shift
        intents2,_,_=causal_clocks("EURUSD",mutated,SCOPE)
        same=next(x for x in intents2 if x["t"]==ref["t"])
        for key in ("direction","rv24","rv48","volRatio",
                    "persistence","entryClock"):
            self.assertEqual(ref[key],same[key])

    def test_forward_censoring_preserves_causal_intents(self):
        a=synthetic()
        intents,raw,runs=causal_clocks("EURUSD",a,SCOPE)
        labels=realized_labels(intents,raw,runs,SCOPE)
        self.assertEqual(len(intents),len(labels))
        self.assertTrue(any(x["known"] for x in labels))
        self.assertTrue(any(not x["known"] for x in labels))
        self.assertEqual([x["t"] for x in intents],[x["t"] for x in labels])

    def test_duplicate_rejected(self):
        a=synthetic(120)
        with self.assertRaisesRegex(ValueError,"DUPLICATE"):
            validated(a+[list(a[100])])

    def test_train_only_tail_distribution(self):
        rows=[]
        for i in range(160):
            rows.append(dict(s="EURUSD",t=SCOPE["calendarStart"]+i*3600000,
                phase="training",known=True,volRatio=.6+i%3*.4,
                persistence=i%2,scaleBps=12.,
                longAdverse=float(i%23+2),shortAdverse=float(i%17+3)))
        fit=fit_training(rows)
        self.assertEqual(fit["trainKnown"],160)
        snap=forecast(rows[0],fit,1)
        self.assertGreaterEqual(snap["simple"],0)
        self.assertGreaterEqual(snap["conditional"],0)
        # Exposed labels never enter fit, even at arbitrary magnitudes.
        rows.append({**rows[0],"phase":"selection","longAdverse":999999.})
        fit2=fit_training(rows)
        self.assertEqual(fit["simple"],fit2["simple"])
        self.assertEqual(fit["groups"],fit2["groups"])
        p=paired_weekly(rows,fit2,SCOPE,"selection",1)
        self.assertEqual(p["n"],1)
        self.assertFalse(p["acceptedRiskInformation"])

    def test_no_financial_evidence_means_no_trade(self):
        self.assertFalse(mandatory_economic_gate(
            [],"EURUSD",1,SCOPE,None)["admitted"])
        self.assertFalse(mandatory_economic_gate(
            [],"EURUSD",1,SCOPE,dict(
                minimumNotionalEur=1000,minimumMarginEur=301,
                adverseBps=8,fundingKnown=True))["admitted"])


if __name__=="__main__":
    unittest.main()

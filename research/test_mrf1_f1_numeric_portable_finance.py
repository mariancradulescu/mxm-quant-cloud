"""MRF1-F1 NEW numerical-portability technical finance-only: secretless integrity tests.

No original market data, no predictor training or scoring, no brokerage.
"""
from __future__ import annotations
import hashlib,json,math,tempfile,unittest
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch
import numpy as np

from . import mrf1_f1_numeric_portable_finance as a
from . import mrf1_authentic_m1_multiresolution as m

class Mrf1RecoveryTests(unittest.TestCase):
    def test_source_adapter_converts_raw_bidask_not_future_synthetic_price(self):
        t=m.START+14*24*m.H+8*m.H+30*m.M
        entry=t+m.DECISION_DELAY
        exit_=entry+m.EXIT_DELAY
        raw=[
            [entry-1000,110000],[entry-900,110005]
        ]
        with patch.object(m,"fee_usd",return_value=D(".03")):
            quote=m.to_euro_quote(raw,entry,object(),D(1000),D("33.33"))
            nextquote=m.to_euro_quote([[exit_-1000,110100],[exit_-900,110105]],
                exit_,object(),D(1000),D("33.33"))
        self.assertIn("Bid",quote)
        self.assertIn("Ask",quote)
        self.assertEqual(quote["Symbol"],"EURUSD")
        self.assertEqual(quote["At"],entry)
        self.assertEqual(quote["MarginPerUnit"],"0.0333300000")
        result=m.actual_original_eur_payoff(quote,nextquote,1,D(1000),"adverse")
        self.assertTrue(math.isfinite(result["netEur"]))
        self.assertGreater(result["netEur"],0)
        with self.assertRaises(KeyError):
            m.actual_original_eur_payoff({"EURUSD":raw},{"EURUSD":raw},1,D(1000),"adverse")

    def test_first_original_json_file_never_replaced_or_relaxed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"first.json"
            p.write_text('{"originalRunId":44069157176}')
            with patch.object(a,"FIRST",p):
                with self.assertRaisesRegex(ValueError,"FIRST_ORIGINAL_BYTE_HASH_CHANGED"):
                    a.first_original()

    def test_exact_12_model_order_and_bit_hash_recovery(self):
        rows=[]
        for w in range(4):
            for j in range(340):
                t=m.START+w*m.W+(j//4)*m.M*30
                symbol=m.SYMS[j%4]
                # This is purely a synthetic immutable model parity fixture.
                features=[.01*(w+1)+.001*(j+i) for i in range(26)]
                rows.append(dict(t=t,s=symbol,week=w,features=features))
        models=[]
        for w in (3,4):
            for horizon in m.HORIZONS:
                for variant in ("FULL","BASE"):
                    cols=m.FULL_COLS if variant=="FULL" else m.BASE_COLS
                    models.append(dict(week=w,horizonMinutes=horizon,variant=variant,
                        columns=cols,coefficients=[.02]+[.001*(i+1) for i in cols],
                        residualQuantiles=[-.1+i*.01 for i in range(16)],
                        calibrationMaturedThrough=m.START+(w-2)*m.W-4*m.H))
        # Independent forward reapplication of ONLY stored coefficients.
        X=np.asarray([r["features"] for r in rows],float)
        weeks=np.asarray([r["week"] for r in rows])
        digest=hashlib.sha256();samples=[]
        for model in models:
            idx=np.flatnonzero(weeks==model["week"]-1)
            cols=model["columns"];beta=np.asarray(model["coefficients"])
            pred=np.column_stack((np.ones(len(idx)),X[idx][:,cols]))@beta
            for j,i in enumerate(idx):
                key=(int(rows[i]["t"]),rows[i]["s"],
                    model["horizonMinutes"],model["variant"])
                value=float(pred[j])
                digest.update(json.dumps(dict(key=key,mean=value),
                    sort_keys=True,separators=(",",":")).encode())
                if len(samples)<24:
                    samples.append(dict(features=rows[i]["features"],
                        columns=cols,coefficients=beta.tolist(),expected=value))
        fake=dict(predictive=dict(models=models,nativeModelParityInputs=samples))
        # A deliberately DIFFERENT full binary hash is allowed ONLY when
        # original 24 parity sample predictions, original coefficients and
        # features remain within the separately frozen 5e-14 bound.
        with patch.object(a,"FIRST_PREDICTION_COMMITMENT","0"*64):
            forecast,proven=a.reproduce_locked_forecast_commitment(rows,fake)
        self.assertEqual(len(forecast),4080)
        self.assertEqual(proven["modelsRefitted"],0)
        self.assertEqual(proven["priceLabelsRescored"],0)
        self.assertEqual(proven["originalFirstPredictionHash"],digest.hexdigest())
        self.assertFalse(proven["fullOriginalForecastByteIdentity"])
        self.assertEqual(proven["fixedBinary64AbsoluteParityBound"],5e-14)
        fake["predictive"]["nativeModelParityInputs"][0]["expected"]+=1e-9
        with patch.object(a,"FIRST_PREDICTION_COMMITMENT","0"*64):
            with self.assertRaisesRegex(ValueError,"NUMERIC_PARITY_BOUND_BREACHED"):
                a.reproduce_locked_forecast_commitment(rows,fake)

if __name__=="__main__":unittest.main()

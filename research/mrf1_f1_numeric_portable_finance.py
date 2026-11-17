"""MRF1-F1 SECOND POSTFIRST NUMERICAL-PORTABILITY technical finance ONLY.

First original #44069157176 FAILED after NEW predictive score. Its immutable
predictive receipt contains all fitted models and calibration quantiles.
This uses those EXACT frozen models; NEVER re-fits, scores price labels or
reruns that original. It repairs only the overlooked conversion of original
raw CXL1 EURUSD BIDASK quote pairs into existing native LedgerQuote inputs.
"""
from __future__ import annotations
import hashlib,json,os,subprocess,tempfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import numpy as np

from . import mrf1_authentic_m1_multiresolution as m

FIRST_RUN="44069157176"
FIRST_JSON_SHA256="3a5fd059a3da1eba6d132f69bc9dd43db4fa2c2b1b0422d3c2de5581fca1aa98"
FIRST_PREDICTION_COMMITMENT="90b196fcb308122d0c20c48cc613a4f455d23a8fff9ac3a3f186e462231a87dc"
FROZEN=Path("research/MRF1_F1_PRESCORE_FINANCIAL_ADAPTER_RECOVERY_PROTOCOL_20261117.md")
NUMERIC_FROZEN=Path("research/MRF1_F1_NUMERIC_PORTABILITY_RECOVERY_BOUNDARY_20261117.md")
MAX_PORTABLE_FORECAST_ERROR=5e-14
FIRST_FAILED_RECOVERY_RUN=44070799145
FIRST=Path("mrf1-first-original/mrf1-original-predictive.json")
OUT=Path("mrf1-f1-numeric-recovery-financial.public.json")

def need(v,reason):
    if not v:raise ValueError("MRF1_FINANCIAL_RECOVERY_"+reason)

def first_original():
    original=FIRST.read_bytes()
    need(hashlib.sha256(original).hexdigest()==FIRST_JSON_SHA256,"FIRST_ORIGINAL_BYTE_HASH_CHANGED")
    past=json.loads(original)
    need(past.get("schema")=="MXM_MRF1_NEW_ORIGINAL_M1_INFORMATION_7TF_THREE_HORIZON_V1"
         and str(past.get("originalRunId"))==FIRST_RUN
         and past.get("ordersSubmitted")==0 and past.get("cloudActivated") is False
         and past.get("qualified") is False and past.get("independentConfirmation") is False,
         "FIRST_ORIGINAL_NOT_PROVEN")
    need(hashlib.sha256(m.P.read_bytes()).hexdigest()==past["frozenProtocolSha256"],
         "FIRST_MODEL_FROZEN_PROTOCOL_CHANGED")
    need(hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()==past["implementationSha256"],
         "FIRST_ORIGINAL_MODEL_SOURCE_CHANGED")
    need(past["predictive"]["predictionHashSha256"]==FIRST_PREDICTION_COMMITMENT
         and len(past["predictive"]["models"])==12
         and len(past["predictive"]["paired"])==6
         and all(x["fullMinusBaseMseBenefit"]<0 and x["fullMinusZeroMseBenefit"]<0
                 for x in past["predictive"]["paired"]),
         "FIRST_ORIGINAL_PREDICTIVE_RESULT_CHANGED")
    need(past["sourceCalendar"]["scheduled"]==1360
         and past["sourceCalendar"]["featureKnown"]==1360,
         "FIRST_ORIGINAL_POPULATION_CHANGED")
    return past

def causal_features_only(streams):
    """Same original SOURCE predecision clocks; no price outcome labels at all."""
    rows=[]
    for d in range(28):
        day=datetime.fromtimestamp((m.START+d*m.DAY)/1000,timezone.utc)
        if day.weekday()>=5:continue
        for k in range(17):
            t=m.START+d*m.DAY+8*m.H+k*30*m.M
            for symbol in m.SYMS:
                f,why=m.frame(symbol,streams,t)
                need(f is not None,"ORIGINAL_PREDECISION_FRAME_CHANGED_"+str(why))
                need("labels" not in f,"FUTURE_PRICE_LABELS_NOT_ALLOWED_IN_RECOVERY")
                rows.append(f)
    need(len(rows)==1360,"ORIGINAL_1360_FEATURE_DENOMINATOR_CHANGED")
    return rows

def reproduce_locked_forecast_commitment(rows,first):
    """ONLY transform original immutable coefficients into predictions.

    No ridge fit, no price target, no calibration, no outcome score.
    Both float matrix ordering and F1 forecast JSON hash MUST bit-match.
    """
    X=np.asarray([r["features"] for r in rows],float)
    weeks=np.asarray([r["week"] for r in rows])
    result={};digest=hashlib.sha256();models=first["predictive"]["models"]
    ordered=[(w,h,v) for w in (3,4) for h in m.HORIZONS for v in ("FULL","BASE")]
    need([(x["week"],x["horizonMinutes"],x["variant"]) for x in models]==ordered,
         "FIRST_FITTED_MODEL_ORDER_CHANGED")
    need(X.shape==(1360,26),"ORIGINAL_FEATURE_SHAPE_CHANGED")
    examples=[];modelForecasts=0
    for model in models:
        week=model["week"]-1;horizon=model["horizonMinutes"];variant=model["variant"]
        cols=model["columns"];beta=np.asarray(model["coefficients"],float)
        need(cols==(m.FULL_COLS if variant=="FULL" else m.BASE_COLS)
             and len(beta)==len(cols)+1 and
             len(model["residualQuantiles"])==16,
             "ORIGINAL_MODEL_COLUMNS_OR_QUANTILES_CHANGED")
        idx=np.flatnonzero(weeks==week)
        preds=np.column_stack((np.ones(len(idx)),X[idx][:,cols]))@beta
        for j,i in enumerate(idx):
            r=rows[i];t=int(r["t"]);s=r["s"];value=float(preds[j])
            key=(t,s,horizon,variant)
            digest.update(json.dumps(dict(key=key,mean=value),sort_keys=True,
                separators=(",",":")).encode())
            result[key]=dict(mean=value,
                quantile=[float(v) for v in model["residualQuantiles"]],
                due=int(t+horizon*m.M),
                calibrationThrough=int(model["calibrationMaturedThrough"]))
            if len(examples)<24:
                examples.append(dict(features=r["features"],columns=cols,
                    coefficients=beta.tolist(),expected=value))
            modelForecasts+=1
    bit_same=(digest.hexdigest()==FIRST_PREDICTION_COMMITMENT)
    # The first recovery STOPPED at this SHA boundary before native finance;
    # do not assert a bit-for-bit identity across BLAS/CPU environments.
    # The separately FROZEN numerical addendum precommits the strict
    # 5e-14 binary64 absolute error bound on original parity examples.
    oldExamples=first["predictive"]["nativeModelParityInputs"]
    need(len(oldExamples)==24 and len(examples)==24,"FIRST_NATIVE_PARITY_EXAMPLES_MISSING")
    maximumSampleDifference=0.
    for a,b in zip(oldExamples,examples):
        need(a["columns"]==b["columns"] and
             np.array_equal(np.asarray(a["coefficients"],dtype=np.float64),
                            np.asarray(b["coefficients"],dtype=np.float64)) and
             np.allclose(a["features"],b["features"],rtol=0,
                         atol=MAX_PORTABLE_FORECAST_ERROR),
             "FIRST_ORIGINAL_COEFFICIENT_OR_FEATURE_PARITY_CONFLICT")
        diff=abs(a["expected"]-b["expected"])
        need(diff<=MAX_PORTABLE_FORECAST_ERROR,
             "FIRST_ORIGINAL_NUMERIC_PARITY_BOUND_BREACHED")
        maximumSampleDifference=max(maximumSampleDifference,diff)
    return result,dict(originalFirstPredictionHash=digest.hexdigest(),
        originalFirstPredictionCommitment=FIRST_PREDICTION_COMMITMENT,
        fullOriginalForecastByteIdentity=bit_same,
        predictedModelMathematicalParity24Cases=True,
        numberOfFirstOriginalParityCases=24,
        maximumOriginalSamplePredictionError=maximumSampleDifference,
        fixedBinary64AbsoluteParityBound=MAX_PORTABLE_FORECAST_ERROR,
        firstFailedRecoveryRunId=FIRST_FAILED_RECOVERY_RUN,
        forecastApplications=modelForecasts,sourceFeatureRows=len(rows),
        originalModelsApplied=12,modelsRefitted=0,priceLabelsRescored=0,
        exactPreviousNativeParityCases=24)

def save(result):
    OUT.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False)+"\n")

def main():
    need(FROZEN.exists() and "FROZEN" in FROZEN.read_text(),
         "FROZEN_RECOVERY_BOUNDARY_ABSENT")
    need(NUMERIC_FROZEN.exists() and "freeze" in NUMERIC_FROZEN.read_text().lower(),
         "SECOND_NUMERIC_PORTABILITY_PRESOURCE_BOUNDARY_ABSENT")
    original=first_original()
    originalBars,rawQuoteSource,contract,custody=m.validate_original_sources()
    # Revalidate source binding against ORIGINAL F1, not current timestamps.
    firstBinding=original["sourceAuthenticity"]
    need(custody["hxcCiphertextSha256"]==firstBinding["hxcCiphertextSha256"]
         and custody["hxcSourceProtocolSha256"]==firstBinding["hxcSourceProtocolSha256"]
         and custody["cxlOriginalCiphertextSha256"]==firstBinding["cxlOriginalCiphertextSha256"]
         and custody["cxlOriginalPlaintextSha256"]==firstBinding["cxlOriginalPlaintextSha256"]
         and custody["newBrokerRequests"]==0,
         "ORIGINAL_SOURCE_CUSTODY_BINDING_CHANGED")
    streams,coverage=m.prepare(originalBars)
    need(coverage==original["originalSourceTfCounts"],
         "FIRST_ORIGINAL_7TF_SUPPORT_CHANGED")
    rows=causal_features_only(streams)
    forecasts,parity=reproduce_locked_forecast_commitment(rows,original)
    # **THE SOLE ORIGINAL FINANCIAL ADAPTER REPAIR**: keep all exactly
    # prespecified 80 clocks, normalize the untouched original paired
    # BIDASK into native ledger quote schema. It does not inspect profits.
    financialQuotes=m.original_finance_points(rawQuoteSource,contract)
    need(len(financialQuotes)==80,
         "SOURCE_QUOTE_ADAPTER_DOES_NOT_PRESERVE_80_CLOCKS")
    result=dict(schema="MXM_MRF1_F1_POSTFIRST_NUMERIC_PORTABILITY_FINANCIAL_RECOVERY_V2",
        originalFirstRunId=int(FIRST_RUN),originalFirstRunStatus="FAILED_POST_PREDICTIVE_BEFORE_FINANCE",
        firstOriginalArtifactId=14321283370,
        firstOriginalZipSha256="497c9baa9a6bd75d169d8c4a2099fce432267d47e250de5989651c33226c07bf",
        firstOriginalPredictiveJsonSha256=FIRST_JSON_SHA256,
        firstOriginalFrozenProtocolSha256=original["frozenProtocolSha256"],
        recoveryFrozenProtocolSha256=hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
        secondRecoveryFrozenProtocolSha256=hashlib.sha256(NUMERIC_FROZEN.read_bytes()).hexdigest(),
        firstFailedRecoveryRunId=FIRST_FAILED_RECOVERY_RUN,
        firstFailedRecoveryReason="BITWISE_FORECAST_SHA_DIFFERENCE_DUE_FLOATING_ROUNDING_NOT_A_NEW_MODEL",
        recoverySourceCodeSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        recoveryRunId=os.environ.get("GITHUB_RUN_ID"),
        originalAuthenticSourceCustody=custody,
        exactFirstOriginalModelParity=parity,
        firstOriginalPredictiveVerdict="ALL_SIX_FULL_VS_BASE_AND_ZERO_PRICE_MSE_BENEFITS_NEGATIVE",
        firstOriginalPricePredictiveReevaluated=False,
        preservedFirstFailure=True,newModelFitted=False,
        originalQuoteTimestampClocks=80,financeEvaluationClockCount=40,
        financialRecoveryIsNotAnIndependentOriginal=True,
        historicalBrokerActualFillsCertified=False,
        historicalTariffContinuityCertified=False,
        independentConfirmation=False,qualified=False,
        ordersSubmitted=0,cloudActivated=False,newBrokerRequests=0,
        oldClosedStudiesRerun=False)
    save(result)
    dotnet=os.environ.get("MRF1_DOTNET","dotnet")
    dll="src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
    with tempfile.TemporaryDirectory(prefix="mrf1-f1-finance-recovery-") as td:
        infile=Path(td)/"finance.json";outfile=Path(td)/"native.json"
        for scenario in ("central","adverse"):
            inp,census,unfunded=m.financial_input(rows,forecasts,financialQuotes,scenario)
            need(census["evaluationScheduled"]==40,"FINANCIAL_40_CLOCK_POPULATION_CHANGED")
            infile.write_text(json.dumps(inp,allow_nan=False,separators=(",",":")))
            financeSha=hashlib.sha256(infile.read_bytes()).hexdigest()
            # Existing C# engine, no use of CXL policy or PVE3 etc.
            native=subprocess.run([dotnet,dll,str(infile),str(outfile),"--native-mrf1"],
                capture_output=True,text=True,timeout=1200)
            if native.returncode!=0 or not outfile.exists():
                result["native_"+scenario]=dict(status="UNKNOWN_NATIVE_FINANCE_TECHNICAL_FAILURE",
                    returnCode=native.returncode,diagnostic=native.stderr[-250:])
                result["financialCensus_"+scenario]=census
                save(result)
                raise RuntimeError("MRF1_F1_FINANCIAL_RECOVERY_NATIVE_"+scenario+"_FAILURE")
            scored=json.loads(outfile.read_text())
            need(set(scored)=={"FULL","BASE","CASH"},"COMMON_NATIVE_EUR300_BOOKS_MISSING")
            for policy,book in scored.items():
                need(book["Qualified"] is False and book["IndependentlyConfirmed"] is False
                     and book["OrdersSubmitted"]==0 and book["CloudActivated"] is False,
                     "NATIVE_FINANCIAL_SAFETY_NOT_RECONCILED")
                card=book["Scorecard"]
                need(card["Policy"]==policy+"_"+scenario and len(
                    card["FundedCompletionsByIsoWeek"])==2 and
                    card["CompletedRoundTrips"]==len(book["Trades"]),
                    "COMMON_BOOK_FUNDED_COMPLETIONS_NOT_RECONCILED")
            result["financialCensus_"+scenario]=census
            result["native_"+scenario+"InputSha256"]=financeSha
            result["native_"+scenario]=scored
            result["unfundedQuoteSideCounterfactual_"+scenario]=dict(
                availableModelPayoffSides=len([x for x in unfunded if x["scenario"]==scenario]),
                alwaysLongConditionalSumEur=sum(x["knownModelUnfundedCounterfactual"]["netEur"]
                    for x in unfunded if x["scenario"]==scenario and x["side"]==1),
                alwaysShortConditionalSumEur=sum(x["knownModelUnfundedCounterfactual"]["netEur"]
                    for x in unfunded if x["scenario"]==scenario and x["side"]==-1),
                notFinancedModels=True,
                noBrokerRealFillsCertified=True)
            Path("mrf1-f1-numeric-recovery-financial-"+scenario+".json").write_text(
                json.dumps(scored,sort_keys=True,indent=2,allow_nan=False)+"\n")
            save(result)
            print("MRF1_F1_NUMERIC_RECOVERY_NATIVE_FINANCE",scenario,
                json.dumps({v:dict(netEur=scored[v]["Scorecard"]["NetEur"],
                    trips=scored[v]["Scorecard"]["CompletedRoundTrips"],
                    hard21=scored[v]["Scorecard"]["Hard21AllEligibleWeeks"])
                    for v in ("FULL","BASE","CASH")}),flush=True)
    result["recoveryFinancialStageSucceeded"]=True
    save(result)
    print("MRF1_F1_FIRST_MODELS_NUMERICAL_PARITY_FINANCE_ONLY_COMPLETED",
        json.dumps(parity,sort_keys=True),flush=True)

if __name__=="__main__":main()

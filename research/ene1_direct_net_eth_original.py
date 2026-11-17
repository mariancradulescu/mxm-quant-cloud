"""ENE1 new original adverse-EUR NET conditional-tail study on authentic ETH CFDs.

Novel objective: predict source-matched EXECUTION-COST net EUR outcomes for both
ETH sides rather than future price MSE. Uses original CXL1 archives as raw
price and quote SOURCE only. Never calls CXL1 strategy score/replay, PVE3 or MRF1.
"""
from __future__ import annotations
import hashlib,json,math,os,subprocess,tempfile
from collections import Counter
from datetime import datetime,timezone
from decimal import Decimal as D
from pathlib import Path
import numpy as np
from . import ene1_eth_original_source_and_features as src

START=src.MONDAY
END=START+13*src.WEEK
TRAIN_END=START+6*src.WEEK
CAL_END=START+9*src.WEEK
EVAL_START=CAL_END
FROZEN=src.FROZEN
RESULT=Path("ene1-new-original-public.json")
MIN_TRAIN=80
MIN_CAL=40
RIDGE=64

def need(x,k):
    if not x:raise ValueError("ENE1_"+k)
def frozen_cols(variant):
    return src.FULL_COLS if variant=="FULL" else src.BASE_COLS

def ridge(X,y,cols):
    a=np.column_stack((np.ones(len(X)),X[:,list(cols)]))
    lhs=a.T@a
    lhs[1:,1:]+=RIDGE*np.eye(len(cols))
    return np.linalg.solve(lhs,a.T@y)
def pred(X,cols,beta):
    return np.column_stack((np.ones(len(X)),X[:,list(cols)]))@beta
def quantile16(residual):
    return np.quantile(residual,(np.arange(16)+.5)/16)

def fit_and_score(rows):
    featureKnown=np.array([row["features"] is not None for row in rows],dtype=bool)
    X=np.array([r["features"] if r["features"] is not None else [0.]*14 for r in rows],dtype=float)
    t=np.array([row["t"] for row in rows]);week=np.array([row["week"] for row in rows])
    due=t+src.DECISION_DELAY+src.EXIT_DELAY
    known=np.array([row["labels"]["adverse",1] is not None and
                    row["labels"]["adverse",-1] is not None for row in rows],dtype=bool)
    need(len(X)==325 and X.shape==(325,14),"FIXED_325_EVENT_FEATURE_POPULATION")
    train=featureKnown&known&(week<6)&(due<TRAIN_END-2*3600000)
    cal=featureKnown&known&(week>=6)&(week<9)&(due<CAL_END-2*3600000)
    test=np.flatnonzero(week>=9)
    need(train.sum()>=MIN_TRAIN and cal.sum()>=MIN_CAL and len(test)==100,
         "SOURCE_LABEL_TRAIN_CAL_NOT_FINANCE_ELIGIBLE")
    models=[];scored={}
    samples=[]
    for variant in ("FULL","BASE"):
        cols=frozen_cols(variant)
        for side in (1,-1):
            y=np.array([row["labels"]["adverse",side] or 0.
                        for row in rows])
            beta=ridge(X[train],y[train],cols)
            r=y[cal]-pred(X[cal],cols,beta)
            quant=quantile16(r)
            forecast=pred(X[test],cols,beta)
            models.append(dict(variant=variant,side=side,
                columns=list(cols),coefficients=beta.tolist(),
                calibrationResidualQuantiles=quant.tolist(),
                trainedCount=int(train.sum()),
                calibratedCount=int(cal.sum()),
                maturedThrough=int(max(due[cal]))))
            for j,i in enumerate(test):
                scored[(int(t[i]),variant,side)]=dict(mean=float(forecast[j]),
                    quantile=quant.tolist(),
                    calibrationThrough=int(max(due[cal])))
                if len(samples)<24:
                    samples.append(dict(variant=variant,side=side,
                        features=X[i].tolist(),columns=list(cols),
                        coefficients=beta.tolist(),expected=float(forecast[j])))
    diagnostic={}
    for variant in ("FULL","BASE"):
        pair=[s for s in models if s["variant"]==variant]
        economic=[]
        for i in test:
            row=rows[i]
            sides=[scored[(row["t"],variant,side)] for side in (1,-1)]
            score=[x["mean"]-.5*max(0.,-float(np.mean(np.sort(
                    np.asarray(x["quantile"])+x["mean"])[:4]))) for x in sides]
            action=1 if score[0]>max(score[1],0) else -1 if score[1]>max(score[0],0) else 0
            economic.append(dict(week=row["week"]+1,action=action,
                score=max(0.,*score),realizedAdverseNetEur=row["labels"].get(("adverse",action))
                   if action else None,
                originalQuoteKnown=row["quoted"]["entry"] is not None
                     and row["quoted"]["exit"] is not None))
        diagnostic[variant]=dict(
            predictedPositiveActions=sum(x["action"]!=0 for x in economic),
            originalCostedLabelsKnown=int(sum(x["originalQuoteKnown"] for x in economic)),
            chronologicalWeeks={str(w):dict(
                proposed=sum(x["week"]==w and x["action"]!=0 for x in economic),
                labelKnown=sum(x["week"]==w and x["originalQuoteKnown"] for x in economic))
                for w in range(10,14)})
    return dict(models=models,originalModelParityInput=samples,
        firstExposedEvaluationWeek=10,lastExposedEvaluationWeek=13,
        sourceTrainKnown=int(train.sum()),sourceCalibrationKnown=int(cal.sum()),
        sourceEvaluationScheduled=100,sourceEvaluationLabelKnown=int(sum(
            known[i] for i in test)),sourceEvaluationFeatureKnown=int(sum(
            featureKnown[i] for i in test)),
        sideBySideEconomicInformation=diagnostic,
        independentConfirmation=False),scored

def risk_tail(mean,quantiles):
    values=np.sort(np.asarray(quantiles,float)+float(mean))
    tail=max(0.,-float(np.mean(values[:4])))
    return dict(score=float(mean)-.5*tail,risk=max(.01,3*tail),
        scenarioEur=[float(v) for v in values])

def native_financial_input(rows,predict,scenario,units,step,minMargin):
    arr=[];allQuotes=[];census=Counter();unfunded=[]
    for row in rows:
        if row["week"]<9:continue
        census["evaluationScheduled"]+=1
        t=row["t"];q0=row["quoted"]["entry"];qz=row["quoted"]["exit"]
        if row["features"] is None:
            census["featureUnknown"]+=1;continue
        if q0 is None:
            census["entryQuoteUnknown"]+=1;continue
        if qz is None:census["futureExitQuoteUnknown"]+=1
        else:
            census["futureExitQuoteKnown"]+=1
            for side in (1,-1):
                val=row["labels"][scenario,side]
                if val is not None:unfunded.append(dict(side=side,at=t,week=row["week"]+1,modeledEuro=val))
        allQuotes.append(q0)
        if qz is not None:allQuotes.append(qz)
        for variant in ("FULL","BASE"):
            sides=[predict.get((t,variant,side)) for side in (1,-1)]
            if any(s is None for s in sides):
                census["modelUnknown_"+variant]+=1;continue
            need(all(s["calibrationThrough"]<t-2*3600000 for s in sides),
                 "MODEL_CALIBRATION_NOT_MATURED")
            risks=[risk_tail(s["mean"],s["quantile"]) for s in sides]
            arr.append(dict(At=t+src.DECISION_DELAY+1,
                ExitAt=t+src.DECISION_DELAY+src.EXIT_DELAY,
                Symbol="ETHUSD",Variant=variant,
                CalibratedThrough=max(s["calibrationThrough"] for s in sides),
                MinUnits=str(units),StepUnits=str(step),
                MinMarginEur=str(minMargin),
                MeanAdverseEur=[s["mean"] for s in sides],
                ActionScore=[s["score"] for s in risks],
                RiskEur=[s["risk"] for s in risks],
                ScenarioNetEur=[s["scenarioEur"] for s in risks]))
            census["actionScorePositive_"+variant]+=int(max(s["score"] for s in risks)>0)
    need(census["evaluationScheduled"]==100,"NATIVE_EVAL_100_CLOCK_POPULATION")
    unique={}
    for quote in allQuotes:
        key=(quote["At"],quote["Symbol"])
        need(key not in unique,"DUPLICATE_ORIGINAL_NATIVE_QUOTE_TIME")
        unique[key]=quote
    inp=dict(Start=EVAL_START,End=END,Scenario=scenario,
        Quotes=[q for k,q in sorted(unique.items())],
        Offers=arr)
    return inp,dict(census),unfunded

def fail_public(report):
    RESULT.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")

def main():
    need(FROZEN.exists() and "FROZEN" in FROZEN.read_text(),
         "EXACT_PRECODE_ECONOMIC_PROTOCOL_UNAVAILABLE")
    rows,contract,margin,sourceReceipt,census=src.make_source_population()
    report,models=fit_and_score(rows)
    output=dict(schema="MXM_ENE1_AUTHENTIC_NEW_DIRECT_NET_ETH_VOL_REGIME_RESEARCH_V1",
        originalRunId=os.environ.get("GITHUB_RUN_ID"),
        protocolSha256=hashlib.sha256(FROZEN.read_bytes()).hexdigest(),
        sourceCodeSha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        originAuthenticity=sourceReceipt,sourceCensus=census,
        originalScheduledClocks=325,predictiveDirectNetEur=report,
        costModelOnly=True,brokerHistoricalNetEur=None,
        independentConfirmation=False,qualified=False,ordersSubmitted=0,
        cloudActivated=False,newBrokerRequests=0,
        cxl1TradingPolicyEvaluated=False,closedStudyReruns=0)
    fail_public(output)
    dll="src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
    dotnet=os.environ.get("ENE1_DOTNET","dotnet")
    with tempfile.TemporaryDirectory(prefix="ene1-original-protected-") as td:
        a=Path(td)/"native-in.json";b=Path(td)/"native-out.json"
        a.write_text(json.dumps(report["originalModelParityInput"],allow_nan=False))
        p=subprocess.run([dotnet,dll,str(a),str(b),"--ene1-parity"],
                         text=True,capture_output=True,timeout=180)
        need(p.returncode==0,"NATIVE_CSHARP_DIRECT_EUR_REGRESSION_PARITY")
        output["nativeModelParity"]=json.loads(b.read_text())
        for scenario in ("central","adverse"):
            facts,census,unfunded=native_financial_input(rows,models,scenario,
                D(contract.minVolume)/100,D(contract.stepVolume)/100,margin)
            a.write_text(json.dumps(facts,allow_nan=False,separators=(",",":")))
            output["nativeInput_"+scenario+"Sha256"]=hashlib.sha256(a.read_bytes()).hexdigest()
            p=subprocess.run([dotnet,dll,str(a),str(b),"--native-ene1"],
                text=True,capture_output=True,timeout=1200)
            if p.returncode!=0:
                output["native_"+scenario]=dict(status="UNKNOWN_NATIVE_FINANCE_FAILURE",
                    stderr=p.stderr[-400:],returnCode=p.returncode)
                output["financialCensus_"+scenario]=census
                fail_public(output)
                raise RuntimeError("ENE1_NATIVE_"+scenario+"_FAILURE")
            books=json.loads(b.read_text())
            need(set(books)=={"FULL","BASE","CASH"},"NATIVE_3_COMMON_BOOKS_MISSING")
            output["financialCensus_"+scenario]=census
            output["native_"+scenario]=books
            output["unfundedAlwaysSide_"+scenario]=dict(
                knownSideQuoteLabels=len(unfunded),
                longEuroSum=sum(x["modeledEuro"] for x in unfunded if x["side"]>0),
                shortEuroSum=sum(x["modeledEuro"] for x in unfunded if x["side"]<0),
                disclaimer="DIAGNOSTIC_NOT_FINANCED_NOT_CAPITAL_NET")
            Path("ene1-native-"+scenario+".json").write_text(
                json.dumps(books,sort_keys=True,indent=2,allow_nan=False)+"\n")
            fail_public(output)
            print("ENE1_NEW_DIRECT_NET_CSHARP",scenario,json.dumps({
                name:dict(netEuro=books[name]["Scorecard"]["NetEur"],
                         fundedTrips=books[name]["Scorecard"]["CompletedRoundTrips"],
                         hard21=books[name]["Scorecard"]["Hard21AllEligibleWeeks"])
                for name in ("FULL","BASE","CASH")}),flush=True)
    output["newResearchEvaluated"]=True
    fail_public(output)
    print("ENE1_ORIGINAL_GENUINE_SOURCE_NET_RESULT_COMPLETE",
        json.dumps(dict(clocks=325,sourceCensus=census,
                        train=report["sourceTrainKnown"],
                        calibration=report["sourceCalibrationKnown"],
                        eval=report["sourceEvaluationScheduled"])),flush=True)

if __name__=="__main__":main()

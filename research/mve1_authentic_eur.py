"""MVE1 genuine original 12-asset M5 event-based predictive/economic research.

The new model is trained only on matured 26w labels, frozen selection 13w
and exposed (not independent) evaluation 13w. Original hashes and native
C# read-only quote/cost extraction are reused. No broker access or orders.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from datetime import datetime, timezone
from hashlib import sha256
from math import log, sqrt
from pathlib import Path
from statistics import NormalDist, mean, stdev
import json
import os
import numpy as np

from .multiscale_conditional_research import recover, extract_costs
from .integrated_predictive_funded import cost_context
from .mve1_event_interaction import TAGS, COLUMNS, build_events, label_after_original_intent, sign
from .mve1_multitarget_model import (
    MODEL_VARIANTS, SCORERS, fit_all_multitarget, normal_cdf,
    admitted_research_opportunity, diagnostic_eur,
)

PROTOCOL=Path("research/mve1_protocol.json")
OUT=Path("mve1-original-12asset-multivariate-predictive-economic.json")
M5=300000
Z_FAMILY=NormalDist().inv_cdf(1-.05/12)
WEEK=7*24*3600000


def need(v,why):
    if not v:
        raise ValueError("MVE1_"+why)


def qvalues(x):
    if not x:
        return None
    a=np.asarray(x,dtype=float)
    return {str(k):round(float(np.percentile(a,k)),6) for k in (5,50,95)}


def weekly_paired_lower(changes,phase_start,num_weeks=13):
    means=[]
    for w in range(num_weeks):
        m=changes.get(phase_start+w,{})
        # Every asset is equal weight inside the same fixed week; no
        # optimistic raw M5 signal independence.
        v=[mean(vals) for s,vals in sorted(m.items()) if vals]
        means.append(mean(v) if v else None)
    actual=[v for v in means if v is not None]
    if len(actual)<8:
        return None
    average=mean(actual)
    spread=stdev(actual)/sqrt(len(actual)) if len(actual)>1 else float("inf")
    return {"weeksCovered":len(actual),
            "weekMeanImprovement":round(average,8),
            "bonferroniLower":round(average-Z_FAMILY*spread,8),
            "chronologicalWeekMeans":[None if v is None else round(v,8) for v in means],
            "selectedAsIndependentHoldout":False}


def predictions_all(phase_rows,fit):
    """Numpy batched, never touches outcomes to compute model inference."""
    if not phase_rows:
        return {}
    array=np.asarray([r["features"] for r in phase_rows],dtype=np.float64)
    x=np.clip((array-fit["avg"])/fit["std"],-5.,5.)
    x[:,0]=1.
    output={}
    for name,model in fit["variants"].items():
        a=x[:,model["indices"]]
        pred=a@model["beta"]
        # Ridge posterior conditional-mean error, NOT future return noise.
        xx=np.einsum("ni,ij,nj->n",a,model["inverse"],a,optimize=True)
        err=np.sqrt(np.maximum(0.,xx))[:,None]*np.sqrt(model["residualVariance"])[None,:]
        residual=np.sqrt(model["residualVariance"])
        output[name]={"est":pred,"se":err,"sigma":residual}
    return output


def causal_prediction_tuple(row,k,prediction):
    variant=prediction["FULL_INTERACTIONS"]
    est=variant["est"][k]
    err=variant["se"][k]
    sigma=variant["sigma"]
    # Present same known predecision normalized forecast, no label usage.
    up=normal_cdf(float(est[0])/max(1e-6,sigma[0]))
    return {"target":est,"meanSE":err,"pathResidualSD":sigma,
            "probUp":up,
            "volExpansionProb":float(np.clip(est[3],0.,1.))}


def selection_performance(rows,fit,phase,p,h):
    prefix=(p["scope"]["calendarStart"])
    phase_start=(26 if phase=="selection" else 39)
    pred=predictions_all(rows,fit)
    cost_input=None
    usable=[i for i,r in enumerate(rows) if r["known"]]
    missing=len(rows)-len(usable)
    stats={}
    tags=defaultdict(lambda:{"n":0,"modelSq":[],"zeroSq":[],"momentumSq":[],
                             "brier":[],"upExcursionAbs":[],"downExcursionAbs":[]})
    regimes=defaultdict(lambda:{"n":0,"modelSq":[],"momentumSq":[],
                                "actualVolExpansion":[]})
    by_model_week=defaultdict(lambda:defaultdict(lambda:defaultdict(list)))
    brier={}
    for k in usable:
        row=rows[k]
        yy=row["target"][0]
        baseline=.25*row["r12"]/max(1e-8,row["vol5"]*sqrt(h))
        for name,v in pred.items():
            error=float(v["est"][k,0])-yy
            by_model_week[name][(row["t"]-prefix)//WEEK][row["s"]].append(error*error)
        by_model_week["MOMENTUM"][(row["t"]-prefix)//WEEK][row["s"]].append((baseline-yy)**2)
        by_model_week["ZERO"][(row["t"]-prefix)//WEEK][row["s"]].append(yy*yy)
        full=pred["FULL_INTERACTIONS"]["est"][k]
        p_up=normal_cdf(float(full[0])/max(1e-6,pred["FULL_INTERACTIONS"]["sigma"][0]))
        sq=(float(full[0])-yy)**2
        for z,flag in enumerate(row["tags"]):
            if flag:
                rec=tags[TAGS[z]]
                rec["n"]+=1;rec["modelSq"].append(sq)
                rec["zeroSq"].append(yy*yy)
                rec["momentumSq"].append((baseline-yy)**2)
                rec["brier"].append((p_up-float(yy>0))**2)
                rec["upExcursionAbs"].append(abs(float(full[1])-row["target"][1]))
                rec["downExcursionAbs"].append(abs(float(full[2])-row["target"][2]))
        rg=regimes[row["regime"]]
        rg["n"]+=1;rg["modelSq"].append(sq)
        rg["momentumSq"].append((baseline-yy)**2)
        rg["actualVolExpansion"].append(row["target"][3])
    for name,v in pred.items():
        if usable:
            y=np.asarray([rows[i]["target"] for i in usable])
            pred_targets=v["est"][usable,:]
            up_prediction=np.asarray([normal_cdf(float(a)/max(1e-6,v["sigma"][0]))
                                      for a in pred_targets[:,0]])
            p_event=(y[:,0]>0).astype(float)
            errors=(pred_targets-y)
            stats[name]={
                "numberWithMaturedLabels":len(usable),
                "meanNormalizedReturnSquaredError":float(np.mean(errors[:,0]**2)),
                "returnBrier":float(np.mean((up_prediction-p_event)**2)),
                "returnDirectionalAccuracy":float(np.mean(np.sign(pred_targets[:,0])==np.sign(y[:,0]))),
                "upExcursionMeanAbsoluteError":float(np.mean(np.abs(errors[:,1]))),
                "downExcursionMeanAbsoluteError":float(np.mean(np.abs(errors[:,2]))),
                "volatilityTransitionBrier":float(np.mean((np.clip(pred_targets[:,3],0,1)-y[:,3])**2)),
                "forecastVolExpansionMean":float(np.mean(np.clip(pred_targets[:,3],0,1))),
                "realizedVolExpansionMean":float(np.mean(y[:,3])),
            }
        else:
            stats[name]={"numberWithMaturedLabels":0}
    ys=np.asarray([rows[i]["target"] for i in usable]) if usable else np.zeros((0,4))
    baseBrier=(fit["unconditionalDirectionUp"]-ys[:,0].__gt__(0))**2 if usable else []
    baseline={
        "unconditionalZeroNormalizedReturnMSE":float(np.mean(ys[:,0]**2)) if usable else None,
        "momentumNormalizedReturnMSE":float(np.mean([
            (.25*r["r12"]/max(1e-8,r["vol5"]*sqrt(h))-r["target"][0])**2
            for r in rows if r["known"]
        ])) if usable else None,
        "historicalTrainOnlyDirectionPrior":fit["unconditionalDirectionUp"],
        "trainOnlyDirectionBrier":float(np.mean(baseBrier)) if usable else None,
        "trainOnlyUpExcursionMeanAbsoluteError":float(np.mean(
            np.abs(ys[:,1]-fit["unconditionalTargets"][1]))) if usable else None,
        "trainOnlyDownExcursionMeanAbsoluteError":float(np.mean(
            np.abs(ys[:,2]-fit["unconditionalTargets"][2]))) if usable else None,
        "trainOnlyVolExpansionBrier":float(np.mean(
            (ys[:,3]-fit["unconditionalVolExpansion"])**2)) if usable else None,
    }
    def paired(a,b):
        delta=defaultdict(lambda:defaultdict(list))
        ma=by_model_week[a];mb=by_model_week[b]
        for week,assets in ma.items():
            for sym,vals in assets.items():
                other=mb.get(week,{}).get(sym,[])
                if len(other)!=len(vals):
                    raise ValueError("MVE1_MODEL_REFERENCE_NOT_COMMON_SAMPLES")
                delta[week][sym]=[v-u for v,u in zip(other,vals)]
        return weekly_paired_lower(delta,phase_start)
    comparisons={
        "fullVsZero":paired("FULL_INTERACTIONS","ZERO"),
        "fullVsFixedOwnMomentum":paired("FULL_INTERACTIONS","MOMENTUM"),
        "fullVsSimpleOwnPrice":paired("FULL_INTERACTIONS","SIMPLE_OWN_PRICE"),
        "fullVsNoPeer":paired("FULL_INTERACTIONS","NO_PEER_COMPONENT"),
        "fullVsNoInteractions":paired("FULL_INTERACTIONS","NO_INTERACTION_TERMS")
    }
    def summaries(original):
        out={}
        for k,z in sorted(original.items()):
            out[k]={
                "n":z["n"],
                "meanNormalizedReturnMSE":round(mean(z["modelSq"]),8) if z["modelSq"] else None,
                "meanZeroMSE":round(mean(z["zeroSq"]),8) if z.get("zeroSq") else None,
                "meanMomentumMSE":round(mean(z["momentumSq"]),8) if z["momentumSq"] else None,
                "directionalBrier":round(mean(z["brier"]),8) if z.get("brier") else None,
                "upExcursionMAE":round(mean(z["upExcursionAbs"]),8) if z.get("upExcursionAbs") else None,
                "downExcursionMAE":round(mean(z["downExcursionAbs"]),8) if z.get("downExcursionAbs") else None,
                "realizedVolatilityExpansionRate":round(mean(z["actualVolExpansion"]),8) if z.get("actualVolExpansion") else None,
            }
        return out
    full=stats["FULL_INTERACTIONS"]
    selpass=(phase=="selection" and len(usable)>100 and
             full["returnBrier"]<baseline["trainOnlyDirectionBrier"] and
             comparisons["fullVsFixedOwnMomentum"] is not None and
             comparisons["fullVsSimpleOwnPrice"] is not None and
             comparisons["fullVsFixedOwnMomentum"]["bonferroniLower"]>0 and
             comparisons["fullVsSimpleOwnPrice"]["bonferroniLower"]>0 and
             full["upExcursionMeanAbsoluteError"]<=baseline["trainOnlyUpExcursionMeanAbsoluteError"] and
             full["downExcursionMeanAbsoluteError"]<=baseline["trainOnlyDownExcursionMeanAbsoluteError"])
    return {
        "phase":phase,"horizonM5":h,
        "fixedAllObservableEvents":len(rows),"forwardKnown":len(usable),
        "forwardUnknown":missing,"forwardLabelCoverage":len(usable)/len(rows) if rows else None,"baseline":baseline,
        "modelVariants":stats,"matchedWeeklyPredictiveDifferences":comparisons,
        "eventTypeDescriptiveOverlapsAllowed":summaries(tags),
        "causalVolatilityRegime":summaries(regimes),
        "strictModelPredictiveSelectionPass":bool(selpass),
        "_predictions":pred,
    }


def conditional_policy(rows,fit,cost,phase,h,forecast_batch):
    """Research-only selection/abstention, no C# funding claims or fills.

    ALL predecision clock intents computed without inspecting labelKnown;
    outcomes are looked up only after schedule is frozen.
    """
    schedule={}
    state_count=Counter()
    by_event=Counter()
    by_s=Counter()
    for i,row in enumerate(rows):
        prediction=causal_prediction_tuple(row,i,forecast_batch)
        q=admitted_research_opportunity(row,prediction,cost.get(row["s"]))
        state_count[q["state"]]+=1
        if q["state"]=="RESEARCH_OPPORTUNITY_UNFUNDED":
            by_s[row["s"]]+=1
            for j,flag in enumerate(row["tags"]):
                if flag:by_event[TAGS[j]]+=1
            t=row["t"]
            best=schedule.get(t)
            val=(q["conservativeNetEur"],row["s"])
            if best is None or val[0]>best[0][0] or (val[0]==best[0][0] and val[1]<best[0][1]):
                schedule[t]=(val,i,q)
    emitted=[]
    data_missing=0
    central=[];adverse=[];own=[]
    favorable=[];unfavorable=[];probabilities=[]
    categories=Counter();regimes=Counter();symbols=Counter()
    weekly=defaultdict(list)
    for t,(_,i,q) in sorted(schedule.items()):
        row=rows[i]
        symbols[row["s"]]+=1
        regime=row["regime"];regimes[regime]+=1
        categories["continuation" if sign(row["r24"])==q["side"] else "reversal"]+=1
        if not row["known"]:
            data_missing+=1
            continue
        c=cost[row["s"]]
        a=diagnostic_eur(row,q["side"],c,"adverse")
        z=diagnostic_eur(row,q["side"],c,"central")
        sign_baseline=sign(row["r12"])
        old=diagnostic_eur(row,sign_baseline,c,"adverse")
        if a is None or z is None or old is None:
            data_missing+=1;continue
        adverse.append(a);central.append(z);own.append(old)
        favored=(row["futureHighBps"] if q["side"]>0 else -row["futureLowBps"])
        against=(-row["futureLowBps"] if q["side"]>0 else row["futureHighBps"])
        favorable.append(favored)
        unfavorable.append(against)
        probabilities.append(q["probUp"])
        week=(t-1762128000000)//WEEK
        weekly[week].append(a)
        emitted.append({"eventClock":t,"instrument":row["s"],
                        "side":q["side"],"horizonM5":h,
                        "adverseConditionalNetEur":round(a,7)})
    scheduled=len(schedule)
    return {
        "phase":phase,"horizonM5":h,
        "allCausalEventForecastDecisionStates":dict(state_count),
        "candidateIntentByInstrument":dict(by_s),
        "candidateIntentByObservableEventTagsMayOverlap":dict(by_event),
        "onePerExactClockUnfundedConditionalIntents":scheduled,
        "pricedConditionalIntents":len(adverse),
        "missingForwardOutcomesOfAlreadySelected":data_missing,
        "centralConditionalEurSumOverlappingNotFunded":round(sum(central),7),
        "adverseConditionalEurSumOverlappingNotFunded":round(sum(adverse),7),
        "sameChosenClocksFixedOwnMomentumAdverseEurSum":round(sum(own),7),
        "incrementalAdverseEurVsSameEventMomentum":round(sum(adverse)-sum(own),7),
        "adverseEurPerPricedIntentMean":round(mean(adverse),7) if adverse else None,
        "positiveNetIntents":sum(x>0 for x in adverse),
        "negativeNetIntents":sum(x<0 for x in adverse),
        "modeledGrossMaxFavorableBpsQuantiles":qvalues(favorable),
        "modeledGrossMaxAdverseBpsQuantiles":qvalues(unfavorable),
        "forecastDirectionProbabilityQuantiles":qvalues(probabilities),
        "intentContinuationVsReversal":dict(categories),
        "predecisionVolRegimes":dict(regimes),
        "chosenSymbols":dict(symbols),
        "weeklyAdverseModeledEurNotPortfolio":[round(sum(weekly.get(w,[])),7)
            for w in range(26 if phase=="selection" else 39,
                           39 if phase=="selection" else 52)],
        "brokerOriginalBidAskAtAllEventTimes":False,
        "singleCommonEur300NativeLedgerNotRun":True,
        "tradesFullyFinancedAndClosed":None,
        "continuousFloatingDrawdownProven":False,
        "hard21SystemicProven":False,
        "noPromotionBasedOnThisCounterfactual":True
    }


def main():
    p=json.loads(PROTOCOL.read_text())
    need(p["status"]=="FROZEN_UNSCORED" and p["id"]=="MVE1","FROZEN_PROTOCOL")
    need(tuple(p["continuousFeatures"]["columns"])==COLUMNS,
         "FEATURE_COLUMNS_NOT_AS_FROZEN")
    actual_bars={}
    original_receipts=[]
    observed_cost=[]
    for original,folder in zip(p["originalSources"],("bdp-source","aip-source")):
        b,decoded,audit=recover(Path(folder),original["run"],original["sha256"],
                                original["originalSchema"],original["protocol"])
        need(set(b["bars"]).isdisjoint(actual_bars),"REUSED_SOURCE_COLLISION")
        actual_bars.update(b["bars"])
        costs,cov=extract_costs(b,decoded)
        observed_cost.extend(costs)
        original_receipts.append({"originalRun":original["run"],
             "sourceEvidence":audit,"originalCostCoverage":cov,
             "sourceOriginalOnlyNoEconomicRerun":True})
        print("MVE1_ORIGINAL_SOURCE_VERIFIED",original["study"],len(b["bars"]),flush=True)
    need(set(actual_bars)==set(p["scope"]["universe"]),
         "ORIGINAL_12_INSTRUMENT_UNIVERSE_CHANGED")
    raw_count=sum(len(x) for x in actual_bars.values())
    need(raw_count==836087,"AUTHENTIC_M5_SOURCE_TOTAL_CHANGED")
    # Feature-only future-blind pass first.
    events,sorted_rows,contiguous,availability,source_by_asset=build_events(actual_bars,p)
    train_events=[r for r in events if r["t"]<p["scope"]["trainEnd"]]
    print("MVE1_ORIGINAL_FEATURE_ONLY",json.dumps({
       "observed":availability,"trainEvents":len(train_events)},sort_keys=True),flush=True)
    all_targets=label_after_original_intent(events,sorted_rows,contiguous,p)
    original_costs=[v for v in observed_cost if v["At"]<p["scope"]["trainEnd"]]
    cost=cost_context(original_costs)
    # Native original C# quote and current contract min-margin extraction
    # supports conditional EUR but NO historical event bid/ask price fill.
    fits={}
    for h,rows in all_targets.items():
        fits[h]=fit_all_multitarget(rows,train_events,h)
        print("MVE1_TRAIN_FIT",h,fits[h]["trainCount"],flush=True)
    predictive=[]
    economic=[]
    for h,rows in all_targets.items():
        fit=fits[h]
        for phase in ("selection","exposed_audit"):
            subset=[r for r in rows if r["phase"]==phase]
            summary=selection_performance(subset,fit,phase,p,h)
            econ=conditional_policy(subset,fit,cost,phase,h,
                                    summary.pop("_predictions"))
            predictive.append(summary)
            economic.append(econ)
            print("MVE1_PREDICTIVE_AND_EUR",json.dumps({
              "h":h,"phase":phase,"events":len(subset),
              "known":summary["forwardKnown"],
              "fullMSE":summary["modelVariants"]["FULL_INTERACTIONS"].get("meanNormalizedReturnSquaredError"),
              "ownMSE":summary["baseline"]["momentumNormalizedReturnMSE"],
              "selectionPass":summary["strictModelPredictiveSelectionPass"],
              "conditionalAdverseEur":econ["adverseConditionalEurSumOverlappingNotFunded"],
              "modelledIntentCount":econ["onePerExactClockUnfundedConditionalIntents"]
            },sort_keys=True),flush=True)
    passed=[x for x in predictive if x["phase"]=="selection" and
            x["strictModelPredictiveSelectionPass"]]
    if len(passed)==1:
        verdict="ONE_EXPOSED_SELECTION_PREDICTIVE_CANDIDATE_NOT_YET_EXECUTABLE"
    elif passed:
        verdict="MORE_THAN_ONE_PREDICTIVE_SELECTION_CANDIDATE_NO_EXANTE_UNIQUE_ADMISSION"
    else:
        verdict="NO_MULTIVARIATE_PREDICTIVE_MODEL_PASSED_STRICT_SELECTION"
    training_census={}
    for h,rows in all_targets.items():
        training_census[str(h)]={
            ph:{"events":sum(x["phase"]==ph for x in rows),
                "known":sum(x["phase"]==ph and x["known"] for x in rows),
                "unknown":sum(x["phase"]==ph and not x["known"] for x in rows)}
            for ph in ("training","selection","exposed_audit")}
    result={
      "schema":"MXM_MVE1_ORIGINAL_SYSTEMATIC_MULTI_TARGET_EVENT_PREDICTIVE_EUR_V1",
      "originalFrozenProtocolSha256":sha256(PROTOCOL.read_bytes()).hexdigest(),
      "originalReadbackJobId":int(os.environ["GITHUB_RUN_ID"]),
      "originalReadOnlyPepperstoneData":True,
      "originalSourcesReadback":original_receipts,
      "originalSourceM5BarCount":raw_count,
      "originalM5BarsByAsset":source_by_asset,
      "originalObservedCausalEventCoverage":availability,
      "eventTypeCounterOverlaps":{k:sum(int(e["tags"][i]) for e in events)
            for i,k in enumerate(TAGS)},
      "continuousFeatureCount":len(COLUMNS),
      "continuousColumns":list(COLUMNS),
      "globallyExposed52WeekDevelopment":True,
      "exposedPeriodsNotIndependentConfirmation":True,
      "trainSelectionExposedCensus":training_census,
      "trainingFitReceiptsByHorizon":{
         str(h):{"maturedTrainSamples":fit["trainCount"],
                 "symbolSamples":fit["trainSymbolCount"],
                 "modelVariants":list(MODEL_VARIANTS),
                 "trainingOnlyNormalization":True,
                 "ridgeLambda":32.,
                 "conditionalTargetResidualSD":{
                    name:np.sqrt(v["residualVariance"]).tolist()
                    for name,v in fit["variants"].items()},
                 "originalM5ScalePriceValidation":True}
         for h,fit in fits.items()},
      "originalCostContextCount":len(observed_cost),
      "originalTrainingCostContextCount":len(original_costs),
      "currentTermCostBySymbol":cost,
      "predictiveComparisonPanels":predictive,
      "opportunitySelectionAndEurPanels":economic,
      "selectionModelFamiliesPassedStrictEvidence":len(passed),
      "verdict":verdict,
      "conditionalEurNotActualHistoricFills":True,
      "modelledOverlappingEurNotNativeFundedPortfolioEur":True,
      "nativeSingle300EuroRiskAndLedgerNotCertified":True,
      "minimumTwelveMonthsIndependentConfirmationNotCertified":True,
      "retuning":False,"newBrokerRequests":0,
      "closedModelsCalled":0,"ordersSubmitted":0,
      "cloudActivated":False,"independentConfirmation":False,
    }
    OUT.write_text(json.dumps(result,sort_keys=True,indent=2,allow_nan=False,default=float)+"\n")
    print("MVE1_AUTHENTIC_MULTIVARIATE_ORIGINAL_RESULT",json.dumps({
      "sourceBars":raw_count,"eventIntents":len(events),
      "trainMatured":{h:fits[h]["trainCount"] for h in fits},
      "selectionQualified":len(passed),"verdict":verdict,
      "selectionPanels":[{
         "h":x["horizonM5"],"mse":x["modelVariants"]["FULL_INTERACTIONS"].get("meanNormalizedReturnSquaredError"),
         "priorMSE":x["baseline"]["momentumNormalizedReturnMSE"],
         "predictivePass":x["strictModelPredictiveSelectionPass"]}
         for x in predictive if x["phase"]=="selection"],
      "selectionConditionalEur":[{
         "h":e["horizonM5"],"adverse":e["adverseConditionalEurSumOverlappingNotFunded"],
         "selected":e["onePerExactClockUnfundedConditionalIntents"]}
         for e in economic if e["phase"]=="selection"],
      "actualFundedEur":None,"brokerOrders":0,
    },sort_keys=True),flush=True)


if __name__=="__main__":
    main()

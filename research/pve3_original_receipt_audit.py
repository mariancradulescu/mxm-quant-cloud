"""PVE3 RECEIPT-ONLY economic reconciliation, no source, no learner, no replay.

Reads first original PVE3 public JSON to verify denominators, matched chronology,
native cash/risk contracts and two prespecified price comparisons. This NEVER
calls the PVE3 source/fit/native evaluators. Confidence bounds are descriptive
week-block normal approximations with Bonferroni for two primary comparisons,
NOT independent confirmation.
"""
from __future__ import annotations
import json,math,sys
from statistics import NormalDist,mean,stdev
from pathlib import Path

def need(cond,why):
    if not cond:raise ValueError("PVE3_RECEIPT_"+why)

def weekly_audit(receipt):
    data=receipt["predictive"]
    weeks=data["weekly"];paired=data["pairedWeekly"]
    need(len(paired)==26 and len(weeks)==52,"EXACT_26_PAIRED_WEEKS")
    for i,p in enumerate(paired):
        week=i+27
        rows=[r for r in weeks if r["week"]==week]
        need(len(rows)==2 and {r["variant"] for r in rows}=={"FULL","OWN"},
             "FROZEN_VARIANT_WEEK_POPULATION")
        a,b=(next(r for r in rows if r["variant"]==v) for v in ("FULL","OWN"))
        need(a["labelKnown"]==b["labelKnown"] and
             a["featureKnown"]==b["featureKnown"],"UNMATCHED_PREDICTIVE_LABELS")
        need(abs((b["normalizedPriceMse"]-a["normalizedPriceMse"])-
             p["fullMinusOwnPriceMseBenefit"])<1e-12,
             "FULL_OWN_PAIRED_MSE_DISAGREES")
        need(abs((a["zeroPriceMse"]-a["normalizedPriceMse"])-
             p["fullMinusZeroPriceMseBenefit"])<1e-12,
             "FULL_ZERO_PAIRED_MSE_DISAGREES")
    z=NormalDist().inv_cdf(1-.05/(2*2))
    result={}
    for comparator,key in (("OWN","fullMinusOwnPriceMseBenefit"),
                           ("ZERO_PRICE","fullMinusZeroPriceMseBenefit")):
        benefits=[p[key] for p in paired]
        mu=mean(benefits)
        sd=stdev(benefits)
        lower=mu-z*sd/math.sqrt(len(benefits))
        result[comparator]=dict(weeklyPairedBenefits=benefits,
            totalWeeks=len(benefits),beneficialWeeks=sum(v>0 for v in benefits),
            meanBenefit=mu,first13Mean=mean(benefits[:13]),
            last13Mean=mean(benefits[13:]),bonferroniDescriptiveLower95=lower,
            positiveLower=lower>0,
            warning="TWO_PRESPECIFIED_COMPARISONS_WEEK_BLOCK_NORMAL_SERIAL_DEPENDENCE_ALL_PROJECT_HISTORY_EXPOSED")
    return result

def financial_audit(receipt):
    out={}
    for scenario in ("central","adverse"):
        book=receipt.get("native_"+scenario)
        if not isinstance(book,dict):
            out[scenario]=dict(status="UNKNOWN_NO_NATIVE_BOOK",error=receipt.get("native_"+scenario))
            continue
        policies={}
        for policy in ("FULL","OWN","CASH"):
            b=book[policy];score=b["Scorecard"]
            count=b["Completed"]
            weeks=score["FundedCompletionsByIsoWeek"]
            need(len(weeks)==26 and sum(weeks.values())==count,
                 "HARD21_WEEKS_COMPLETIONS_MISMATCH")
            need(not b["Qualified"] and not b["IndependentConfirmation"] and b["NoOrders"],
                 "FORBIDDEN_PROMOTION_OR_TRADING")
            need(score["CompletedRoundTrips"]==count,"SCORECARD_TRIP_IDENTITY")
            if count==0:
                need(all(score[x] is None for x in (
                    "NetExpectancyPerTradeEur","WinRate","MeanWinEur","MeanLossEur",
                    "ProfitFactor","PayoffRatio","MeanRiskMultiple",
                    "ExpectedShortfall5PctEur","WorstTradeEur")),
                    "NO_TRADE_METRIC_MUST_BE_NA")
                if score["FullFinancialOutcomeKnown"]:
                    need(score["NetEur"]==0,"CASH_ONLY_NET_NOT_ZERO")
            if score["FullFinancialOutcomeKnown"]:
                need(score["NetEur"]==b["Book"]["ClosedNetEur"],
                     "NATIVE_SCORECARD_CASH_NET_IDENTITY")
            policies[policy]=dict(
                completed=count,netEur=score["NetEur"],
                returnOnCapital=score["ReturnOnCapital"],
                maximumSampledFloatingDd=score["MaximumSampledFloatingDrawdown"],
                hard21=score["Hard21AllEligibleWeeks"],
                weeklyComplete=weeks,unknown=score["UnknownOrNotApplicable"],
                scorecard=score)
        fn=policies["FULL"]["netEur"];on=policies["OWN"]["netEur"]
        out[scenario]=dict(policies=policies,
            incrementalFullVsOwnEur=None if fn is None or on is None else fn-on,
            incrementalFullVsCashEur=None if fn is None else fn,
            allMetricsAreOriginalNativeReceipts=True)
    return out

def audit(receipt):
    need(receipt["schema"]=="MXM_PVE3_NEW_ORIGINAL_DISTRIBUTIONAL_PRICE_AND_ECONOMIC_RESEARCH_V1",
         "ORIGINAL_RECEIPT_SCHEMA")
    need(receipt["sourceBars"]==836087 and len(receipt["sourceSymbols"])==12,
         "ORIGINAL_SOURCE_CENSUS")
    need(len(receipt["weekCensus"])==52,"EXACT_ALL_SOURCE_WEEKS")
    need(receipt["independentConfirmation"] is False and
         receipt["qualified"] is False and
         receipt["ordersSubmitted"]==0 and receipt["cloudActivated"] is False,
         "FORBIDDEN_PROJECT_PROMOTION")
    return dict(schema="MXM_PVE3_RECEIPT_ONLY_INDEPENDENTLY_REPRODUCIBLE_DIAG_V1",
        originalRunId=receipt["executionRunId"],
        protocolSha256=receipt["protocolSha256"],
        originalSourceBars=receipt["sourceBars"],
        globallyExposedDevelopment=True,
        predictivePairedBonferroni=weekly_audit(receipt),
        nativeFinancialScorecard=financial_audit(receipt),
        historicalBrokerFillsCertified=False,
        confirmationIndependent=False,
        sourceRetouched=False,modelsRerun=False,ordersSubmitted=0)

def main():
    need(len(sys.argv)==3,"USAGE_ORIGINAL_PUBLIC_JSON_OUTPUT_JSON")
    source=Path(sys.argv[1]);dest=Path(sys.argv[2])
    original=json.loads(source.read_text())
    result=audit(original)
    dest.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("PVE3_RECEIPT_ONLY_RECONCILED",json.dumps(dict(
        originalRunId=result["originalRunId"],
        comparisons={k:dict(beneficialWeeks=v["beneficialWeeks"],
                           mean=v["meanBenefit"],lower=v["bonferroniDescriptiveLower95"])
                     for k,v in result["predictivePairedBonferroni"].items()})),flush=True)

if __name__=="__main__":main()

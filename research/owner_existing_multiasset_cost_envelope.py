"""Independent public-receipt multi-asset capital/cost envelope.

Runs NOW solely on previously authenticated *published source receipts*.
No broker requests, sealed-source readback, rescoring or model prediction.
Observations and limited sampling are preserved. Future admissibility
requires real joint exposure, actual fills and unexposed NET evidence.
"""
from __future__ import annotations
import json
from decimal import Decimal as D
from pathlib import Path
from itertools import combinations

SOURCES={
 "cma1":Path("docs/CMA1_AUTHENTIC_CONTRACT_TERMS_20261108.json"),
 "cma2":Path("docs/CMA2_AUTHENTIC_COST_SURFACE_20261108.json"),
 "xua1":Path("docs/XUA1_AUTHENTIC_RESULT_20261108.json")
}
CAPITAL=D(300)
STRESS_EQUITY=D(210)
CATEGORIES={
 "NatGas":"energy","SpotBrent":"energy","SpotCrude":"energy",
 "USDX":"index","JPYX":"index","HK50":"index","JPN225-F":"index",
 "AMD.US":"equity","ETHUSD":"crypto"
}
def dc(x):return D(str(x))
def raw_sources():
    return {k:json.loads(p.read_text()) for k,p in SOURCES.items()}
def decimal_text(d):return format(d,"f")
def actual_receipt_envelope(sources=None):
    o=sources or raw_sources()
    c=o["cma1"];d=o["cma2"];x=o["xua1"]
    if (c["originalSourceReadbackVerified"] is not True or
        d["evidence"]["originalRawRequestResponseIndependentDecryptReadback"] is not True or
        x["provenance"]["originalLivePepperstoneEURCryptographicBindingRechecked"] is not True):
        raise ValueError("OWNER_CURRENT_PUBLIC_SOURCE_NOT_AUTHENTICATED")
    rows={}
    for symbol,rec in c["instruments"].items():
        units=dc(rec["minimumUnits"])
        source_fee_usd=dc(c["sharedCurrentContract"]["commissionPerLotPerSideUsdFromNativeCurrentModel"])*2*units/dc(c["sharedCurrentContract"]["lotSizeUnits"])
        rows[symbol]={"symbol":symbol,"class":"fx",
            "minMarginEur":decimal_text(dc(rec["currentMinMarginEur"])),
            "contractSource":"CMA1_2026_11_04_ORIGINAL",
            "sourceMinUnits":str(rec["minimumUnits"]),
            "sourceRoundTripCommissionUsdAtMinUnits":decimal_text(source_fee_usd),
            "sourceOriginalBidAskPairedCount":None,
            "sourceObservedSpreadBps":None,
            "costResultClass":"PARTIAL_CONTRACT_FEE_ONLY_NO_EUR_FX_ROUTE",
            "brokerActualNetEur":None}
    for symbol,rec in d["candidates"].items():
        rows[symbol]={"symbol":symbol,"class":CATEGORIES[symbol],
            "minMarginEur":decimal_text(dc(rec["minMarginEur"])),
            "contractSource":"CMA2_2026_11_05_ORIGINAL",
            "sourceMinUnits":str(rec["minVolumeUnits"]),
            "sourceRoundTripCommissionUsdAtMinUnits":None,
            "sourceOriginalBidAskPairedCount":rec["observedFreshQuotePairs"],
            "sourceObservedSpreadBps":rec["observedSpreadBps"],
            "costResultClass":"ONE_OR_ZERO_FRESH_BID_ASK_NOT_REPRESENTATIVE",
            "brokerActualNetEur":None}
    for symbol,rec in x["sourceAndCurrentTerms"]["contractAndCostByMarket"].items():
        # GBPJPY is already in CMA1. Keep source-date contract margin as
        # recorded there, append XUA1 descriptive spread/cost evidence only.
        if symbol not in rows:
            rows[symbol]={"symbol":symbol,
                "class":CATEGORIES.get(symbol,"fx"),
                "minMarginEur":decimal_text(dc(rec["currentMinimumMarginEur"])),
                "contractSource":"XUA1_AS_OBSERVED_ORIGINAL",
                "sourceMinUnits":str(rec["minimumVolume"]),
                "sourceRoundTripCommissionUsdAtMinUnits":None,
                "sourceOriginalBidAskPairedCount":rec["pairedBidAsk"],
                "sourceObservedSpreadBps":str(rec["originalMedianSpreadBps"]),
                "costResultClass":"XUA1_CONDITIONAL_MODEL_NO_HISTORICAL_FILLS",
                "brokerActualNetEur":None}
        else:
            rows[symbol]["additionalXua1QuoteCount"]=rec["pairedBidAsk"]
            rows[symbol]["additionalXua1MedianSpreadBps"]=str(rec["originalMedianSpreadBps"])
        rows[symbol]["xua1HistoricalCurrentTermAdverseCostModelBps"]=str(rec["adverseModeledBps"])
        rows[symbol]["xua1NegativeExactStrategyVerdictRetained"]=True
    if len(rows)!=18:
        raise ValueError("OWNER_SOURCE_UNIVERSE_CHANGED")
    margins={s:dc(v["minMarginEur"]) for s,v in rows.items()}
    # These are purely static independent *source-date minimum* margin sums,
    # not broker financing, concentration, or floating DD30 guarantees.
    specified=[
        ["NatGas","USDX","AMD.US"],
        ["NatGas","USDX"],
        ["USDX","AMD.US"],
        ["NatGas","AMD.US"],
        ["NatGas","HK50","AMD.US"],
        ["SpotCrude","HK50","AMD.US"],
        ["NatGas","AMD.US","EURJPY"],
        ["USDX","GBPJPY","AMD.US"],
    ]
    def sum_case(names):
        t=sum((margins[s] for s in names),D(0))
        return {"symbols":names,"observedAsOfMinMarginSumEur":decimal_text(t),
            "staticHeadroomAtEur300BeforeFeesEur":decimal_text(CAPITAL-t),
            "illustrativeEquityAfter30PercentDrawdownEur":"210",
            "stress210StaticHeadroomBeforeCostsEur":decimal_text(STRESS_EQUITY-t),
            "stress210SourceDateMinimumMarginFits":t<=STRESS_EQUITY,
            "feasibilityCertified":False}
    configurations=[sum_case(names) for names in specified]
    # Three independent classes; no optimization by model returns since
    # no such outcomes are observed. Lowest-margin is NOT best or promoted.
    feasible_by_class=[]
    for names in combinations(sorted(rows),3):
        distinct={rows[s]["class"] for s in names}
        if len(distinct)==3 and sum(margins[s] for s in names)<=STRESS_EQUITY:
            feasible_by_class.append(names)
    paired_unknown=[s for s,row in rows.items()
                    if row["sourceOriginalBidAskPairedCount"] is None or
                       row["sourceOriginalBidAskPairedCount"]<3]
    illustrative_hurdles={}
    for s in ("NatGas","USDX","AMD.US"):
        row=rows[s]
        spread=dc(row["sourceObservedSpreadBps"] or 0)
        if row["sourceOriginalBidAskPairedCount"]!=1:
            raise ValueError("OWNER_CMA2_SOURCE_SNAPSHOT_CHANGED")
        variable_fee_bps=D(0)
        if s=="AMD.US":
            # USD200/share illustrative price and 0.1 share at original
            # exact USD0.02 per side minimum: USD0.04/$20 = 20bps.
            fee=d["candidates"][s]
            unit=dc(fee["minVolumeUnits"])
            price=D(200)
            one=max(dc(fee["commissionRateWire"])/D(10)**8*
                        unit/dc(fee["lotSizeUnits"]),
                    dc(fee["minCommissionWire"])/D(10)**8)
            variable_fee_bps=one*2/(unit*price)*10000
        central=D("1.5")*spread+variable_fee_bps+D(".5")
        adverse=D(2)*spread+variable_fee_bps+D(1)
        illustrative_hurdles[s]={
          "originalSingleSourceObservedSpreadBps":decimal_text(spread),
          "minVolumeCommissionAtIllustrativeAmdUsd200Bps":decimal_text(variable_fee_bps),
          "illustrativeCentralGrossBreakEvenBps":decimal_text(central),
          "illustrativeAdverseGrossBreakEvenBps":decimal_text(adverse),
          "notObservedHistoricalCostDistribution":True,
          "notPredictiveGrossOrNet":True}
    return {
      "schema":"MXM_OWNER_CASH_COST_PORTFOLIO_ENVELOPE_PUBLIC_RECEIPTS_V1",
      "source":"ORIGINAL_PUBLISHED_GENUINE_CMA1_CMA2_XUA1_READ_ONLY_RECEIPTS",
      "sourceArtifactsUnchanged":True,
      "originalClosedXua1OrSfx1OutcomesRescored":False,
      "newBrokerRequests":0,
      "distinctContractSymbolsReviewed":len(rows),
      "sourceClassCounts":{k:sum(v["class"]==k for v in rows.values())
         for k in sorted({v["class"] for v in rows.values()})},
      "contracts":{k:rows[k] for k in sorted(rows)},
      "currentSourceQuoteCoverageUnknownOrUnderThreeBySymbol":sorted(paired_unknown),
      "selectedActualSourceMarginConfigurations":configurations,
      "distinctThreeClassCombinationsUnderIllustrativeStress210":len(feasible_by_class),
      "illustrativeCurrentSingleSnapshotCostHurdles":illustrative_hurdles,
      "economicConclusions":{
        "usdxOneSourceMinPositionConsumesCapitalPercent":decimal_text(margins["USDX"]/CAPITAL*100),
        "usdxOneSourceMinPositionConsumesStressEquityPercent":decimal_text(margins["USDX"]/STRESS_EQUITY*100),
        "minMarginNatGasPlusUsdxAtStressLeavesEur":decimal_text(STRESS_EQUITY-margins["NatGas"]-margins["USDX"]),
        "minMarginAllThreeMcs1Exceeds210StressEquityEur":decimal_text(
            sum(margins[s] for s in ["NatGas","USDX","AMD.US"])-STRESS_EQUITY),
        "allThreeMcs1Under300AtSourceDate":sum(margins[s] for s in ["NatGas","USDX","AMD.US"])<CAPITAL,
        "conditionalUnder30PercentFloatingDrawdownAllThreeMarginSafe":False,
        "observedCostSnapshotsEnoughToCertifyHistoricalNet":False,
        "futureH1OrM15GrossAndNetPredictiveEdgeEur":None,
        "brokerFundedRoundTripsFromThisScreen":0,
        "actualPortfolioNetEur":None,
        "systemHard21Certified":False,
        "globalFloatingDD30Certified":False,
        "independentConfirmation":False,
        "ordersSubmitted":0,
        "cloudActivated":False}
    }
if __name__=="__main__":
    print(json.dumps(actual_receipt_envelope(),indent=2,sort_keys=True))

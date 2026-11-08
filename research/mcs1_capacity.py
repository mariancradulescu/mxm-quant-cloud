"""SOURCE-DATED capacity precheck, not a financed EUR300 strategy or NET.

Verifies preregistered market/schedule capacity from original CMA2 broker
terms BEFORE seeking new target OHLCV. No outcome access; no broker calls.
"""
from __future__ import annotations
from decimal import Decimal as D
from pathlib import Path
import json

P=Path("research/mcs1_protocol.json")
C=Path("docs/CMA2_AUTHENTIC_COST_SURFACE_20261108.json")
def inspect_capacity(protocol=None,broker=None):
    p=protocol or json.loads(P.read_text())
    b=broker or json.loads(C.read_text())
    if p["id"]!="MCS1" or p["status"]!="REGISTERED_UNSCORED" or \
       p["source"]["readOnlyBrokerRequestsExact"]!=324:
        raise ValueError("MCS1_FREQUENCY_PROTOCOL_DRIFT")
    fam=p["families"]
    names=[x["symbol"] for x in fam]
    if len(fam)!=3 or len(set(names))!=3 or \
       set(names)!={"NatGas","USDX","AMD.US"}:
        raise ValueError("MCS1_FREQUENCY_SYMBOL_DRIFT")
    week={}
    for f in fam:
        hours=f["decisionUtcHours"]
        if len(hours)!=len(set(hours)) or any(not 0<=x<24 for x in hours):
            raise ValueError("MCS1_FREQUENCY_INVALID_HOURS")
        days=f["weekdays"]
        if len(days)!=len(set(days)) or any(x not in
             ("MON","TUE","WED","THU","FRI","SAT","SUN") for x in days):
            raise ValueError("MCS1_FREQUENCY_INVALID_DAYS")
        week[f["symbol"]]=len(hours)*len(days)
    total=sum(week.values())
    if total!=105 or p["frequencyPrescreen"]["combinedUpperBound"]!=total:
        raise ValueError("MCS1_FREQUENCY_NO_HARDCODED_CAPACITY")
    margins={s:D(b["candidates"][s]["minMarginEur"]) for s in names}
    units={s:D(b["candidates"][s]["minVolumeUnits"]) for s in names}
    if any(v<=0 or v>=300 for v in margins.values()) or any(v<=0 for v in units.values()):
        raise ValueError("MCS1_MARGIN_OR_MINIMUM_VOLUME_NOT_FEASIBLE")
    combined=sum(margins.values())
    required=21
    # A SINGLE authentic observed CMA2 spread per symbol, never a historical
    # p50/p90, can only define a HYPOTHETICAL minimum price hurdle.
    spreads={s:D(b["candidates"][s]["observedSpreadBps"]) for s in names}
    if any(v<0 for v in spreads.values()):raise ValueError("BROKER_SPREAD_NOT_OBSERVED")
    # Illustrative AMD quoted price 200 USD/share; original minimum fee
    # two sides USD0.02 each for minimum 0.1 share -> 20bps at USD200.
    hypotheticalAmdUsdPrice=D(200)
    amdUnits=units["AMD.US"]
    minUsdFee=D(b["candidates"]["AMD.US"]["minCommissionWire"])/D(10)**8
    oneSideUsd=max(
       D(b["candidates"]["AMD.US"]["commissionRateWire"])/D(10)**8 *
       amdUnits/D(b["candidates"]["AMD.US"]["lotSizeUnits"]),
       minUsdFee)
    illustrativeCommission={s:D(0) for s in names}
    illustrativeCommission["AMD.US"]=D(20000)*oneSideUsd/(amdUnits*hypotheticalAmdUsdPrice)
    central={s:spreads[s]*D("1.5")+illustrativeCommission[s]+D(".5") for s in names}
    adverse={s:spreads[s]*D(2)+illustrativeCommission[s]+D(1) for s in names}
    return {
      "source":"AUTHENTIC_CMA2_ORIGINAL_CONTRACT_AS_OBSERVED_2026_11_05",
      "economicProtocolFrozenBeforePriceOutcomes":True,
      "nominalEligibleH1DecisionClocksPerWeekByInstrument":week,
      "nominalMaximumWeeklyDecisions":total,
      "requiredSystemicFinancedClosedRoundTripsPerEligibleWeek":required,
      "minimumSignalAndFundingConversionRateFromNominalClocks":
          str(D(required)/D(total)),
      "realHistoricalSignalFrequencies":None,
      "sourceWindowCoverage":None,
      "sourceObservedMinimumMarginsEur":{k:str(v) for k,v in margins.items()},
      "observedMinimumUnits":{k:str(v) for k,v in units.items()},
      "illustrativeSingleSpreadConditionalMinimumGrossHurdlesBps":{
        key:{"sourceObservedOneSpreadBps":str(spreads[key]),
             "illustrativeCentralCostBps":str(central[key]),
             "illustrativeAdverseCostBps":str(adverse[key])}
        for key in names},
      "illustrativeAmdSharePriceUsdForFeeBpsOnly":str(hypotheticalAmdUsdPrice),
      "oneObservedQuotePairPerSymbolNotHistoricalDistribution":True,
      "theseAreNotRealModelNetOrPredictiveOutcomes":True,
      "sumOfSourceDateOneMinPositionMarginsEur":str(combined),
      "hypotheticalHeadroomBeforeCommissionsAndFloatingDrawdownEur":str(D(300)-combined),
      "sumOfMarginsDoesNotProveSimultaneousFinancing":True,
      "capitalInitialProspectiveEur":300,
      "historicalTariffContinuityNotProven":True,
      "actualBidAskFillEurNet":None,
      "actualFundedPositions":0,
      "systemicHARD21NotProven":True,
      "DD30NotProven":True,
      "originalBrokerOrdersSubmitted":0
    }
if __name__=="__main__":
    print(json.dumps(inspect_capacity(),indent=2,sort_keys=True))

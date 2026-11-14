"""SFV1 original Pepperstone fixed multi-class spot/-F feasibility, not a predictor.

Original account requests are SCOPE_VIEW allowlisted. The source is sealed before
any current-contract and causal quote-spread public summary is calculated.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal as D
from hashlib import sha256
import json
import os
from pathlib import Path

from .cma2_cost_preflight import asof_spread
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT
from .ctrader_proto import OpenApiMessages_pb2 as m, OpenApiModelMessages_pb2 as e
from .ctrader_transport import StdlibCTraderTransport
from .custody import seal_new
from .custody_new import checked_public
from .decode import decode_side
from .full_inventory_pipeline import _raw_record
from .guard import require_read_only_request
from .owner_readonly_auth import authenticate

PROTOCOL = Path("research/SFV1_TERM_PAIRS_ECONOMIC_FEASIBILITY.md")
PAIRS = (
    ("JPN225", "JPN225-F"),
    ("NatGas", "NatGas-F"),
    ("US500", "US500-F"),
    ("AUS200", "AUS200-F"),
    ("USDX", "USDX-F"),
)
CLOCKS = (
    "2026-11-12T08:15:00+00:00",
    "2026-11-12T14:45:00+00:00",
    "2026-11-12T19:45:00+00:00",
)
CLOCK_MS = tuple(int(datetime.fromisoformat(t).timestamp() * 1000) for t in CLOCKS)
LIMIT = 100
EXPECTED_CEILING_ALL_PRESENT = 3+len(PAIRS)*2*(2+2*len(CLOCK_MS))
assert EXPECTED_CEILING_ALL_PRESENT == 83

def need(value, tag):
    if not value: raise ValueError(tag)

def money(margin, field):
    if margin is None or not margin.HasField("moneyDigits") or len(margin.margin) != 1:
        return None
    value = getattr(margin.margin[0], field)
    if not (0 <= margin.moneyDigits <= 12 and value >= 0):
        return None
    return str(D(value) / (D(10) ** margin.moneyDigits))

def classify_pair(spot, future):
    """Only a necessary single-volume capital screen, NOT a funded portfolio."""
    if spot is None or future is None:
        return {"state":"UNKNOWN_MISSING_SYMBOL"}
    if not spot["enabledCurrent"] or not future["enabledCurrent"]:
        return {"state":"UNKNOWN_NOT_ENABLED"}
    if spot["tradingMode"] is None or future["tradingMode"] is None:
        return {"state":"UNKNOWN_TRADING_MODE_WIRE"}
    if spot["tradingMode"]!=0 or future["tradingMode"]!=0:
        return {"state":"NOT_CURRENTLY_OPENABLE_TRADING_MODE"}
    if spot["shortSellingAllowed"] is None or future["shortSellingAllowed"] is None:
        return {"state":"UNKNOWN_SHORT_SELLING_CONTRACT"}
    if not spot["shortSellingAllowed"] and not future["shortSellingAllowed"]:
        return {"state":"NO_TWO_LEG_LONG_SHORT_ORIENTATION"}
    if spot["marginBuyEur"] is None or future["marginBuyEur"] is None or (
       spot["marginSellEur"] is None or future["marginSellEur"] is None):
        return {"state":"UNKNOWN_ORIGINAL_MARGIN"}
    sm = max(D(spot["marginBuyEur"]),D(spot["marginSellEur"]))
    fm = max(D(future["marginBuyEur"]),D(future["marginSellEur"]))
    total = sm+fm
    result = {
        "spotMinMarginEur":str(sm),
        "futureMinMarginEur":str(fm),
        "sumSingleLegMinMarginEur":str(total),
        "headroomVs300Eur":str(D(300)-total),
        "headroomVs210Eur":str(D(210)-total),
        "futureLegAloneBelow300Eur":fm<D(300),
        "simplePairSumBelow300Eur":total<D(300),
        "simplePairSumBelow210Eur":total<D(210),
    }
    result["oneLegShortAllowedSpot"]=spot["shortSellingAllowed"]
    result["oneLegShortAllowedFuture"]=future["shortSellingAllowed"]
    result["state"] = ("NECESSARY_CAPITAL_SCREEN_FAILED" if
        sm>=300 or fm>=300 or total>=300 else
        "ONLY_PRELIMINARY_MARGIN_FEASIBLE_TERM_CONVENTION_UNKNOWN")
    return result

def summary(public_rows, count, cipher_digest, protocol_digest):
    byname={row["symbol"]:row for row in public_rows}
    results=[]
    for spot_name,fut_name in PAIRS:
        pair=classify_pair(byname.get(spot_name),byname.get(fut_name))
        results.append({
            "spot":spot_name,"candidateFutureLabel":fut_name,
            **pair,
            "futureExpiryTimestampFromOpenApiContract":None,
            "historicalContinuousRollProtocolVerified":False,
            "sameUnderlyingAndCashFlowConventionCertified":False,
            "nativeCloudFuturesSettingsChecked":False,
            "historicalCostDistributionOrNetEur":None,
        })
    return {
        "schema":"MXM_SFV1_AUTHENTIC_CURRENT_SPOT_FORWARD_CONTRACT_PREFLIGHT",
        "originalPepperstoneEurAccountVerified":True,
        "sourceAuthenticatedOriginalReadOnlyRequestCount":count,
        "originalSourceSealedBeforePublicScoring":True,
        "originalSealedSourceSha256":cipher_digest,
        "protocolSha256":protocol_digest,
        "historicalInventoryOriginalPublicSha256":"1b15d08fa14bf67239acf31109b1f0f11093df7fe5c1b04fcbf1bff893040c5a",
        "historicalInventoryOriginalRunId":41939175379,
        "fixedClocksUtc":CLOCKS,
        "selectedMarkets":public_rows,
        "pairNecessaryCapitalScreens":results,
        "limitOriginalSourceQueries":LIMIT,
        "costsAsOfCurrentNotHistorical":True,
        "noNewPriceReturnModel":True,
        "futuresExpiryAndRolloverSourceUnknown":True,
        "developmentOnlyNotIndependent":True,
        "actualFundedPortfolioEurNet":None,
        "ordersSubmitted":0,
        "cloudTradingActivated":False,
        "oauthReauthorized":False,
    }

def main():
    run = os.environ["GITHUB_RUN_ID"]
    need(run.isdigit(),"SFV1_RUN_ID")
    recipient = checked_public(Path("new-recipient-output"),run)
    t=StdlibCTraderTransport()
    raw=[]
    count=0
    prices={}
    contracts={}
    assets={}
    roster={}

    def req(q,klass,allow_empty_ticks=False):
        nonlocal count
        need(count<LIMIT,"SFV1_READONLY_REQUEST_CEILING")
        require_read_only_request(q)
        resp=t.request(q)
        count+=1
        need(resp.IsInitialized() and
             int(resp.ctidTraderAccountId)==int(q.ctidTraderAccountId)==int(account),
             "SFV1_ORIGINAL_RESPONSE_ACCOUNT")
        if (allow_empty_ticks and type(q) is m.ProtoOAGetTickDataReq and
            type(resp) is m.ProtoOAErrorRes and resp.errorCode=="NO_QUOTES"):
            raw.append(_raw_record(q,resp))
            return None
        need(type(resp) is klass,"SFV1_ORIGINAL_RESPONSE_TYPE")
        raw.append(_raw_record(q,resp))
        return resp

    try:
        account=authenticate(t)
        need(sha256(sha256(f"ctrader-account:{account}".encode()).hexdigest().encode()).hexdigest()
             ==HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT,
             "SFV1_HISTORIC_ACCOUNT_FINGERPRINT")
        trader=req(m.ProtoOATraderReq(ctidTraderAccountId=account),m.ProtoOATraderRes)
        aset=req(m.ProtoOAAssetListReq(ctidTraderAccountId=account),m.ProtoOAAssetListRes)
        assets={x.assetId:x.name for x in aset.asset}
        need(trader.trader.HasField("brokerName") and
             "pepperstone" in trader.trader.brokerName.casefold() and
             assets.get(trader.trader.depositAssetId)=="EUR",
             "SFV1_NOT_ORIGINAL_BROKER_EUR")
        syms=req(m.ProtoOASymbolsListReq(ctidTraderAccountId=account,
                 includeArchivedSymbols=False),m.ProtoOASymbolsListRes)
        roster={s.symbolName:s for s in syms.symbol if s.HasField("symbolName")}
        selected=[name for pair in PAIRS for name in pair]
        need(len(selected)==len(set(selected)),"SFV1_DUPLICATE_TARGETS")

        # ZERO outcome-driven fallback: missing/disabled symbols are UNKNOWN.
        for name in selected:
            light=roster.get(name)
            if light is None or not light.HasField("enabled") or not light.enabled:
                prices[name]={"symbol":name,"enabledCurrent":False,
                    "state":"UNKNOWN_MISSING_OR_DISABLED","marginBuyEur":None,
                    "marginSellEur":None,"indicativeSpreads":[]}
                continue
            sid=int(light.symbolId)
            detail=req(m.ProtoOASymbolByIdReq(ctidTraderAccountId=account,
                       symbolId=[sid]),m.ProtoOASymbolByIdRes)
            need(len(detail.symbol)==1 and detail.symbol[0].symbolId==sid,
                 "SFV1_EXACT_SYMBOL_CONTRACT_BINDING")
            c=detail.symbol[0]
            contracts[name]=c
            minimum = (int(c.minVolume) if c.HasField("minVolume") and c.minVolume>0
                       else None)
            margin=None
            if minimum is not None:
                margin=req(m.ProtoOAExpectedMarginReq(
                    ctidTraderAccountId=account,symbolId=sid,
                    volume=[minimum]),m.ProtoOAExpectedMarginRes)
                need(len(margin.margin)==1 and
                     margin.margin[0].volume==minimum,"SFV1_MIN_MARGIN_VOLUME_BINDING")
            one={"symbol":name,"enabledCurrent":True,
                 "quoteAsset":assets.get(light.quoteAssetId),
                 "brokerDescription":light.description if light.HasField("description") else None,
                 "currentCategoryId":light.symbolCategoryId if light.HasField("symbolCategoryId") else None,
                 "tradingMode":int(c.tradingMode) if c.HasField("tradingMode") else None,
                 "shortSellingAllowed":bool(c.enableShortSelling) if c.HasField("enableShortSelling") else None,
                 "minimumUnits":str(D(minimum)/100) if minimum is not None else None,
                 "stepUnits":str(D(c.stepVolume)/100) if c.HasField("stepVolume") else None,
                 "lotSizeUnits":str(D(c.lotSize)/100) if c.HasField("lotSize") else None,
                 "marginBuyEur":money(margin,"buyMargin"),
                 "marginSellEur":money(margin,"sellMargin"),
                 "commissionType":int(c.commissionType) if c.HasField("commissionType") else None,
                 "preciseTradingCommissionRateWire":int(c.preciseTradingCommissionRate) if c.HasField("preciseTradingCommissionRate") else None,
                 "preciseMinCommissionWire":int(c.preciseMinCommission) if c.HasField("preciseMinCommission") else None,
                 "minCommissionType":int(c.minCommissionType) if c.HasField("minCommissionType") else None,
                 "minCommissionAsset":c.minCommissionAsset if c.HasField("minCommissionAsset") else None,
                 "pnlConversionFeeRateWire":int(c.pnlConversionFeeRate) if c.HasField("pnlConversionFeeRate") else None,
                 "swapLongWire":c.swapLong if c.HasField("swapLong") else None,
                 "swapShortWire":c.swapShort if c.HasField("swapShort") else None,
                 "swapPeriodHours":c.swapPeriod if c.HasField("swapPeriod") else None,
                 "swapTimeUtcMin":c.swapTime if c.HasField("swapTime") else None,
                 "swapCalcType":int(c.swapCalculationType) if c.HasField("swapCalculationType") else None,
                 "currentScheduleZone":c.scheduleTimeZone if c.HasField("scheduleTimeZone") else None,
                 "currentScheduleCount":len(c.schedule),
                 "brokerExpiryAndRollKnown":False,
                 "indicativeSpreads":[]}
            prices[name]=one
            for clock in CLOCK_MS:
                sides={};complete=True
                for side in (e.BID,e.ASK):
                    q=req(m.ProtoOAGetTickDataReq(ctidTraderAccountId=account,
                           symbolId=sid,type=side,
                           fromTimestamp=clock-60000,toTimestamp=clock),
                           m.ProtoOAGetTickDataRes,allow_empty_ticks=True)
                    if q is not None and q.HasField("hasMore") and not q.hasMore:
                        sides[side]=decode_side(q.tickData,clock-60000,clock)
                    else:
                        sides[side]=[]
                        complete=False
                one["indicativeSpreads"].append(
                    {"clockUtcMs":clock,**asof_spread(
                         sides[e.BID],sides[e.ASK],clock,
                         20000,20000,complete=complete)})
        need(count<=83,"SFV1_UNEXPECTED_BROKER_SCOPE")
    finally:
        t.close()

    # Original protobuf and original decoded research evidence sealed first.
    private=json.dumps({
        "schema":"MXM_SFV1_ORIGINAL_TERM_SYMBOL_CONTRACTS_PRIVATE",
        "originalRun":run,
        "sourceOriginalReadOnlyRequests":raw,
        "sourceOriginalReadOnlyRequestCount":count,
        "selectedCurrentContractsWithAsOfQuotes":prices,
        "accountIdentityBoundOriginalPepperstoneEur":True,
        "noBrokerOrderRequests":True
    },sort_keys=True,separators=(",",":")).encode()
    cipher=seal_new(private,recipient,run)
    Path("sfv1-original-protected.v2.enc").write_bytes(cipher)
    receipt=summary([prices[name] for pair in PAIRS for name in pair],
                    count,sha256(cipher).hexdigest(),sha256(PROTOCOL.read_bytes()).hexdigest())
    receipt["originalPlaintextSha256"]=sha256(private).hexdigest()
    Path("sfv1-original-public-capital-screen.json").write_text(
        json.dumps(receipt,indent=2,sort_keys=True,allow_nan=False)+"\n")
    print("SFV1_ORIGINAL_CONTRACT_ONLY",json.dumps({
        "readOnly":count,
        "pairScreens":[{"symbol":x["candidateFutureLabel"],
                        "state":x["state"],"futureMargin":x.get("futureMinMarginEur"),
                        "pairSum":x.get("sumSingleLegMinMarginEur")}
                       for x in receipt["pairNecessaryCapitalScreens"]],
        "noFinancialAlphaScore":True},sort_keys=True),flush=True)

if __name__=="__main__":
    main()

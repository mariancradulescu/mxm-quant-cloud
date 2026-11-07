"""CMA1: independent tariff/rollover recovery from the frozen ORIGINAL CCP1 ciphertext.

No network, Open API transport, predictor, portfolio scorer or order endpoint.
Rates are source-date *contract terms*, not fills or historical fee continuity.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
from .carry_cycle_preflight import audit as original_ccp1_audit
from .custody import unseal_new
from .ctrader_proto import OpenApiMessages_pb2 as m

SOURCE_RUN = 41774823771
SOURCE_PATH = Path("ccp1-original-source/source.envelope.json")
RECEIPT = Path("docs/CCP1_AUTHENTIC_PREFLIGHT.json")
PROTOCOL = Path("research/carry_cycle_preflight_protocol.json")
OUTPUT = Path("cma1-current-terms-public.json")
NEW_NONLEGACY = ("EURJPY", "AUDJPY", "NZDJPY", "NZDUSD")

def need(condition, code):
    if not condition:
        raise ValueError("CMA1_" + code)

def sha(blob):
    return hashlib.sha256(blob).hexdigest()

def opt(c, name):
    return getattr(c, name) if c.HasField(name) else None

def contract_terms(c, light, margin_rows):
    """Report *explicit* Open API contract fields; absence is UNKNOWN, not zero.

    Current commission currency/rate are reported as wire values and scale, rather
    than silently converting via fabricated EUR FX rates. Rollover dates are not
    inferred from UTC midnight. Current margin != simultaneous finance proof.
    """
    need(c.symbolId == light, "SYMBOL_ID")
    mn, st, mx = (opt(c, name) for name in ("minVolume", "stepVolume", "maxVolume"))
    need(mn is not None and st is not None and mx is not None and
         0 < mn <= mx and st > 0, "INVALID_VOLUME_GRID")
    commission_type = opt(c, "commissionType")
    min_type = opt(c, "minCommissionType")
    rate = opt(c, "preciseTradingCommissionRate")
    minimum = opt(c, "preciseMinCommission")
    conversion = opt(c, "pnlConversionFeeRate")
    need(rate is None or rate >= 0, "NEGATIVE_COMMISSION")
    need(minimum is None or minimum >= 0, "NEGATIVE_FEE_FLOOR")
    need(conversion is None or conversion >= 0, "NEGATIVE_CONVERSION")
    need(commission_type is None or commission_type in (1, 2, 3, 4),
         "UNKNOWN_COMMISSION_TYPE")
    need(min_type is None or min_type in (1, 2), "UNKNOWN_FEE_MINIMUM_TYPE")
    swap_period = opt(c, "swapPeriod")
    swap_time = opt(c, "swapTime")
    need(swap_period is None or swap_period > 0, "INVALID_SWAP_PERIOD")
    need(swap_time is None or 0 <= swap_time < 1440, "INVALID_SWAP_CLOCK")
    # Never conflate a protobuf default with an observed zero tariff or default
    # crossover day with an independently verified broker rollover policy.
    wire_complete = (rate is not None and minimum is not None and
                     commission_type is not None and min_type is not None and
                     (min_type != 1 or opt(c, "minCommissionAsset") is not None))
    return {
        "tradingModeExplicit": opt(c, "tradingMode"),
        "minVolumeUnits": str(mn / 100),
        "stepVolumeUnits": str(st / 100),
        "maxVolumeUnits": str(mx / 100),
        "lotSizeUnits": None if opt(c, "lotSize") is None else str(c.lotSize / 100),
        "commissionTypeExplicit": commission_type,
        "preciseCommissionRateWire": rate,
        "commissionRateScale": 100000 if commission_type == 3 else 100000000,
        "preciseMinCommissionWire": minimum,
        "minCommissionTypeExplicit": min_type,
        "minCommissionAssetExplicit": opt(c, "minCommissionAsset"),
        "pnlConversionFeeRateBasisPointsExplicit": conversion,
        "allRequiredCommissionWireFieldsExplicit": wire_complete,
        "swapCalculationTypeExplicit": opt(c, "swapCalculationType"),
        "swapLongExplicit": opt(c, "swapLong"),
        "swapShortExplicit": opt(c, "swapShort"),
        "swapRollover3DaysExplicit": opt(c, "swapRollover3Days"),
        "swapPeriodHoursExplicit": swap_period,
        "swapTimeMinutesFromUtcMidnightExplicit": swap_time,
        "skipSwapPeriodsExplicit": opt(c, "skipSWAPPeriods"),
        "chargeSwapAtWeekendsExplicit": opt(c, "chargeSwapAtWeekends"),
        "swapFreeRolloverCommissionWire": opt(c, "rolloverCommission"),
        "rolloverCommission3DaysExplicit": opt(c, "rolloverCommission3Days"),
        "scheduleTimeZoneExplicit": opt(c, "scheduleTimeZone"),
        "scheduleIntervals": len(c.schedule),
        "currentQueriedMarginsEur": margin_rows,
        "brokerRoundTripFeeEur": None,
        "reasonEurUnknown": "REQUIRES_CAUSAL_PRICE_SIZE_AND_QUOTE_TO_EUR_CONVERSION",
        "historicalTariffContinuityCertified": False,
        "longHorizonFundingCertified": False,
        "slippageAssumed": False
    }

def recover(encrypted, private_key):
    receipt = json.loads(RECEIPT.read_text())
    p = json.loads(PROTOCOL.read_text())
    need(receipt["SourceRunId"] == SOURCE_RUN, "ORIGINAL_SOURCE_RUN")
    need(sha(encrypted) == receipt["SourceCiphertextSha256"], "SOURCE_CIPHERTEXT_HASH")
    need(sha(PROTOCOL.read_bytes()) == receipt["ProtocolSha256"], "ORIGINAL_PROTOCOL_HASH")
    original = json.loads(unseal_new(encrypted, private_key.encode(), str(SOURCE_RUN)))
    reread = original_ccp1_audit(original, p)
    need(reread == original["auditReceipt"] and reread["requests"] == 39,
         "RAW_ACCOUNT_AND_CONTRACT_BINDING")
    need(original["schema"] == "mxm-carry-cycle-source-v1", "SOURCE_CLASS")
    need(set(original["symbols"]) == set(p["universe"]), "ORIGINAL_UNIVERSE")
    rows = {}
    for name in p["universe"]:
        entry = original["symbols"][name]
        raw = original["raw"][entry["contractIndex"]]
        need(raw["type"] == "ProtoOASymbolByIdRes", "CONTRACT_PROTO_TYPE")
        import base64
        reply = m.ProtoOASymbolByIdRes()
        reply.ParseFromString(base64.b64decode(raw["protobuf"], validate=True))
        need(len(reply.symbol) == 1, "SINGLE_CONTRACT")
        rows[name] = contract_terms(reply.symbol[0], entry["symbolId"],
                                    entry["marginGrid"])
    return {
        "schema": "MXM_CMA1_ORIGINAL_CCP1_CONTRACT_FEE_ROLLOVER_READBACK_V1",
        "authority": "OWNER_SPEC_v2.0_2026-11-08",
        "sourceRunId": SOURCE_RUN,
        "sourceCiphertextSha256": sha(encrypted),
        "originalSourceReadbackVerified": True,
        "originalBrokerAccountBoundByCCP1": True,
        "sourceWasAlreadyCollected": True,
        "additionalBrokerRequests": 0,
        "originalSourceNominalUtcMs": original["nominal"],
        "accountNormalSwapFlagFromWire": original["normalAccountEffective"],
        "accountSwapFreeFieldExplicit": original["swapFreeExplicitInWire"],
        "contractRows": rows,
        "newOutsidePreviously18CandidatesForSourceTriage": list(NEW_NONLEGACY),
        "nextTemporalEvidence": {
            "FXSessionRepricing": ["M15", "H4_as_regime_context"],
            "JPYMultiMarketVolatility": ["H1", "H4"],
            "noOutcomeScoring": True,
            "nativeCloudMultiTimeframeAPI": "MarketData.GetBars",
        },
        "brokerFeeIsNotAssumedSlippage": True,
        "unknownHistoricalTradingTariffsAndFunding": True,
        "noBacktestOrStudyReclassification": True,
        "fundedEurNet": None,
        "independentConfirmation": False,
        "hard21Proven": False,
        "drawdown30Proven": False,
        "ordersSubmitted": 0,
        "cloudActivated": False,
    }

def main():
    need(RECEIPT.exists() and SOURCE_PATH.exists(), "SOURCE_MISSING")
    result = recover(SOURCE_PATH.read_bytes(), os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"])
    OUTPUT.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("CMA1_RECONCILED " + json.dumps({
        "originalAccountBound": result["originalBrokerAccountBoundByCCP1"],
        "existingContracts": len(result["contractRows"]),
        "newMarketsForTriage": len(NEW_NONLEGACY),
        "newBrokerRequests": 0, "orders": 0,
        "historicalNetEur": None
    }, sort_keys=True))

if __name__ == "__main__":
    main()

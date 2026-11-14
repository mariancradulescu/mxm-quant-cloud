"""BWR1-F1 corrected exact money readback ONLY of immutable original ciphertext.

No Pepperstone authentication, transport, original requests, raw original export,
new signal, parameter or calendar. Corrects only the 25-event state predicate.
"""
from __future__ import annotations
from collections import Counter
from datetime import timedelta
from hashlib import sha256
import base64,json,os
from pathlib import Path

from .custody import unseal_new
from .ctrader_proto import OpenApiMessages_pb2 as m
from .bwr1_brent_wti_paired_eur import (
    START,WEEKS,ALL,MARKETS,first_signal,financial)

ORIGINAL_RUN="43576022822"
ORIGINAL_CIPHER="a019aaf2131173832630863d83bfa2127fb3a3d8ed6a6c22002fc42dc2b280e7"
ORIGINAL_PLAIN="df5f7f39e24921112bf89adde9aa47dccbee00f14d2b843a97860b2eb693e042"
ORIGINAL_PUBLIC="13298cd7f3fe34ff2bec865f81c66aae36e1bdedd9d73a064bca57241ab399d2"
EXPECTED_FIRST_RECEIPT_CAUSAL=25


def original_readback():
    cipher=Path("bwr1-original-source/bwr1-original-encrypted-source.v2.enc").read_bytes()
    public_bytes=Path("bwr1-original-public/bwr1-public-original-conditional-eur.json").read_bytes()
    if sha256(cipher).hexdigest()!=ORIGINAL_CIPHER or (
        sha256(public_bytes).hexdigest()!=ORIGINAL_PUBLIC):
        raise ValueError("BWR1_F1_ORIGINAL_SOURCE_OR_PUBLIC_SHA_MISMATCH")
    old=json.loads(public_bytes)
    if (old.get("schema")!="MXM_BWR1_BRENT_WTI_PAIRED_CONDITIONAL_EUR_COST_ECONOMICS"
        or old.get("originalRunId")!=int(ORIGINAL_RUN)
        or old.get("originalReadOnlyRequestsAfterAuth")!=979
        or old.get("originalSourceCipherSha256")!=ORIGINAL_CIPHER
        or old.get("originalSourcePlainSha256")!=ORIGINAL_PLAIN
        or not old.get("sourceSealedBeforeAnyPostEntryEconomicScoring")
        or old["economics"]["all52Weeks"]["states"].get(
            "CAUSAL_REJECTED_BASIS")!=EXPECTED_FIRST_RECEIPT_CAUSAL
        or old["economics"]["all52Weeks"]["pairedCompleteEurPriced"]!=0
        or old["economics"]["first26Weeks"]["states"].get(
            "CAUSAL_REJECTED_BASIS")!=13
        or old["economics"]["last26Weeks"]["states"].get(
            "CAUSAL_REJECTED_BASIS")!=12):
        raise ValueError("BWR1_F1_FIRST_PUBLIC_TECHNICAL_DEFECT_NOT_MATCHED")
    secret=os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    if not secret.strip():
        raise ValueError("BWR1_F1_ORIGINAL_INSTALLED_CUSTODY_SECRET_MISSING")
    plain=unseal_new(cipher,secret,ORIGINAL_RUN)
    if sha256(plain).hexdigest()!=ORIGINAL_PLAIN:
        raise ValueError("BWR1_F1_ORIGINAL_PLAINTEXT_SHA_MISMATCH")
    raw=json.loads(plain)
    if (raw.get("schema")!="MXM_BWR1_ORIGINAL_BRENT_WTI_CFD_SOURCE_PRIVATE"
        or raw.get("run")!=ORIGINAL_RUN
        or raw.get("originalPepperstoneEurAccountBound") is not True
        or raw.get("postEntryEconomicScoringNotStarted") is not True
        or raw.get("readonlyCallsAfterAuthentication")!=979
        or len(raw.get("originalBrokerProtobuf",[]))!=979):
        raise ValueError("BWR1_F1_ORIGINAL_DECRYPTED_SCHEMA_OR_SOURCE_CONFLICT")
    # Rebuild exact CURRENT contract terms from ORIGINAL immutable
    # cTrader protobuf response bytes. Never reconstruct missing fields
    # from assumptions, test fixtures or another broker session.
    symbols={}
    snapshots={}
    for call in raw["originalBrokerProtobuf"]:
        if call["responseType"]=="ProtoOASymbolsListRes":
            roster=m.ProtoOASymbolsListRes()
            roster.ParseFromString(base64.b64decode(call["response"],validate=True))
            for obj in roster.symbol:
                if obj.symbolName in ALL:
                    symbols[obj.symbolName]=obj.symbolId
        elif call["responseType"]=="ProtoOASymbolByIdRes":
            z=m.ProtoOASymbolByIdRes()
            z.ParseFromString(base64.b64decode(call["response"],validate=True))
            for c in z.symbol:
                if c.symbolId in snapshots:
                    raise ValueError("BWR1_F1_DUPLICATE_CONTRACT_RESPONSE")
                snapshots[c.symbolId]=c
    if len(symbols)!=3 or len(set(symbols.values()))!=3 or (
        any(v not in snapshots for v in symbols.values())):
        raise ValueError("BWR1_F1_ORIGINAL_BROKER_CONTRACT_MAPPING_UNKNOWN")
    contracts={name:snapshots[sid] for name,sid in symbols.items()}
    source=raw["decodedOriginalBarsAndQuotes"]
    if len(source)!=260:
        raise ValueError("BWR1_F1_ORIGINAL_260_WEEKDAY_SOURCE_MISSING")
    margins=raw["currentContractSnapshot"]
    for name in ALL:
        if name not in margins or margins[name].get("minimumWireVolume")!=int(contracts[name].minVolume):
            raise ValueError("BWR1_F1_ORIGINAL_VOLUME_OR_MARGIN_CONFLICT")

    # Convert canonical JSON keys back to M5 UTC close integers,
    # without any change of clock or price values.
    for wk in range(WEEKS):
        for wd in range(5):
            day=START+timedelta(weeks=wk,days=wd)
            if day.isoformat() not in source or source[day.isoformat()]["week"]!=wk:
                raise ValueError("BWR1_F1_ORIGINAL_FIXED_WEEK_CALENDAR_CONFLICT")
            for name in MARKETS:
                bars=source[day.isoformat()]["bars"][name]
                source[day.isoformat()]["bars"][name]={int(t):int(v) for t,v in bars.items()}
    intents=Counter()
    for wk in range(WEEKS):
        for wd in range(5):
            day=START+timedelta(weeks=wk,days=wd)
            signal=first_signal(day,source[day.isoformat()]["bars"])
            if signal["state"]=="CAUSAL_REJECTED_BASIS":
                intents["ALL"]+=1
                intents["FIRST" if wk<26 else "LAST"]+=1
                if len(source[day.isoformat()].get("quotes",{}))!=3:
                    raise ValueError("BWR1_F1_CAUSAL_EVENT_ORIGINAL_QUOTES_NOT_CAPTURED")
    if (intents["ALL"],intents["FIRST"],intents["LAST"])!=(25,13,12):
        raise ValueError("BWR1_F1_ORIGINAL_CAUSAL_INTENTS_CHANGED")

    results=financial(source,contracts,margins)
    if (results["all52Weeks"]["scheduledDays"]!=260 or
        results["all52Weeks"]["basisSweepIntents"]!=25 or
        results["first26Weeks"]["basisSweepIntents"]!=13 or
        results["last26Weeks"]["basisSweepIntents"]!=12 or
        "CAUSAL_REJECTED_BASIS" in results["all52Weeks"]["states"]):
        raise ValueError("BWR1_F1_CORRECTED_ECONOMIC_GATE_STILL_NOT_EXECUTED")
    return results


def main():
    outcome=original_readback()
    report={
        "schema":"MXM_BWR1_F1_EXACT_ORIGINAL_SOURCE_ONLY_TECHNICAL_MONEY_CORRECTION",
        "frozenRepairProtocolSha256":sha256(Path(
            "research/BWR1_ORIGINAL_STATE_LABEL_READBACK.md").read_bytes()).hexdigest(),
        "originalRunId":int(ORIGINAL_RUN),
        "originalSourceCipherSha256":ORIGINAL_CIPHER,
        "originalSourcePlainSha256":ORIGINAL_PLAIN,
        "originalPublicEconomicReceiptSha256":ORIGINAL_PUBLIC,
        "exactOriginal2025_2026BasisEvents":25,
        "originalPublicReceiptFinancialZerosTechnicallyInvalid":True,
        "sourceRestoredExactlyAndOriginalReceiptRetained":True,
        "statePredicateOneLiteralCorrectedOnly":True,
        "newBrokerRequests":0,
        "newSignalThresholdsEntryExits":0,
        "originalCryptoSourceReplaced":False,
        "allOutcomesHistoricalGloballyExposedDevelopment":True,
        "economics":outcome,
        "actualFundedCSharpNetEur":None,
        "continuousFloatDDCertified":False,
        "brokerRealizedNetEur":None,
        "independentChronologicalConfirmation":False,
        "ordersLiveDemo":0,"cloudTradingActivated":False,
        "oauthReauthorized":False,
        "disclosure":"Exact first protected BWR1 original source. Repair only causal state literal in original financial evaluator. Historical paired genuine BID/ASK and signed EURUSD current-tariff 0.5/2bps modeled risk net EUR, NOT filled or native funded or independently validated."
    }
    Path("bwr1-f1-corrected-original-eur-public.json").write_text(
        json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+"\n")
    a=outcome["all52Weeks"]
    print("BWR1_F1_CORRECTED_25_ORIGINAL_CAUSAL_EVENTS",
          json.dumps({"states":a["states"],"matched":a["pairedCompleteEurPriced"],
              "adverse":a["money"]["adverse"]["adaptive"],
              "firstAdverse":outcome["first26Weeks"]["money"]["adverse"]["adaptive"],
              "lastAdverse":outcome["last26Weeks"]["money"]["adverse"]["adaptive"],
              "gate":outcome["candidateEconomicGate"]}),flush=True)


if __name__=="__main__":
    main()

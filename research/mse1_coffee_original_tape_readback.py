"""Protected forensic inspection of immutable MSE1 original tape; NO replay.

Unseals original 2026 MSE1 source only inside preinstalled custody environment.
Inspects as-of quote-stage evidence (Coffee raw pairs, EURUSD raw pairs and
model-ready marks); never recalculates price, P&L, signal or score.
"""
from datetime import datetime,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
from .custody import unseal_new

ORIGINAL_RUN="43366399346"
ORIGINAL_PLAIN_SHA="068cf7a396d0cddfc59b856f95f930b7bff83eddef4c8beae556243e168c4f7e"
ORIGINAL_CIPHER_SHA="e10bec88a954d11d7a68d8079dcf382084aecf6a7cdc474e76f37db93fd1cf29"
ORIGINAL_PUBLIC_SHA="53db93ff14866b703ea77051e9859033df39e17401991d485e2323f13feb3535"
CLOCKS=(
    "2026-09-02T17:00:01.500Z",
    "2026-09-02T17:10:01.500Z",
    "2026-09-02T17:15:01.500Z",
    "2026-09-02T17:30:01.500Z",
    "2026-09-02T17:35:01.500Z",
    "2026-09-03T08:15:01.500Z",
    "2026-09-03T08:20:01.500Z",
    "2026-09-03T14:00:01.500Z",
    "2026-09-03T14:05:01.500Z",
)

def clock(value):
    return int(datetime.fromisoformat(value.replace("Z","+00:00")).timestamp()*1000)

def main():
    cipher=Path("original-mse1-encrypted/mse1-original-native-tape.v2.enc").read_bytes()
    if sha256(cipher).hexdigest()!=ORIGINAL_CIPHER_SHA:
        raise ValueError("MSE1_IMMUTABLE_ENCRYPTED_SOURCE_HASH_MISMATCH")
    original_public=Path("original-mse1-public/mse1-public.json").read_bytes()
    if sha256(original_public).hexdigest()!=ORIGINAL_PUBLIC_SHA:
        raise ValueError("MSE1_IMMUTABLE_PUBLIC_HASH_MISMATCH")
    public=json.loads(original_public)
    if public.get("SourceSha256")!=ORIGINAL_PLAIN_SHA:
        raise ValueError("MSE1_ORIGINAL_SOURCE_COMMITMENT_MISMATCH")
    plaintext=unseal_new(cipher,
        os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),ORIGINAL_RUN)
    if sha256(plaintext).hexdigest()!=ORIGINAL_PLAIN_SHA:
        raise ValueError("MSE1_ORIGINAL_PLAINTEXT_HASH_MISMATCH")
    source=json.loads(plaintext)
    if source["SourceLabel"]!=public["OriginalInputLabel"]:
        raise ValueError("MSE1_ORIGINAL_TAPE_LABEL_MISMATCH")
    pairs={name:set(stamps) for name,stamps in source["RawPairClocks"].items()}
    marks={}
    for item in source["Marks"]:
        marks.setdefault(item["Symbol"],set()).add(item["At"])
    if len(source["Marks"])!=public["OriginalBidAskAsOfMarks"]:
        raise ValueError("MSE1_IMMUTABLE_MARK_COUNT_MISMATCH")
    clock_results=[]
    for text in CLOCKS:
        at=clock(text)
        cp=at in pairs.get("Coffee",set())
        ep=at in pairs.get("EURUSD",set())
        cm=at in marks.get("Coffee",set())
        em=at in marks.get("EURUSD",set())
        if cm and not cp:
            raise ValueError("MSE1_COFFEE_MODEL_MARK_WITHOUT_RAW_PAIR")
        stage=("MODEL_READY_COFFEE_MARK" if cm else
          "ORIGINAL_COFFEE_BIDASK_PAIR_MISSING" if not cp else
          "ORIGINAL_USDEUR_PAIR_MISSING" if not ep else
          "ORIGINAL_PAIRED_INPUT_NOT_MODELED_UNRESOLVED")
        clock_results.append({
            "ClockUtc":text,"CoffeeOriginalRawPair":cp,
            "EurUsdOriginalRawPair":ep,
            "CoffeeOriginalModelReadyMark":cm,
            "EurUsdOriginalModelReadyMark":em,
            "MissingStage":stage})
    report={
        "Study":"MSE1_COFFEE_ORIGINAL_TAPE_POSTCLOSURE_READBACK",
        "OriginalRun":int(ORIGINAL_RUN),
        "ImmutableSourceVerified":True,
        "OriginalCiphertextSha256":ORIGINAL_CIPHER_SHA,
        "OriginalPlaintextSha256":ORIGINAL_PLAIN_SHA,
        "OriginalPublicReceiptSha256":ORIGINAL_PUBLIC_SHA,
        "OriginalMarksCount":len(source["Marks"]),
        "OriginalCoffeeRawPairClocks":len(pairs.get("Coffee",())),
        "OriginalCoffeeModelReadyMarks":len(marks.get("Coffee",())),
        "OriginalEURUSDRawPairClocks":len(pairs.get("EURUSD",())),
        "GapStageAtSpecificClocks":clock_results,
        "NoBrokerCalls":True,"OrdersSubmitted":0,
        "CloudActivated":False,"HistoricalSessionHolidayCertification":False,
        "ProfitLossRecomputed":False,"OriginalReplayRerun":False,
        "OriginalEvidenceModified":False,
        "Note":"Original captured as-of paired marks are not complete intrabar tick paths or actual broker orders"
    }
    Path("mse1-coffee-original-tape-postclosure-public.json").write_text(
        json.dumps(report,sort_keys=True,indent=2)+"\n")
    print("ORIGINAL_MSE1_IMMUTABLE_COFFEE_GAP_STAGE_VERIFIED",
          json.dumps({"Clocks":len(clock_results),"BrokerCalls":0,"Orders":0}),flush=True)

if __name__=="__main__":
    main()

"""XMH2 independently reconstruct original raw bound-account protobuf requests.
Output is DATE/COUNT/HASH provenance only, never real broker bars or account IDs.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
import json
import os

from .custody import unseal_new
from . import hxc1_historical_readback as original_validator
from .xmh2_m15_source import PROTOCOL,SOURCE_CLASS

NAMES=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD",
       "US500","NAS100","GER40","UK100","AUS200","JPN225")


def execute() -> None:
    secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    run=os.environ.get("GITHUB_RUN_ID","")
    if not secret.strip() or not run.isdecimal() or int(run)<=0:
        raise ValueError("XMH2_PROTECTED_RUN_BOUND_SECRET_REQUIRED")
    path=Path("xmh2-sealed-output/source.envelope.json")
    envelope=path.read_bytes()
    receipt=json.loads(Path("xmh2-sealed-output/receipt.public.json").read_text())
    digest=sha256(envelope).hexdigest()
    if digest!=receipt.get("ciphertextSha256"):
        raise ValueError("XMH2_ENCRYPTED_ORIGINAL_HASH_MISMATCH")
    original=json.loads(unseal_new(envelope,secret,run))
    # Reuse identical independently tested raw protobuf reconstruction.
    original_validator.PROTOCOL=PROTOCOL
    original_validator.SCHEMA=SOURCE_CLASS
    validated=original_validator.validate(original,receipt,run)
    if validated["rawRequestsRebuilt"]!=1644:
        raise ValueError("XMH2_MISSING_FROZEN_ORIGINAL_REQUESTS")
    counts=validated["sourceCounts"]
    if len(counts)!=12 or set(counts)!={s+"/M15" for s in NAMES}:
        raise ValueError("XMH2_MISSING_SOURCE_NAMES")
    months={}
    bounds={}
    for symbol in NAMES:
        rows=original["bars"][symbol+"/M15"]
        monthly=Counter(datetime.fromtimestamp(row[0]/1000,timezone.utc)
                        .strftime("%Y-%m") for row in rows)
        months[symbol]={k:monthly[k] for k in sorted(monthly)}
        bounds[symbol]={"firstBarStartUtc":
            datetime.fromtimestamp(rows[0][0]/1000,timezone.utc).isoformat() if rows else None,
            "lastBarEndUtc":
            datetime.fromtimestamp(rows[-1][1]/1000,timezone.utc).isoformat() if rows else None}
    output={
        "status":"XMH2_NEW_AUTHENTIC_FULL_EARLIER_274DAY_M15_RAW_PROTOBUF_REBUILT",
        "sourceRunId":run,"sourceProtocolSha256":validated["protocolSha256"],
        "ciphertextSha256":digest,"originalBrokerPepperstoneReadOnly":True,
        "rawHistoricalProtobufRequestsVerified":validated["rawRequestsRebuilt"],
        "requestedDateStartUtc":"2025-11-16T00:00:00Z",
        "requestedDateEndUtc":"2026-08-17T00:00:00Z",
        "returnedRealBarCounts":counts,"returnedTotalAuthenticM15Bars":sum(counts.values()),
        "perSymbolMonthlyDateSupportCounts":months,
        "earliestLatestActualBarClocks":bounds,
        "requestedWindowsWithZeroRealBars":sum(
            window["barCount"]==0 for window in original["windows"]),
        "newHistoricalSourceNotIndependentFutureValidation":True,
        "completedClosedStudyRerun":False,"predictorsFitted":0,
        "positionsOrOrders":0,"cloudActivated":False,"netEur":None,
        "fundedHard21OrFloatingDdCertified":False,
        "economicQualification":False}
    Path("xmh2-full-m15-provenance.public.json").write_text(
        json.dumps(output,sort_keys=True,indent=2)+"\n")
    print("XMH2_AUTHENTIC_274DAY_M15_SOURCE_REBUILT_FROM_ORIGINAL_PROTOBUF_NO_TRADING",
          flush=True)


if __name__=="__main__":
    try:
        execute()
    except Exception:
        print("XMH2_PROTECTED_READBACK_GUARDED_FAILURE_DETAILS_WITHHELD",
              flush=True)
        raise SystemExit(1)

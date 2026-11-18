"""Independent XMH1 ORIGINAL raw protobuf verification, no strategy rescoring."""
import hashlib
import json
import os
from pathlib import Path

from .custody import unseal_new
from . import hxc1_historical_readback as existing
from .xmh1_m15_source import PROTOCOL, SOURCE_CLASS


def execute() -> None:
    private = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    run = os.environ.get("GITHUB_RUN_ID", "")
    if not private.strip() or not run.isdecimal() or int(run)<=0:
        raise ValueError("XMH1_RUN_BOUND_PRIVATE_CUSTODY_REQUIRED")
    envelope = Path("xmh1-sealed-output/source.envelope.json").read_bytes()
    receipt = json.loads(Path("xmh1-sealed-output/receipt.public.json").read_text())
    digest=hashlib.sha256(envelope).hexdigest()
    if digest!=receipt["ciphertextSha256"]:
        raise ValueError("XMH1_ORIGINAL_CIPHER_DIGEST_FAIL")
    bundle=json.loads(unseal_new(envelope,private,run))
    # Keep original trusted HXC1 raw-protobuf reconstruction code unchanged.
    # Only bind it to this NEW frozen source-protocol and source class.
    existing.PROTOCOL=PROTOCOL
    existing.SCHEMA=SOURCE_CLASS
    checked=existing.validate(bundle,receipt,run)
    counts=checked["sourceCounts"]
    if len(counts)!=12 or any(not k.endswith("/M15") for k in counts):
        raise ValueError("XMH1_UNEXPECTED_SYMBOL_SOURCE_PERIOD")
    total=sum(counts.values())
    # Exact facts only. A non-positive past window does not certify that all
    # other past dates are absent or a formal maximum-history cutoff.
    out={
        "status":"XMH1_NEW_AUTHENTIC_PEPPERSTONE_EARLIER_M15_SOURCE_RAW_PROTOBUF_VERIFIED",
        "sourceRunId":run,
        "protocolSha256":checked["protocolSha256"],
        "ciphertextSha256":digest,
        "readOnly":True,
        "rawProtobufRequestsVerified":checked["rawRequestsRebuilt"],
        "exactSourceCountsBySymbolPeriod":counts,
        "totalAuthenticM15BarsInThreeOldProbes":total,
        "allTwelveSourcesObservedM15":all(counts[k+"/M15"]>0 for k in [
            "EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD",
            "XAUUSD","US500","NAS100","GER40","UK100","AUS200","JPN225"]),
        "earlierHistoryExistenceDemonstrated":total>0,
        "officialMaximumHistoricalDepthDemonstrated":False,
        "newPredictiveResults":False,"cdh1OriginalRerun":False,
        "fundedNetEur":None,"economicQualification":False,
        "ordersSubmitted":0,"cloudActivated":False,
    }
    Path("xmh1-original-readback.public.json").write_text(
        json.dumps(out,sort_keys=True,indent=2)+"\n")
    print("XMH1_ORIGINAL_NEW_BROKER_M15_PROVENANCE_VERIFIED_SOURCE_ONLY",flush=True)


if __name__ == "__main__":
    try:
        execute()
    except Exception:
        print("XMH1_SOURCE_READBACK_FAILED_CLOSED_NO_PRIVATE_ERROR",flush=True)
        raise SystemExit(1)

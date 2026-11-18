"""SHD1 original HXC1 protected native C# bridge: custody and transcode ONLY.
NO prediction/model/threshold/NET computation in Python; no history export.
This is NEW SHD1 research, NOT a rerun or modification of closed HXC1/AHR1.
"""
from __future__ import annotations
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .custody import unseal_new
from .decode import need
from .hxc1_historical_readback import validate

ORIGINAL_RUN = "43817213663"
SOURCE = Path("shd1-hxc1-source")
OUTPUT = Path("shd1-public")
UNIVERSE = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
            "XAUUSD", "US500", "NAS100", "GER40", "UK100", "AUS200", "JPN225")
PERIODS = ("H1", "M15")


def execute() -> None:
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and
         os.environ.get("GITHUB_REF") == "refs/heads/main" and
         os.environ.get("GITHUB_ACTOR") == "mariancradulescu",
         "SHD1_OWNER_ORIGINAL_MAIN_ONLY")
    key = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key.strip()), "SHD1_PROTECTED_CUSTODY_MISSING")
    encrypted = (SOURCE / "source.envelope.json").read_bytes()
    original = json.loads((SOURCE / "receipt.public.json").read_text())
    ciphertext_sha = hashlib.sha256(encrypted).hexdigest()
    need(ciphertext_sha == original["ciphertextSha256"],
         "SHD1_ORIGINAL_SOURCE_CIPHERTEXT_SHA_MISMATCH")
    bundle = json.loads(unseal_new(encrypted, key, ORIGINAL_RUN))
    rebuilt = validate(bundle, original, ORIGINAL_RUN)
    need(rebuilt["status"] ==
         "HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT",
         "SHD1_NOT_AN_AUTHENTIC_ORIGINAL_BROKER_HISTORY")
    streams = []
    counts = {}
    for symbol in UNIVERSE:
        for period in PERIODS:
            ident = symbol + "/" + period
            need(ident in bundle["bars"], "SHD1_ORIGINAL_PERIOD_MISSING")
            rows = bundle["bars"][ident]
            need(len(rows) >= 100, "SHD1_ORIGINAL_SOURCE_SPARSE")
            streams.append({
                "Symbol": symbol, "Period": period,
                "Bars": [{"Start": r[0], "End": r[1], "Open": r[2],
                          "High": r[3], "Low": r[4], "Close": r[5],
                          "Volume": r[6]} for r in rows]
            })
            counts[ident] = len(rows)
    payload = {
        "SourceRunId": ORIGINAL_RUN,
        "ProtocolSha256": bundle["protocolSha256"],
        "CiphertextSha256": ciphertext_sha,
        "Streams": streams,
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="shd1-private-original-") as private:
        source_file = Path(private) / "original-h1-m15-market-bars.json"
        source_file.write_text(json.dumps(payload, separators=(",", ":")))
        result_file = OUTPUT / "shd1-original-authentic-native-aggregate.json"
        run = subprocess.run([
            "dotnet", "run", "--no-build", "--project", "src/Mxm.Replay",
            "-c", "Release", "--", str(source_file), str(result_file),
            "--shd1-authentic-h1-m15"
        ], capture_output=True, text=True, timeout=2400)
        need(run.returncode == 0, "SHD1_CSHARP_AUTHENTIC_SCORER_FAILED")
        result = json.loads(result_file.read_text())
        need(result["SourceClass"] ==
             "AUTHENTIC_PEPPERSTONE_HXC1_H1_M15_BAR_HISTORY" and
             result["SourceRunId"] == ORIGINAL_RUN and
             result["ProtocolSha256"] == bundle["protocolSha256"] and
             result["CiphertextSha256"] == ciphertext_sha and
             result["OrdersSubmitted"] == 0 and
             result["CloudActivated"] is False and
             result["EconomicQualification"] is False and
             result["AuthenticFundedTrades"] is None and
             result["NetEur"] is None and len(result["Streams"]) == 24,
             "SHD1_AUTHENTIC_NATIVE_RECEIPT_INVALID")
        (OUTPUT / "shd1-original-source-custody.public.json").write_text(
            json.dumps({
                "status": rebuilt["status"],
                "sourceRunId": ORIGINAL_RUN,
                "originalHxc1CiphertextSha256": ciphertext_sha,
                "originalHxc1ProtocolSha256": bundle["protocolSha256"],
                "sourceCounts": counts,
                "totalOriginalH1M15Bars": sum(counts.values()),
                "nativeCSharpOutputSha256":
                    hashlib.sha256(result_file.read_bytes()).hexdigest(),
                "sourceOriginalAccountRebuilt": True,
                "historicalBrokerFills": False,
                "privateOriginalHistoryPublished": False,
                "orderActions": 0,
                "cloudActivated": False,
                "netEur": None
            }, indent=2, sort_keys=True) + "\n")
    print("SHD1_ORIGINAL_HXC1_CRYPTO_VERIFIED_NATIVE_H1_M15_AGGREGATE_NO_ORDERS", flush=True)


if __name__ == "__main__":
    try:
        execute()
    except Exception:
        # Do not print exception content in the protected job: it may include
        # decrypted account or market source details.
        print("SHD1_ORIGINAL_GUARDED_FAILURE_NO_PRIVATE_DETAILS", flush=True)
        raise SystemExit(1)

"""CDH1 ORIGINAL Pepperstone HXC1 protected custody-only bridge.
No Python prediction/fitting/selection/NET. Do not read public original market bars
out of custody and do not change/retrigger any closed historical scorer.
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
SRC = Path("cdh1-hxc1-source")
OUT = Path("cdh1-public")
SYMBOLS = ("EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD",
           "XAUUSD", "US500", "NAS100", "GER40", "UK100", "AUS200", "JPN225")
PERIODS = ("H1", "M15")


def execute() -> None:
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and
         os.environ.get("GITHUB_REF") == "refs/heads/main" and
         os.environ.get("GITHUB_ACTOR") == "mariancradulescu",
         "CDH1_ORIGINAL_ONLY")
    key = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key.strip()), "CDH1_MISSING_PRIVATE_CUSTODY_KEY")
    cipher = (SRC / "source.envelope.json").read_bytes()
    receipt = json.loads((SRC / "receipt.public.json").read_text())
    sha = hashlib.sha256(cipher).hexdigest()
    need(sha == receipt["ciphertextSha256"], "CDH1_ORIGINAL_CIPHER_SHA_MISMATCH")
    bundle = json.loads(unseal_new(cipher, key, ORIGINAL_RUN))
    v = validate(bundle, receipt, ORIGINAL_RUN)
    need(v["status"] ==
         "HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT",
         "CDH1_ORIGINAL_PEPPERSTONE_READBACK_NOT_VERIFIED")
    streams = []
    source_counts = {}
    for symbol in SYMBOLS:
        for period in PERIODS:
            ident = symbol + "/" + period
            need(ident in bundle["bars"], "CDH1_MISSING_ORIGINAL_MARKET_STREAM")
            rows = bundle["bars"][ident]
            need(len(rows) >= 100, "CDH1_ORIGINAL_STREAM_TOO_SHORT")
            streams.append({"Symbol": symbol, "Period": period,
                            "Bars": [{"Start": row[0], "End": row[1],
                                      "Open": row[2], "High": row[3],
                                      "Low": row[4], "Close": row[5],
                                      "Volume": row[6]} for row in rows]})
            source_counts[ident] = len(rows)
    payload = {"SourceRunId": ORIGINAL_RUN,
               "ProtocolSha256": bundle["protocolSha256"],
               "CiphertextSha256": sha, "Streams": streams}
    OUT.mkdir(exist_ok=True, parents=True)
    with tempfile.TemporaryDirectory(prefix="cdh1-protected-original-") as d:
        private = Path(d) / "original-h1-m15-not-public.json"
        private.write_text(json.dumps(payload, separators=(",", ":")))
        public = OUT / "cdh1-original-competing-hazard-csharp-aggregate.json"
        result = subprocess.run(
            ["dotnet", "run", "--no-build", "--project", "src/Mxm.Replay",
             "-c", "Release", "--", str(private), str(public),
             "--cdh1-authentic-competing-hazards"],
            capture_output=True, text=True, timeout=3000)
        need(result.returncode == 0, "CDH1_ORIGINAL_CSHARP_SCORER_FAILED")
        scored = json.loads(public.read_text())
        need(scored["Protocol"] == "CDH1_EXANTE_COMPETING_RISKS_DIRECTIONAL_V1" and
             scored["SourceRunId"] == ORIGINAL_RUN and
             scored["ProtocolSha256"] == bundle["protocolSha256"] and
             scored["CiphertextSha256"] == sha and
             len(scored["Streams"]) == 24 and
             scored["OrdersSubmitted"] == 0 and
             scored["CloudActivated"] is False and
             scored["EconomicQualification"] is False and
             scored["NetEur"] is None and
             scored["RealFundedTrades"] is None,
             "CDH1_NATIVE_PUBLIC_RECEIPT_NOT_VALID")
        (OUT / "cdh1-original-source-custody.public.json").write_text(
            json.dumps({
                "status": v["status"],
                "originalRunId": ORIGINAL_RUN,
                "originalCiphertextSha256": sha,
                "originalSourceProtocolSha256": bundle["protocolSha256"],
                "originalMarketCounts": source_counts,
                "totalOriginalH1M15Bars": sum(source_counts.values()),
                "nativeOriginalCSharpJsonSha256":
                    hashlib.sha256(public.read_bytes()).hexdigest(),
                "originalAccountProtobufRebuilt": True,
                "originalBrokerFills": False,
                "rawBrokerSourcePublished": False,
                "orders": 0, "cloudActivated": False, "netEur": None
            }, indent=2, sort_keys=True) + "\n")
    print("CDH1_ORIGINAL_PEPPERSTONE_COMPETING_HAZARD_CSHARP_AGGREGATE_PRESERVED",
          flush=True)


if __name__ == "__main__":
    try:
        execute()
    except Exception:
        # Never print raw exception containing possible private account/source info.
        print("CDH1_PROTECTED_ORIGINAL_GUARDED_FAILURE_NO_PRIVATE_DETAILS",
              flush=True)
        raise SystemExit(1)

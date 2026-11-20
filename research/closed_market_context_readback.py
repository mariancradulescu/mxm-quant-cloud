"""Read the original tapes for the closed-context census. No economic evaluator is invoked."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from . import closed_market_bar_source as supplement
from . import hxc1_historical_readback as hxc1
from . import integrated_market_readback as integrated
from .custody import unseal_new
from .decode import need
from .integrated_market_source import digest


HXC1_RUN = "43817213663"
HXC1_CIPHER = "445195a645f5427a04bb62b8a2b755715226a3893dda27c26ec7c80786c1077d"
INTEGRATED_RUN = "44687919474"
INTEGRATED_RECEIPT = "1f4621b9e76cb38d0ac69f0d88ea02b4face3d124b5528a56ba853d1ac9877ee"
AUDIT = Path("closed-market-context-public")


def sources(key, supplementary_run, native_boundaries=False):
    more, new_receipt = supplement.readback(key, supplementary_run, native_boundaries=native_boundaries)

    root = Path("hxc1-original")
    hxc_receipt = json.loads((root / "receipt.public.json").read_text())
    cipher = (root / "source.envelope.json").read_bytes()
    need(digest(cipher) == hxc_receipt["ciphertextSha256"] == HXC1_CIPHER, "CLOSED_CONTEXT_HXC1_CIPHER_HASH")
    bundle = json.loads(unseal_new(cipher, key, HXC1_RUN))
    hxc1.validate(bundle, hxc_receipt, HXC1_RUN)
    hxc_rows = {tag.split("/")[0]: rows for tag, rows in bundle["bars"].items() if tag.endswith("/M1")}
    del cipher, bundle

    raw = (integrated.PUBLIC_DIR / "source.json").read_bytes()
    receipt = json.loads(raw)
    need(digest(raw) == INTEGRATED_RECEIPT and receipt["RunId"] == INTEGRATED_RUN
         and receipt["NewOrders"] == 0 and not receipt["CloudActivated"]
         and receipt["Status"] == "AUTHENTIC_READ_ONLY_SOURCE_CAPTURED"
         and digest(integrated.PROTOCOL.read_bytes()) == receipt["ProtocolSha256"],
         "CLOSED_CONTEXT_FULL_SESSION_ORIGINAL_RECEIPT")
    records = integrated.readback(receipt, key, interval=30_000)
    close = supplement.stamp(json.loads(supplement.PROTOCOL.read_text())["coveredByHxc1From"])
    for market in records:
        symbol = market["Name"]
        market["AdditionalTimeframes"] = {}
        for period in supplement.MINUTES:
            rows = more.get((symbol, period), [])
            source = "PEPPERSTONE_NATIVE_OPEN_API_" + supplementary_run
            if period == "M1" and symbol in hxc_rows:
                rows = rows + [r for r in hxc_rows[symbol] if r[0] >= close and r[1] <= integrated.END]
                source += "_AND_HXC1_" + HXC1_RUN
            market["AdditionalTimeframes"][period] = {"Source": source, "Bars": integrated.normalized_bars(rows)}
    return records, new_receipt


def main():
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    run = os.environ["GITHUB_RUN_ID"]
    need(bool(key.strip()), "CLOSED_CONTEXT_CUSTODY_KEY_UNAVAILABLE")
    markets, extra = sources(key, run)
    AUDIT.mkdir(exist_ok=True)
    report = AUDIT / "closed-market-context.json"
    with tempfile.TemporaryDirectory(prefix="mxm-closed-context-") as tmp:
        path = Path(tmp) / "verified-input.json"
        with path.open("x") as file:
            path.chmod(0o600)
            json.dump(dict(Start=integrated.START, End=integrated.END, SourceRun=INTEGRATED_RUN,
                           ProtocolSha256=extra["ProtocolSha256"], Markets=markets),
                      file, separators=(",", ":"))
        rc = subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                             "--closed-market-context-audit", str(path), str(report)], check=False).returncode
    need(rc == 0 and report.is_file(), "CLOSED_CONTEXT_NATIVE_CENSUS_FAILED")
    (AUDIT / "receipt.json").write_text(json.dumps({
        "CurrentSourceRun": run, "SupplementaryNativeTrendbarRequests": extra["NativeTrendbarRequests"],
        "SupplementaryProtocolSha256": extra["ProtocolSha256"], "SupplementaryCipherSha256": extra["CipherSha256"],
        "Hxc1OriginalRun": HXC1_RUN, "Hxc1OriginalCipherSha256": HXC1_CIPHER,
        "FullSessionOriginalRun": INTEGRATED_RUN, "FullSessionReceiptSha256": INTEGRATED_RECEIPT,
        "NativeCensusSha256": digest(report.read_bytes()),
        "EconomicEvaluations": 0, "BrokerOrders": 0, "CloudActivated": False, "IndependentConfirmation": False,
    }, indent=2) + "\n")
    print("Native causal context coverage reconstructed from protected original source.", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        from .guard import CaptureContractError
        code = str(exc)
        print(code if isinstance(exc, CaptureContractError) and code.isupper() and code.replace("_", "").isalnum()
              else "CLOSED_CONTEXT_CUSTODY_OR_REPLAY_FAILED_CLOSED", flush=True)
        raise SystemExit(1)

"""Read back existing authentic paths for the frozen coherent native lifecycle."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .decode import need
from .integrated_lifecycle_forensics import SOURCE_SHA, checked_json
from .integrated_market_readback import readback
from .integrated_market_source import END, PUBLIC_DIR, START, digest

PROTOCOL = Path("research/INTEGRATED_CAUSAL_LIFECYCLE_20261120.md")
PROTOCOL_SHA = "1020f6493849138d1394e02dc1085d1f775ae57794e5845006e32341056a4aac"
FORENSICS_SHA = "c961d1ec34050a88f5f30a994a2c731530aa5a087c2fc3477e7fbe03e835118b"
OUTPUT = Path("integrated-lifecycle-economic-public")


def main():
    need(digest(PROTOCOL.read_bytes()) == PROTOCOL_SHA, "INTEGRATED_LIFECYCLE_FROZEN_PROTOCOL")
    forensic = checked_json(Path("integrated-lifecycle-existing-forensics/forensics.json"), FORENSICS_SHA)
    need(forensic["OriginalEconomicRun"] == "44691260616" and forensic["OriginalSourceRun"] == "44687919474",
         "INTEGRATED_LIFECYCLE_FORENSIC_BINDING")
    source = checked_json(PUBLIC_DIR / "source.json", SOURCE_SHA)
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(key), "INTEGRATED_LIFECYCLE_CUSTODY_KEY_MISSING")
    markets = readback(source, key, interval=30_000)
    print("INTEGRATED_LIFECYCLE_RECONCILED_MARKS", [(m["Name"], len(m["Quotes"])) for m in markets], flush=True)
    OUTPUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="integrated-lifecycle-") as directory:
        verified = Path(directory) / "verified.json"
        verified.write_text(json.dumps({
            "Start": START, "End": END, "SourceRun": source["RunId"], "ProtocolSha256": PROTOCOL_SHA,
            "ManagementIntervalMs": 30_000, "Markets": markets,
        }, separators=(",", ":")))
        result = subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                                 "--integrated-coherent", str(verified), str(OUTPUT)], check=False)
        report = OUTPUT / "economic.json"
        need(result.returncode == 0 and report.is_file(), "INTEGRATED_LIFECYCLE_NATIVE_EVALUATION_FAILED")
    (OUTPUT / "receipt.json").write_text(json.dumps({
        "Status": "COHERENT_INTEGRATED_EXPOSED_NATIVE_ECONOMICS_AVAILABLE",
        "SourceRun": source["RunId"], "OriginalForensicRun": "44698833443", "ForensicsSha256": FORENSICS_SHA,
        "FrozenProtocolSha256": PROTOCOL_SHA, "NativeOutputSha256": digest(report.read_bytes()),
        "ExistingSourceReadOnlyRequests": source["Requests"], "NewSourceRequests": 0,
        "OrdersSubmitted": 0, "CloudActivated": False, "IndependentConfirmation": False,
        "BrokerNetCertified": False, "ContinuousFloatingDrawdownCertified": False,
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()

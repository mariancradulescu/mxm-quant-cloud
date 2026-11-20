"""Reconcile source timing first, then run the frozen C# conditional common-book research."""

import json
import os
import subprocess
import tempfile
from pathlib import Path

from .closed_market_context_readback import sources, INTEGRATED_RUN, INTEGRATED_RECEIPT
from .decode import need
from .guard import CaptureContractError
from .integrated_market_readback import START, END
from .integrated_market_source import digest


SUPPLEMENTARY_RUN = "44733062339"
SUPPLEMENTARY_CIPHER = "443b2dd37d31ea2227de39a19bcce17ba1f0c0804a51483bc3e035eedb5d9d53"
PROTOCOL = Path("research/CLOSED_MARKET_OPPORTUNITIES_20261120.md")
OUTPUT = Path("closed-market-structural-public")


def main():
    private = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(private.strip()), "CLOSED_MARKET_ORIGINAL_CUSTODY_KEY_MISSING")
    OUTPUT.mkdir(exist_ok=True)
    markets, receipt = sources(private, SUPPLEMENTARY_RUN, native_boundaries=True)
    need(receipt["CipherSha256"] == SUPPLEMENTARY_CIPHER, "CLOSED_MARKET_SUPPLEMENTARY_ORIGINAL_HASH")
    protocol_hash = digest(PROTOCOL.read_bytes())
    context, result = OUTPUT / "context.json", OUTPUT / "economic.json"
    exe = ["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"]
    with tempfile.TemporaryDirectory(prefix="mxm-structural-original-") as tmp:
        data = Path(tmp) / "source.json"
        with data.open("x") as file:
            data.chmod(0o600)
            json.dump(dict(Start=START, End=END, SourceRun=INTEGRATED_RUN, ProtocolSha256=protocol_hash, Markets=markets),
                      file, separators=(",", ":"))
        for route, path in (("--closed-market-context-audit", context), ("--closed-market-opportunities", result)):
            if route == "--closed-market-opportunities":
                coverage = json.loads(context.read_text())["Markets"]
                need(any(m["SynchronizedDecisionContexts"] > 0 for m in coverage),
                     "CLOSED_MARKET_NO_SYNCHRONIZED_AUTHENTIC_CONTEXT")
            need(subprocess.run(exe + [route, str(data), str(path)], check=False).returncode == 0 and path.is_file(),
                 "CLOSED_MARKET_NATIVE_EXECUTION_FAILED")
    (OUTPUT / "receipt.json").write_text(json.dumps({
        "ProtocolSha256": protocol_hash, "FullSessionOriginal": INTEGRATED_RUN,
        "FullSessionOriginalReceiptSha256": INTEGRATED_RECEIPT, "SupplementaryOriginal": SUPPLEMENTARY_RUN,
        "SupplementaryCipherSha256": SUPPLEMENTARY_CIPHER, "ContextSha256": digest(context.read_bytes()),
        "EconomicSha256": digest(result.read_bytes()), "DataExposed": True, "BrokerNetCertified": False,
        "IndependentConfirmation": False, "ReadOnlyNewRequests": 0, "Orders": 0, "CloudActivated": False
    }, indent=2) + "\n")
    print("CLOSED_MARKET_STRUCTURAL_ORIGINAL_RECEIPT_AVAILABLE", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        code = str(exc)
        print(code if isinstance(exc, CaptureContractError) and code.isupper() and code.replace("_", "").isalnum()
              else "CLOSED_MARKET_STRUCTURAL_CUSTODY_OR_NATIVE_FAILURE", flush=True)
        raise SystemExit(1)

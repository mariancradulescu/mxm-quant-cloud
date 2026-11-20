"""Post-415 authentic-source W44-W45 ONLY native funded development.

Recover original Pepperstone read-only encrypted source in the protected runner.
The authoritative economic experiment and all book decisions run in C#.
This never invokes or scores the frozen W46 economic evaluator.
"""
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .closed_market_context_readback import sources, INTEGRATED_RUN, INTEGRATED_RECEIPT
from .closed_market_structural_evaluation import SUPPLEMENTARY_RUN, SUPPLEMENTARY_CIPHER
from .decode import need
from .integrated_market_readback import START, END
from .integrated_market_source import digest

OUT = Path("post415-exhaustion-development-public")
INTENT = "OWNER_POST415_EXHAUSTION_W44_W45_DEVELOPMENT_ONCE"


def main():
    private = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM", "").encode()
    need(bool(private.strip()), "POST415_CUSTODY_KEY_MISSING")
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and
         os.environ.get("GITHUB_REF") == "refs/heads/main" and
         os.environ.get("GITHUB_ACTOR") == "mariancradulescu" and
         os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and
         Path("ops/post415-exhaustion-development-once.txt").read_text() == INTENT,
         "POST415_ONLY_FIRST_MAIN_MARKER_ALLOWED")
    markets, receipt = sources(private, SUPPLEMENTARY_RUN, native_boundaries=True)
    need(receipt["CipherSha256"] == SUPPLEMENTARY_CIPHER,
         "POST415_SUPPLEMENTARY_CIPHER_ORIGINAL_MISMATCH")
    OUT.mkdir(exist_ok=True)
    economic = OUT / "economic.json"
    with tempfile.TemporaryDirectory(prefix="mxm-post415-original-") as tmp:
        data = Path(tmp) / "source.json"
        with data.open("x") as output:
            data.chmod(0o600)
            json.dump(dict(Start=START, End=END, SourceRun=INTEGRATED_RUN,
                           ProtocolSha256=receipt["ProtocolSha256"], Markets=markets),
                      output, separators=(",", ":"))
        rc = subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                             "--post415-exhaustion-development", str(data), str(economic)],
                            check=False).returncode
    need(rc == 0 and economic.is_file(), "POST415_NATIVE_DEV_ECONOMIC_EVALUATION_FAILED")
    outcome = json.loads(economic.read_text())
    result = outcome["Result"]
    need(result["W46AdvancedClocks"] == 0 and
         not result["IndependentConfirmation"] and not result["BrokerNetCertified"] and
         result["Orders"] == 0 and not result["CloudActivation"],
         "POST415_DEVELOPMENT_MUST_NOT_CLAIM_CONFIRMATION")
    (OUT / "receipt.json").write_text(json.dumps(dict(
        Study="POST415_IMPULSE_EXHAUSTION_W44_W45_DEVELOPMENT",
        GitCommit=os.environ["GITHUB_SHA"], Protocol="RESEARCH_CORE_CSHARP_PRE_REGISTERED",
        OriginalFullSessionRun=INTEGRATED_RUN,
        OriginalFullSessionReceiptSha256=INTEGRATED_RECEIPT,
        OriginalSupplementaryRun=SUPPLEMENTARY_RUN,
        OriginalSupplementaryCipherSha256=SUPPLEMENTARY_CIPHER,
        EconomicSha256=digest(economic.read_bytes()),
        W46AdvancedClocks=0, HistoricalExposure=True,
        BrokerNetCertified=False, IndependentConfirmation=False,
        Orders=0, CloudActivated=False, BrokerRequests=0
    ), indent=2)+"\n")
    print("POST415_NATIVE_EXPOSED_W44_W45_DEVELOPMENT_ORIGINAL_AVAILABLE", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("POST415_ORIGINAL_CUSTODY_OR_NATIVE_EVALUATION_FAILED", flush=True)
        raise SystemExit(1)

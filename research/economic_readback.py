"""Independently verify newly collected multi-resolution encrypted evidence via C#."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from .custody import unseal_new

def run():
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    run_id=os.environ.get("GITHUB_RUN_ID","")
    if not private.strip() or not run_id.isdigit():
        raise ValueError("ECONOMIC_CUSTODY_CONFIGURATION_MISSING")
    sealed=Path("sealed-output/source.envelope.json").read_bytes()
    public=json.loads(Path("sealed-output/receipt.public.json").read_text())
    if (public.get("status")!="NEW_ECONOMIC_SOURCE_V2_SEALED" or
        hashlib.sha256(sealed).hexdigest()!=public.get("ciphertextSha256")):
        raise ValueError("ECONOMIC_SOURCE_DIGEST_MISMATCH")
    bundle=json.loads(unseal_new(sealed,private,run_id))
    original=bundle.pop("csharpReceipt")
    if bundle.get("schema")!="mxm-econ-source-v2" or not bundle.get("readOnly"):
        raise ValueError("ECONOMIC_SOURCE_TYPE_INCORRECT")
    with tempfile.TemporaryDirectory(prefix="mxm-economic-readback-") as tmp:
        original_input=Path(tmp)/"tape.json"
        verification=Path(tmp)/"receipt.json"
        original_input.write_text(json.dumps(bundle,sort_keys=True))
        original_input.chmod(0o600)
        env={k:v for k,v in os.environ.items() if not k.startswith(
            ("R3_","CTRADER_","MXM_V4_"))}
        child=subprocess.run(["dotnet",
            "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
            str(original_input),str(verification),"--economic-source"],
            env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if child.returncode!=0 or json.loads(verification.read_text())!=original:
            raise ValueError("ECONOMIC_CSHARP_READBACK_PARITY_FAILED")
    if original.get("ordersSubmitted")!=0 or original.get("fullyFundedNet200EurProven"):
        raise ValueError("ECONOMIC_QUALIFICATION_NOT_AUTHORIZED")
    receipt={
        "schema":"mxm.economic-source-readback-public.v2",
        "runId":int(run_id),
        "status":"AUTHENTIC_PEPPERSTONE_MULTIRESOLUTION_CSHARP_PARITY",
        "sealedSha256":public["ciphertextSha256"],
        "totalBars":original["sourceBarCount"],
        "perResolutionBars":original["perResolutionBars"],
        "perResolutionMonths":original["observedCalendarMonths"],
        "twelveMonthSourceSpanObserved":original["twelveMonthSpanObserved"],
        "brokerContractFeasibilityStatus":original["brokerSourceContract"],
        "historicalBidAskQuoteSpreadObservation":original["genuineHistoricalBidAskQuotes"],
        "economicNET":None,
        "eur200ExecutableConfirmed":False,
        "hard21Confirmed":False,
        "freshIndependentConfirmation":False,
        "ordersSubmitted":0,
        "noRawPriceOrAccountExport":True
    }
    Path("economic-source-receipt.public.json").write_text(
        json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("AUTHENTIC_ECONOMIC_SOURCE_PUBLIC_AGGREGATE "+json.dumps({
        "totalBars":receipt["totalBars"],
        "resolutionMonths":receipt["perResolutionMonths"],
        "brokerContractFeasibilityStatus":receipt["brokerContractFeasibilityStatus"],
        "historicalBidAskQuoteSpreadObservation":receipt["historicalBidAskQuoteSpreadObservation"],
        "economicNET":receipt["economicNET"],
        "eur200ExecutableConfirmed":False
    },sort_keys=True))

if __name__=="__main__":
    try: run()
    except Exception:
        print("ECONOMIC_SOURCE_READBACK_FAILED_DETAIL_WITHHELD")
        sys.exit(1)

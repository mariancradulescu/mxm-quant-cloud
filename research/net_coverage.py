"""Genuine cost-evidence inventory on ONE already-authenticated encrypted tape.

Never rerun any closed model, collect broker data or convert OHLC profits to NET.
Source prior native receipt parity must match exactly before the new C# audit.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from .custody import unseal_new

SOURCE_RUN_ID="41476636915"

def run():
    if os.environ.get("MXM_NET_SOURCE_RUN_ID")!=SOURCE_RUN_ID:
        raise ValueError("NET_SOURCE_PROVENANCE_MISMATCH")
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    if not private.strip():
        raise ValueError("NET_SOURCE_PRIVATE_MISSING")
    sealed=Path("sealed-output/source.envelope.json").read_bytes()
    pub=json.loads(Path("sealed-output/receipt.public.json").read_text())
    if pub.get("status")!="NEW_ECONOMIC_SOURCE_V2_SEALED" or (
        hashlib.sha256(sealed).hexdigest()!=pub.get("ciphertextSha256")):
        raise ValueError("NET_SOURCE_SEALED_DIGEST_INVALID")
    original=json.loads(unseal_new(sealed,private,SOURCE_RUN_ID))
    frozen=original.pop("csharpReceipt")
    with tempfile.TemporaryDirectory(prefix="mxm-net-broker-private-") as folder:
        src=Path(folder)/"original.json"
        parity=Path(folder)/"parity.json"
        audit=Path(folder)/"audit.json"
        src.write_text(json.dumps(original,sort_keys=True))
        src.chmod(0o600)
        dll="src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
        env={k:v for k,v in os.environ.items() if not k.startswith(
            ("R3_","CTRADER_","MXM_V4_"))}
        for dest,mode in ((parity,"--economic-source"),(audit,"--economic-net-coverage")):
            p=subprocess.run(["dotnet",dll,str(src),str(dest),mode],
                env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if p.returncode!=0 or not dest.exists():
                raise ValueError("NET_NATIVE_CSHARP_EVALUATION_FAILED")
        if json.loads(parity.read_text())!=frozen:
            raise ValueError("NET_ORIGINAL_CSHARP_PARITY_FAILED")
        source=json.loads(audit.read_text())
    if source.get("historicalExecutableFundedNetEur") is not None or (
        source.get("ordersSubmitted")!=0):
        raise ValueError("NET_ECONOMIC_ADMISSION_FALSE_CLAIM")
    receipt={
        "schema":"mxm.original-live-broker-net-gap.public.v1",
        "originalProtectedSourceRun":int(SOURCE_RUN_ID),
        "originalNativeCSharpReadbackReconciled":True,
        "sealedOriginalSourceSha256":pub["ciphertextSha256"],
        "originalCapitalConstraintEur":200,
        "sourceScope":"AUTHENTIC_13MO_H4_14D_M15_QUOTE_CONTRACT_DEVELOPMENT",
        "contracts":source["contracts"],
        "symbolsWithFullyPricedNetEvidence":source["symbolsWithFullExecutableNetEvidence"],
        "netEur":None,
        "hard21BrokerRoundTrips":0,
        "certifiedDrawdown":False,
        "prospectiveConfirmation":False,
        "modelRetunedOrReplayed":False,
        "ordersSubmitted":0,
        "sourcePricesOrAccountIdentifiersPublished":False
    }
    Path("authenticated-net-gap.public.json").write_text(
        json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    print("AUTHENTIC_BROKER_NET_COST_COVERAGE "+json.dumps({
        "observedSymbols":len(receipt["contracts"]),
        "contracts":receipt["contracts"],
        "symbolsWithFullyPricedNetEvidence":
            receipt["symbolsWithFullyPricedNetEvidence"],
        "netEur":None
    },sort_keys=True))

if __name__=="__main__":
    try: run()
    except Exception:
        print("BROKER_NET_COVERAGE_FAILED_DETAIL_WITHHELD")
        sys.exit(1)

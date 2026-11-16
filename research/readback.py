import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from .custody import unseal_new

def main():
    private = os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM", "")
    if not private: raise ValueError("CONFIGURATION_MISSING")
    cipher=Path("sealed-output/source.envelope.json").read_bytes()
    receipt=json.loads(Path("sealed-output/receipt.public.json").read_text())
    if hashlib.sha256(cipher).hexdigest()!=receipt["ciphertextSha256"]: raise ValueError("CIPHERTEXT_MISMATCH")
    # New v2 recipient is independently derived from the existing private
    # key; same-run AEAD prevents swapping recipient/source artifacts.
    run_id=os.environ.get("GITHUB_RUN_ID","")
    bundle=json.loads(unseal_new(cipher,private.encode(),run_id))
    original=bundle.pop("csharpReceipt")
    with tempfile.TemporaryDirectory(prefix="mxm-readback-") as folder:
        source=Path(folder)/"source.json"; source.write_text(json.dumps(bundle,sort_keys=True)); source.chmod(0o600)
        output=Path(folder)/"receipt.json"
        clean_env={k:v for k,v in os.environ.items() if not k.startswith(("R3_", "CTRADER_", "MXM_V4_"))}
        result=subprocess.run(["dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",str(source),str(output)],env=clean_env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if result.returncode!=0: raise ValueError("CSHARP_READBACK_FAILED")
        if json.loads(output.read_text())!=original: raise ValueError("CSHARP_RECEIPT_MISMATCH")
    Path("readback.public.json").write_text(json.dumps({"status":"NEW_SOURCE_V2_CUSTODY_AND_CSHARP_READBACK_VERIFIED","ciphertextSha256":receipt["ciphertextSha256"],"economicQualification":False}))

if __name__ == "__main__":
    try:
        main()
        print("CUSTODY_AND_CSHARP_READBACK_VERIFIED; NOT_ECONOMIC_QUALIFICATION")
    except Exception:
        print("CUSTODY_READBACK_FAILED_DETAIL_WITHHELD")
        sys.exit(1)

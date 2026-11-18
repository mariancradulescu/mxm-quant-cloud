"""AHR1 protected custody bridge only: authenticated HXC1 original raw-source validation,
price-bar transcode, native C# invocation. Never fit, score or select models in Python.
No new broker call, no orders, no exposure of raw H1 bars in public artifacts.
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

ORIGINAL_RUN="43817213663"
SRC=Path("ahr1-hxc1-source")
OUT=Path("ahr1-public")
UNIVERSE=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD",
          "US500","NAS100","GER40","UK100","AUS200","JPN225")


def execute():
    need(os.environ.get("GITHUB_EVENT_NAME") == "push" and
         os.environ.get("GITHUB_REF") == "refs/heads/main",
         "AHR1_ORIGINAL_MAIN_ONLY")
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(private.strip()),"AHR1_MISSING_CUSTODY")
    encrypted=(SRC/"source.envelope.json").read_bytes()
    receipt=json.loads((SRC/"receipt.public.json").read_text())
    digest=hashlib.sha256(encrypted).hexdigest()
    need(digest==receipt["ciphertextSha256"],"AHR1_ORIGINAL_CIPHERTEXT_SHA")
    bundle=json.loads(unseal_new(encrypted,private,ORIGINAL_RUN))
    validated=validate(bundle,receipt,ORIGINAL_RUN)
    need(validated["status"]=="HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT",
         "AHR1_ORIGINAL_PROTOBUF_REBUILD_REQUIRED")
    originals=bundle["bars"]
    need(all(s+"/H1" in originals for s in UNIVERSE),
         "AHR1_FROZEN_UNIVERSE_NOT_ALL_PRESENT")
    source=[]
    for symbol in UNIVERSE:
        rows=originals[symbol+"/H1"]
        need(len(rows)>=100,"AHR1_SOURCE_SYMBOL_INSUFFICIENT")
        source.append({"Symbol":symbol,"Bars":[{
            "Start":row[0],"End":row[1],"Open":row[2],"High":row[3],
            "Low":row[4],"Close":row[5],"Volume":row[6]} for row in rows]})
    payload={
        "SourceRunId":ORIGINAL_RUN,
        "ProtocolSha256":bundle["protocolSha256"],
        "CiphertextSha256":digest,
        "Symbols":source,
    }
    OUT.mkdir(parents=True,exist_ok=True)
    # Original history only inside protected temporary file, never artifact upload.
    with tempfile.TemporaryDirectory(prefix="ahr1-private-source-") as directory:
        private_input=Path(directory)/"original-h1-only.json"
        private_input.write_text(json.dumps(payload,separators=(",",":")))
        path=OUT/"ahr1-original-authentic-h1-native-public.json"
        p=subprocess.run(["dotnet","run","--no-build","--project","src/Mxm.Replay",
                          "-c","Release","--",str(private_input),str(path),
                          "--ahr1-authentic-h1"],capture_output=True,text=True,
                         timeout=1800)
        need(p.returncode==0,"AHR1_NATIVE_CSHARP_FAILED")
        result=json.loads(path.read_text())
        need(result["SourceClass"]=="AUTHENTIC_PEPPERSTONE_ORIGINAL_HXC1_H1" and
             result["SourceRunId"]==ORIGINAL_RUN and
             result["ProtocolSha256"]==bundle["protocolSha256"] and
             result["CiphertextSha256"]==digest and
             result["OrdersSubmitted"]==0 and result["CloudActivated"] is False and
             result["EconomicQualification"] is False and
             result["NetEur"] is None and len(result["Results"])==12,
             "AHR1_NATIVE_PUBLIC_RECEIPT_INVALID")
        (OUT/"ahr1-original-source-custody.public.json").write_text(json.dumps({
            "status":validated["status"],"sourceRunId":ORIGINAL_RUN,
            "ciphertextSha256":digest,"protocolSha256":bundle["protocolSha256"],
            "sourceCountsH1":{s:len(originals[s+"/H1"]) for s in UNIVERSE},
            "nativeOutputSha256":hashlib.sha256(path.read_bytes()).hexdigest(),
            "sourceOriginalAccountRebuilt":True,"historicalBrokerFills":False,
            "orders":0,"cloudActivated":False,"netEur":None
        },sort_keys=True,indent=2)+"\n")
    print("AHR1_AUTHENTIC_ORIGINAL_H1_NATIVE_CSHARP_CUSTODY_AND_PREDICTIVE_PUBLIC",flush=True)


if __name__=="__main__":
    try:
        execute()
    except Exception:
        print("AHR1_ORIGINAL_GUARDED_FAILURE_NO_PRIVATE_DETAILS",flush=True)
        raise SystemExit(1)

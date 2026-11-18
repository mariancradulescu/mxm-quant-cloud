"""MCE1 protected source custody/transcode ONLY; no model/strategy in Python.

Use one XMH2 NEW original account M15 archive. Rebuild every original protobuf
request and response in an independent protected job. Open private source tape
ONLY transiently. All predictive features/fit/hazard scoring happen in SAME C#
Cdh1NativeResearch private engine helpers reused by NEW MCE1.
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
from . import hxc1_historical_readback as validator
from .xmh2_m15_source import PROTOCOL,SOURCE_CLASS

XMH2_RUN="44352570167"
SOURCE=Path("mce1-xmh2-source")
OUT=Path("mce1-public")
SYMBOLS=("EURUSD","GBPUSD","USDJPY","AUDUSD","USDCAD","XAUUSD",
         "US500","NAS100","GER40","UK100","AUS200","JPN225")
FIXED=(("AUDUSD","L2_SOFTMAX_COMPETING_HAZARD"),
       ("EURUSD","CONTEXT_BAYES_HAZARD"),
       ("GBPUSD","L2_SOFTMAX_COMPETING_HAZARD"),
       ("JPN225","L2_SOFTMAX_COMPETING_HAZARD"))


def execute() -> None:
    need(os.environ.get("GITHUB_EVENT_NAME")=="push" and
         os.environ.get("GITHUB_REF")=="refs/heads/main" and
         os.environ.get("GITHUB_ACTOR")=="mariancradulescu",
         "MCE1_MAIN_OWNER_ONLY")
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(key.strip()),"MCE1_NO_CUSTODIAN_PRIVATE_KEY")
    data=(SOURCE/"source.envelope.json").read_bytes()
    receipt=json.loads((SOURCE/"receipt.public.json").read_text())
    digest=hashlib.sha256(data).hexdigest()
    need(digest==receipt["ciphertextSha256"],"MCE1_SOURCE_HASH_MISMATCH")
    original=json.loads(unseal_new(data,key,XMH2_RUN))
    validator.PROTOCOL=PROTOCOL
    validator.SCHEMA=SOURCE_CLASS
    checked=validator.validate(original,receipt,XMH2_RUN)
    need(checked["rawRequestsRebuilt"]==1644 and len(checked["sourceCounts"])==12,
         "MCE1_XMH2_ORIGINAL_BROKER_SOURCE_INCOMPLETE")
    source=[]
    for symbol in SYMBOLS:
        name=symbol+"/M15"
        rows=original["bars"].get(name)
        need(rows is not None and len(rows)>=100,
             "MCE1_SOURCE_SUPPORT_MISSING")
        source.append({"Symbol":symbol,"Period":"M15","Bars":[{
            "Start":z[0],"End":z[1],"Open":z[2],"High":z[3],
            "Low":z[4],"Close":z[5],"Volume":z[6]} for z in rows]})
    payload={
        "SourceRunId":XMH2_RUN,
        "ProtocolSha256":checked["protocolSha256"],
        "CiphertextSha256":digest,
        "Streams":source
    }
    OUT.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mce1-protected-raw-original-") as d:
        source_path=Path(d)/"xmh2-original-m15-only-private.json"
        source_path.write_text(json.dumps(payload,separators=(",",":")))
        output=OUT/"mce1-original-extended-m15-cdh1-mechanisms.native.json"
        job=subprocess.run(["dotnet","run","--no-build","--project",
            "src/Mxm.Replay","-c","Release","--",
            str(source_path),str(output),"--mce1-cumulative-cdh1-native"],
            capture_output=True,text=True,timeout=2400)
        need(job.returncode==0,"MCE1_CORE_CSHARP_RUN_FAILED")
        result=json.loads(output.read_text())
        need(result["Protocol"]==
                 "MCE1_CUMULATIVE_CDH1_EXACT_MECHANISMS_NEW_HISTORICAL_M15_V1"
             and result["SourceRunId"]==XMH2_RUN
             and result["CiphertextSha256"]==digest
             and result["ProtocolSha256"]==checked["protocolSha256"]
             and result["OrdersSubmitted"]==0
             and result["CloudActivated"] is False
             and result["EconomicQualification"] is False
             and result["NetEur"] is None
             and len(result["Hypotheses"])==4
             and tuple((x["Symbol"],x["FrozenSelectedModel"])
                       for x in result["Hypotheses"])==FIXED,
             "MCE1_BOUND_NATIVE_AGGREGATE_INVALID")
        (OUT/"mce1-original-new-source-custody.public.json").write_text(
            json.dumps({
                "status":"MCE1_XMH2_NEW_SOURCE_RAW_PROTOBUF_INDEPENDENTLY_REBUILT",
                "sourceRunId":XMH2_RUN,
                "sourceCiphertextSha256":digest,
                "originalSourceProtocolSha256":checked["protocolSha256"],
                "sourceRawProtobufRequestsChecked":checked["rawRequestsRebuilt"],
                "sourceAuthenticM15Counts":checked["sourceCounts"],
                "nativeOriginalCSharpResultSha256":
                    hashlib.sha256(output.read_bytes()).hexdigest(),
                "unexposedFutureConfirmation":False,
                "closedStudyReruns":0,"brokerOrders":0,
                "cloudActivated":False,"netEur":None,
                "fundedQualification":False
            },sort_keys=True,indent=2)+"\n")
    print("MCE1_ORIGINAL_NEW_M15_FROZEN_CDH1_MECHANISMS_NATIVE_CSHARP_COMPLETED",flush=True)


if __name__=="__main__":
    try:
        execute()
    except Exception:
        print("MCE1_PROTECTED_CUSTODY_OR_NATIVE_GUARDED_FAIL_NO_PRIVATE_ERROR",
              flush=True)
        raise SystemExit(1)

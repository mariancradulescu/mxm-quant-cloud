"""Execute exactly ONE frozen V3.2 program; Python only original-custody adaptor.

The SAME C# Core decides AND accounts; no Python financial simulator, no broker APIs.
No private prices, account ids, decrypted protobuf or credentials in public artifact.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .v32_unified_source_adapter import execute as build_private_input

OUT=Path("v32-integrated-public")
EXPECTED={
    "41724643418","41735441128","44352570167","43817213663","45134137836"
}

def need(ok,code):
    if not ok:raise ValueError("V32_UNIFIED_"+code)

def run():
    need(bool(os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").strip()),"PROTECTED_CUSTODY_MISSING")
    OUT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="mxm-v32-private-") as temp:
        tape=Path(temp)/"authenticated-originals-private.json"
        economic=Path(temp)/"one-native-eur300-private-output.json"
        provenance=build_private_input(tape)
        print("V32_STAGE_AUTHENTIC_SOURCES_JOINED",flush=True)
        need(set(provenance["SourceRuns"])==EXPECTED and provenance["Markets"]>=48,
             "INTEGRATED_SOURCE_BINDING")
        private_sha=hashlib.sha256(tape.read_bytes()).hexdigest()
        print("V32_STAGE_NATIVE_CSHARP_START",flush=True)
        result=subprocess.run(["dotnet","run","--no-build","--project",
            "src/Mxm.Replay","-c","Release","--",str(tape),str(economic),
            "--v32-unified-integrated-development"],
            text=True,capture_output=True,timeout=5400)
        need(result.returncode==0 and economic.is_file(),"NATIVE_CSHARP_ECONOMIC_REPLAY_FAILED")
        native=json.loads(economic.read_text())
        print("V32_STAGE_NATIVE_ECONOMIC_REPORT_READY",flush=True)
        need(native.get("Schema")=="V32_INTEGRATED_EUR300_NATIVE_DEVELOPMENT"
             and set(native["SourceRuns"])==EXPECTED
             and native.get("ModelOrders")==0
             and native.get("CloudActivated") is False
             and native.get("NoClosedStudyRerun") is True
             and len(native.get("Results",[]))==21,"NATIVE_ECONOMIC_REPORT_INTEGRITY")
        result_list=native["Results"]
        policy=[x for x in result_list if x["Policy"]=="FULL"]
        need(sorted(float(x["CostMultiplier"]) for x in policy)==[1,1.5,2],
             "PRIMARY_STRESS_CASES_MISSING")
        for row in result_list:
            need(row["InitialEur"]==300 and row["Orders"]==0 and
                 row["CloudActivated"] is False and row["CertifiedHARD21"] is False,
                 "MODEL_SAFETY_OR_EUR300")
            need(row["FundedModeledCompleteTrips"]==sum(
                 1 for t in row["CompletedAndPartialTrades"]
                 if t["Reason"] is not None),"MODEL_CLOSED_TRIP_COUNT")
        package={
            "Schema":"MXM_V32_ONE_UNIFIED_ECONOMIC_REPRODUCIBLE_RESULT",
            "SourceProvenance":provenance,
            "PrivateOriginalSourceTapeSha256":private_sha,
            "PolicyProtocolSha256":provenance["ProtocolSha256"],
            "NativeCoreResult":native,
            "OriginalStudyReruns":0,"BrokerRequests":0,
            "BrokerOrders":0,"CloudActivated":False,
            "HistoricalExecutableCostCertified":False,
            "PeriodBOrCUsed":False,
            "EconomicVerdict":"EXPOSED_DEVELOPMENT_MODEL_ONLY_NOT_QUALIFIED"
        }
        (OUT/"v32-integrated-full-public.json").write_text(
            json.dumps(package,indent=2,sort_keys=True,default=str)+"\n")
        compact=[{
            "Multiplier":x["CostMultiplier"],
            "NET_EUR":x["NET_EUR"],
            "NET_Pct":x["NET_VS_CASH_Pct"],
            "CompleteModeledFinancedTrips":x["FundedModeledCompleteTrips"],
            "SampledDD_Pct":x["FloatingSampledDD_Pct"],
            "Weekly":x["Weekly"],
            "HARD21Certified":False
        } for x in policy]
        receipt={
            "SourceRuns":sorted(EXPECTED),"ProtocolSha256":provenance["ProtocolSha256"],
            "AuthenticMarketCount":provenance["Markets"],
            "FullCases":compact,"EligibleWeeksCertified":0,
            "BrokerNETCertified":False,"FloatingIntrabarDDCertified":False,
            "IndependentConfirmation":False,"VERDICT":"NOT_QUALIFIED",
            "Orders":0,"CloudActivated":False
        }
        (OUT/"v32-integrated-gate-public.json").write_text(
            json.dumps(receipt,indent=2,sort_keys=True,default=str)+"\n")
        print("V32_INTEGRATED_EUR300_NATIVE_RESULT " +
            json.dumps({k:v for k,v in receipt.items() if k!="FullCases"},
                       sort_keys=True),flush=True)

if __name__=="__main__":
    try:run()
    except Exception as exc:
        # Never print private bar, identity, FX, underlying library exception message or trace.
        msg=str(exc)
        allowed=(isinstance(exc,ValueError) and
                 (msg.startswith("V32_SOURCE_") or msg.startswith("V32_UNIFIED_")) and
                 all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in msg))
        safe=msg if allowed else type(exc).__name__
        print("V32_PROTECTED_FAILURE_"+safe,flush=True)
        raise SystemExit(1)

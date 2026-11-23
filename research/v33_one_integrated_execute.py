"""ONE V3.3 protected execution: original five-run source -> ONE native C# Core -> aggregate receipt.

Python owns authenticated custody and final serialization only. ALL decisions,
fills, portfolio allocation, cash and NET are in NativeV33PredictiveEconomic,
reusing the exact existing native funded ledger.
"""
import hashlib,json,os,subprocess,tempfile
from pathlib import Path
from .v32_unified_source_adapter import execute as existing_authenticated_five_source
OUT=Path("v33-one-integrated-public")
PROTOCOL=Path("research/V33_SINGLE_PREDICTIVE_ECONOMIC_PROTOCOL_20261123.md")
EXPECTED={"41724643418","41735441128","43817213663","44352570167","45134137836"}

def need(condition,code):
    if not condition: raise ValueError("V33_SINGLE_"+code)

def run():
    need(bool(os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").strip()),"PROTECTED_SOURCE_UNAVAILABLE")
    OUT.mkdir(exist_ok=True,parents=True)
    sha=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="mxm-v33-private-") as directory:
        tape=Path(directory)/"original-authentic-bars-private.json"
        result=Path(directory)/"native-eur300-economic-unaltered.json"
        provenance=existing_authenticated_five_source(tape)
        need(set(provenance["SourceRuns"])==EXPECTED and provenance["Markets"]>=48,
             "FIVE_BROKER_SOURCES_NOT_RECONCILED")
        tape_sha=hashlib.sha256(tape.read_bytes()).hexdigest()
        print("V33_SOURCE_AUTHENTICATED_RECONCILED",flush=True)
        code=subprocess.run([
            "dotnet","run","--no-build","-c","Release","--project","src/Mxm.Replay","--",
            str(tape),str(result),"--v33-one-predictive-integrated-economic",sha],
            capture_output=True,text=True,timeout=9300)
        need(code.returncode==0 and result.is_file(),"NATIVE_CAUSAL_EUR300_EXECUTION_FAILED")
        obj=json.loads(result.read_text())
        need(obj.get("Schema")=="V33_ONE_CAUSAL_PREDICTIVE_FUNDED_EUR300_DEV"
             and obj.get("PreregisteredNewProtocolSha256")==sha
             and set(obj.get("InputRuns",[]))==EXPECTED
             and len(obj.get("Results",[]))==21
             and obj.get("Orders")==0 and obj.get("Cloud") is False
             and obj.get("ClosedStudyReruns")==0
             and obj.get("IndependentConfirmation") is False,
             "UNIFIED_NATIVE_RESULT_CONTRACT_FAILED")
        policies=obj["Results"]
        for row in policies:
            need(row["InitialCapitalEur"]==300 and row["Orders"]==0
                 and row["Cloud"] is False
                 and row["HistoricalNETCertified"] is False
                 and row["HARD21Certified"] is False
                 and row["Financed"] >= row["Completed"]>=0,
                 "NATIVE_EUR300_ACCOUNTING_OR_SAFETY")
        cases=[v for v in policies if v["Policy"]=="FULL"]
        need(sorted(float(v["Multiplier"]) for v in cases)==[1.0,1.5,2.0],
             "PRIMARY_THREE_COST_STRESSES_MISSING")
        package={
            "Schema":"V33_ONE_NATIVE_CAUSAL_ECONOMIC_ORIGINAL_PUBLIC_RESULT",
            "FrozenProtocolSha256":sha,
            "UnderlyingSourceProtocolSha256":provenance["ProtocolSha256"],
            "PrivateAuthenticOriginalTapeSha256":tape_sha,
            "OriginalSourceProvenance":provenance,
            "NativeCompleteResult":obj,
            "OriginalRejectedV32RunId":"45154569433",
            "OriginalRejectedV32Rerun":False,
            "HistoricalExecutionCertified":False,
            "IndependentConfirmation":False,
            "PeriodBOrCUsed":False,
            "BrokerRequests":0,"Orders":0,"Cloud":False,
            "Verdict":"NEW_PREREGISTERED_DEVELOPMENT_ONLY_PENDING_ECONOMIC_GATES"}
        (OUT/"v33-one-integrated-complete-original-public.json").write_text(
            json.dumps(package,indent=2,sort_keys=True,default=str)+"\n")
        gate={
            "FrozenProtocolSha256":sha,
            "SourceRuns":sorted(EXPECTED),
            "AuthenticMarkets":provenance["Markets"],
            "FULL":[{
                "CostMultiplier":x["Multiplier"],
                "Evaluated":x["Evaluated"],"Proposed":x["Proposed"],
                "Accepted":x["Accepted"],"Financed":x["Financed"],
                "Rejected":x["Rejected"],"Completed":x["Completed"],
                "NET_EUR":x["NET_EUR"],"SampledDDPercent":x["SampledDDPercent"],
                "Weekly":x["Weekly"],"HARD21Certified":False,
                "OpenUnresolved":x["RightCensored"]
            } for x in cases],
            "IndependentConfirmation":False,"HistoricalNETCertified":False,
            "HARD21Certified":False,"IntrabarDDCertified":False,
            "BrokerOrders":0,"Cloud":False
        }
        (OUT/"v33-one-integrated-economic-gate-public.json").write_text(
            json.dumps(gate,indent=2,sort_keys=True,default=str)+"\n")
        print("V33_NATIVE_COMPLETE_ECONOMIC_RESULT " +
              json.dumps({k:v for k,v in gate.items() if k!="FULL"},sort_keys=True),
              flush=True)

if __name__=="__main__":
    try:run()
    except Exception as exc:
        value=str(exc)
        allowed=isinstance(exc,ValueError) and (
            value.startswith("V32_SOURCE_") or value.startswith("V33_SINGLE_")) and \
            all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_" for c in value)
        print("V33_PROTECTED_EXECUTION_ERROR_"+(value if allowed else type(exc).__name__),flush=True)
        raise SystemExit(1)

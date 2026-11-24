"""ONE protected CPE1 genuine source-only bridge -> existing native Core engine.

No execution of older V3.2/UCP1/RVC1 economic evaluators. No broker request,
orders, Cloud activation, secret changes, account IDs or full OHLC exported.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from .v32_unified_source_adapter import execute as original_source_only
from .multiscale_conditional_research import recover as recover_original_custody

PROTOCOL=Path("research/CPE1_FROZEN_CAUSAL_FINANCED_PAYOFF_CYCLE_20261124.md")
PUBLIC=Path("cpe1-public")
FROZEN_COMMIT="3d38ee366b5de285b5a928478fa46616093d6b94"

def need(ok,code):
    if not ok: raise ValueError("CPE1_"+code)

def recover_original_contract_swap(tape=None):
    """Actual authenticated BDP1 ProtoOASymbolByIdRes per original read-only account.

    P05 has NO EURUSD/GBPUSD contract; never claim otherwise, do not assign
    weekend or skip fields default=0 when protobuf did not evidence them.
    """
    p=json.loads(Path("research/hrc1_protocol.json").read_text())
    source=next(x for x in p["source"] if x["folder"]=="bdp-source")
    original,decoded,proof=recover_original_custody(
        Path(source["folder"]),source["run"],source["hash"],
        source["schema"],source["protocol"])
    need(proof["rawAccountAndBarsReconstructed"] and proof["newBrokerRequests"]==0,
         "BDP1_RAW_ORIGINAL_ACCOUNT_NOT_VERIFIED")
    expected=({m["Symbol"]:int(m["Terms"]["ObservedAtUtcMs"])
               for m in tape["Markets"] if m.get("Terms")} if tape is not None
              else {s:1793577600000 for s in ("EURUSD","GBPUSD")})
    observed=[]
    required=("swapPeriod","swapTime","chargeSwapAtWeekends","skipSWAPPeriods",
              "swapCalculationType","pipPosition","swapRollover3Days","swapLong","swapShort")
    diagnostics={s:{"Status":"ORIGINAL_CONTRACT_OR_TARIFF_BINDING_UNAVAILABLE",
                    "MissingFields":list(required)}
                 for s in ("EURUSD","GBPUSD")}
    for symbol,metadata in original["symbols"].items():
        if symbol not in expected:continue
        req,response=decoded[metadata["contractRawIndex"]]
        need(type(response).__name__=="ProtoOASymbolByIdRes" and
             len(response.symbol)==1 and
             response.symbol[0].symbolId==metadata["symbolId"],
             "BDP1_CONTRACT_ORIGINAL_IDENTITY_MISMATCH")
        contract=response.symbol[0]
        # The original BDP1 source adapter explicitly stamps these terms at
        # the original BDP1 economic source tariff observation.
        stamp=1793577600000
        if expected[symbol]!=stamp: continue
        # BDP1 contract_snapshot historically omitted swapRollover3Days
        # (and the V32 tape does not carry weekend/skip). Restore all supported
        # funding fields from the authenticated protobuf, not from defaults.
        # Do not mutate the shared adapter or any closed study's inputs.
        if tape is not None:
            terms=next(m["Terms"] for m in tape["Markets"] if m["Symbol"]==symbol)
            mapping={"SwapPeriodHours":"swapPeriod","SwapTimeUtcMinute":"swapTime",
                     "SwapCalculationType":"swapCalculationType","PipPosition":"pipPosition",
                     "TripleSwapWeekday":"swapRollover3Days","LongSwap":"swapLong",
                     "ShortSwap":"swapShort"}
            for key,field in mapping.items():
                raw=getattr(contract,field) if contract.HasField(field) else None
                before=terms.get(key)
                need(before is None or before==raw,"BDP1_EXISTING_TARIFF_FIELD_MISMATCH_"+symbol+"_"+key)
                terms[key]=raw
        weekend=bool(contract.chargeSwapAtWeekends) if contract.HasField(
            "chargeSwapAtWeekends") else None
        skip=int(contract.skipSWAPPeriods) if contract.HasField(
            "skipSWAPPeriods") else None
        observed.append(dict(Symbol=symbol,ChargeSwapAtWeekends=weekend,
            SkipSwapPeriods=skip,ObservedAtUtcMs=stamp,
            OriginalBrokerAuthenticated=True))
        if symbol in diagnostics:
            missing=[f for f in required if not contract.HasField(f)]
            supported=(not missing and int(contract.swapPeriod)==24 and
                       int(contract.swapCalculationType)==0 and
                       0<=int(contract.swapTime)<1440 and
                       int(contract.skipSWAPPeriods)>=0 and
                       1<=int(contract.swapRollover3Days)<=7)
            diagnostics[symbol]={"Status":"COMPLETE_SUPPORTED_CURRENT_SCHEDULE" if supported
                else "UNKNOWN_OR_UNSUPPORTED_CURRENT_SCHEDULE",
                "MissingFields":missing,
                "Fields":{f:getattr(contract,f) if contract.HasField(f) else None
                          for f in required},
                "OriginalBrokerAuthenticated":True,"ObservedAtUtcMs":stamp}
    return observed,dict(Source=proof,Symbols=diagnostics,
        HistoricalTariffContinuityCertified=False,HistoricalBrokerNetCertified=False,
        BrokerRequests=0,Orders=0,CloudActivated=False,ClosedModelsCalled=0)

def preflight_bdp1():
    target=Path("cpe1-bdp1-preflight")
    target.mkdir(exist_ok=True)
    path=target/"cpe1-bdp1-contract-source-only.json"
    try:
        _,report=recover_original_contract_swap()
        report["Scope"]="ORIGINAL_BDP1_SOURCE_ONLY_NO_ECONOMIC_ENGINE"
        path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    except Exception as exc:
        # No raw broker records, account identifier, decrypted archive or
        # environment value may be exported even on failed authentication.
        path.write_text(json.dumps(dict(Scope="BDP1_SOURCE_ONLY",
            Status="AUTHENTIC_SOURCE_RECOVERY_FAILED",ErrorType=type(exc).__name__,
            BrokerRequests=0,Orders=0,CloudActivated=False))+"\n")
        raise RuntimeError("CPE1_BDP1_PREFLIGHT_SOURCE_RECOVERY_FAILED") from None

def main():
    execute(PUBLIC, run_original_native)
    print("CPE1_ORIGINAL_EXPOSED_SOURCE_COMMON_CSHARP_ECONOMIC_RESULT_COMPLETE",flush=True)


def run_original_native(private_input, native, protocol_sha):
    run=subprocess.run(["dotnet","run","--project","src/Mxm.Replay",
        "--no-build","-c","Release","--",
        str(private_input),str(native),
        "--cpe1-one-unified-financed-economics",protocol_sha],
        capture_output=True,text=True,timeout=8400)
    need(run.returncode==0,"ONE_NATIVE_CPE1_ECONOMIC_ENGINE_FAILED_" +
         run.stderr[-900:].replace("\n"," "))


def execute(public, run_native, report_stage=None, recovery=None):
    public.mkdir(exist_ok=True)
    need(PROTOCOL.is_file(),"PRECOMMITTED_PROTOCOL_MISSING")
    protocol_sha=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="cpe1-genuine-causal-") as tmp:
        folder=Path(tmp)
        sealed_bridge=folder/"original-source-only.json"
        private_input=folder/"input-CPE1-accounts.json"
        native=folder/"native-cpe1-integrated-result.json"
        if report_stage:
            report_stage("AUTHENTICATE_ORIGINAL_SOURCES")
        custody=original_source_only(sealed_bridge)
        need(custody["BrokerRequests"]==0 and custody["Orders"]==0 and
             custody["CloudActivated"] is False,
             "ORIGINAL_SOURCE_ONLY_AUTHORITY_VIOLATED")
        tape=json.loads(sealed_bridge.read_text())
        if report_stage:
            report_stage("AUTHENTICATE_ORIGINAL_FUNDING")
        funding,funding_audit=recover_original_contract_swap(tape)
        private_input.write_text(json.dumps(dict(Tape=tape,Funding=funding),
                                            separators=(",",":")))
        private_input.chmod(0o600)
        if report_stage:
            report_stage("START_NATIVE_REPLAY")
        run_native(private_input, native, protocol_sha)
        if report_stage:
            report_stage("VERIFY_AND_WRITE_VERDICT")
        need(native.is_file(),"NATIVE_CPE1_EVIDENCE_MISSING")
        data=native.read_bytes()
        original_sha=hashlib.sha256(data).hexdigest()
        result=json.loads(data)
        need(result["FrozenProtocolSha256"]==protocol_sha and
             result["OrderRequests"]==0 and result["CloudActivated"] is False and
             len(result["BookSummaries"])==9 and
             result["IndependentEvaluation"] is False,
             "NATIVE_CPE1_FINANCIAL_SCOPE_VIOLATION")
        # Public record contains per-episode economics, NOT reconstructed
        # account credentials or raw OHLC/tick histories. No champion selected.
        receipt=dict(Study="CPE1_FROZEN_ONE_COMMON_NATIVE_ACCOUNT_EXPOSED",
            FrozenProtocolAncestor=FROZEN_COMMIT,
            FrozenProtocolSha256=protocol_sha,
            OriginalSourceReceipt=custody,
            NativeOriginalWholeFileSha256=original_sha,
            OriginalBrokerRequests=0,SubmittedBrokerOrders=0,
            CloudActivated=False,OldStudiesRerun=0,
            OriginalBdp1FundingFieldAudit=funding_audit,
            OfficialRecoveredSwap={
                "AttemptedOriginalSource":"BDP1_AUTHENTIC_PROTO_OA_SYMBOL_BY_ID",
                "EURUSD":next((x for x in funding if x["Symbol"]=="EURUSD"),None),
                "GBPUSD":next((x for x in funding if x["Symbol"]=="GBPUSD"),None)
            },
            HistoricalBrokerFillsCertified=False,
            FutureIndependentConfirmation=False,
            Qualifier="DEVELOPMENT_ONLY_RESULT_AFTER_ONLY_ONE_PRECOMMITTED_RUN")
        if recovery is not None:
            receipt["TechnicalRecovery"]=recovery
        (public/"cpe1-source-and-funding-receipt.json").write_text(
            json.dumps(receipt,indent=2,sort_keys=True)+"\n")
        name=("cpe1-original-one-economic.json" if recovery is None else
              "cpe1-recovery-1-economic.json")
        (public/name).write_bytes(data)

if __name__=="__main__":
    if sys.argv[1:]==["--preflight-bdp1"]:
        preflight_bdp1()
    elif not sys.argv[1:]:
        main()
    else:
        raise ValueError("CPE1_UNKNOWN_ARGUMENT")

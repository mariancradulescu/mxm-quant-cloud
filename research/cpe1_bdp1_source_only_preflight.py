"""CPE1 authenticated original BDP1 source readback only. No scoring, broker calls or Cloud."""
import json
from pathlib import Path
from .multiscale_conditional_research import recover as recover_original_custody

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
        # Only the explicitly allowlisted contract fields and public source proof.
        print("CPE1_BDP1_SOURCE_ONLY_RECEIPT="+json.dumps(report,sort_keys=True,separators=(",",":")),flush=True)
    except Exception as exc:
        # No raw broker records, account identifier, decrypted archive or
        # environment value may be exported even on failed authentication.
        path.write_text(json.dumps(dict(Scope="BDP1_SOURCE_ONLY",
            Status="AUTHENTIC_SOURCE_RECOVERY_FAILED",ErrorType=type(exc).__name__,
            BrokerRequests=0,Orders=0,CloudActivated=False))+"\n")
        raise RuntimeError("CPE1_BDP1_PREFLIGHT_SOURCE_RECOVERY_FAILED") from None


if __name__=="__main__":
    preflight_bdp1()

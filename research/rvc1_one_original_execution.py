"""RVC1 source-only authentic custody bridge and single native C# economic replay.

This is NOT a rerun of the V3.2 original economic evaluator. The unchanged
v32_unified_source_adapter.execute() only verifies and serializes the same
original sealed read-only BDP1/AIP1/HXC1/XMH2/P05 market sources. Every RVC1
economic decision, fill model and financial ledger lives in Mxm.Core C#.

No new network requests, broker orders, source prices or account IDs published.
"""
import hashlib
import json
import subprocess
import tempfile
from decimal import Decimal
from pathlib import Path
from .v32_unified_source_adapter import execute as source_only

FROZEN = Path("research/RVC1_FROZEN_JOINT_FX_RESIDUAL_ECONOMICS_20261123.md")
PUBLIC = Path("rvc1-public")

def need(ok,code):
    if not ok: raise ValueError("RVC1_"+code)

def main():
    need(FROZEN.is_file(),"FROZEN_PROTOCOL_MISSING")
    frozen_hash=hashlib.sha256(FROZEN.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="mxm-rvc1-original-") as folder:
        workspace=Path(folder)
        raw=workspace/"verified-source.json"
        native=workspace/"rvc1-private-economic.json"
        receipt=source_only(raw)  # CUSTODY + RAW BAR IDENTITY ONLY; no old model
        need(receipt.get("BrokerRequests")==0 and
             receipt.get("Orders")==0 and
             receipt.get("CloudActivated") is False,
             "SOURCE_ONLY_AUTHORITY_VIOLATION")
        source=json.loads(raw.read_text())
        names={x["Symbol"] for x in source["Markets"]}
        need({"EURUSD","GBPUSD"}.issubset(names),
             "ORIGINAL_RVC1_MARKET_COVERAGE_MISSING")
        for market in source["Markets"]:
            if market["Symbol"] not in ("EURUSD","GBPUSD"): continue
            need(all(k in market["Bars"] and len(market["Bars"][k])>=48
                for k in ("M5","M15","H1")),"ORIGINAL_CLOSED_CONTEXT_MISSING")
        process=subprocess.run([
            "dotnet","run","--project","src/Mxm.Replay","--no-build",
            "-c","Release","--",str(raw),str(native),
            "--rvc1-frozen-joint-fx-residual-economic",frozen_hash
        ],capture_output=True,text=True,timeout=8500)
        need(process.returncode==0,
             "NATIVE_INTEGRATED_ECONOMICS_FAILED_NOT_CERTIFIED")
        need(native.is_file(),"NATIVE_ORIGINAL_OUTPUT_MISSING")
        private=native.read_bytes()
        original_sha=hashlib.sha256(private).hexdigest()
        result=json.loads(private)
        need(result.get("Version")==
             "RVC1_FROZEN_FX_JOINT_RESIDUAL_DEVELOPMENT_ONLY",
             "CORE_VERSION_UNEXPECTED")
        need(result.get("FrozenProtocolSha256")==frozen_hash and
             result.get("BrokerOrders")==0 and
             result.get("CloudActivated") is False and
             result.get("ClosedStudyReruns")==0 and
             result.get("IndependentConfirmation") is False,
             "SOURCE_ORIGINAL_SCOPE_VIOLATION")
        need(len(result["Books"])==12,"SINGLE_PROGRAM_BOOKS_INCOMPLETE")
        expected={(policy,str(factor)) for policy in
                  ("JOINT_RESIDUAL","PAIRED_NO_CONVERGENCE","SINGLE_EURUSD","CASH")
                  for factor in ("1","1.5","2")}
        actual={(b["Policy"],str(Decimal(str(b["Factor"])))) for b in result["Books"]}
        need(actual==expected,"ORIGINAL_COMPARATOR_MISMATCH")
        # Independent arithmetic verification only. C# is the sole economic
        # authority; Python does NOT choose opportunities or alter any P&L.
        books=[]
        for b in result["Books"]:
            sums=sum((Decimal(str(f["NetEur"]))
                      for f in b["ClosedFragments"]),Decimal(0))
            actual_net=Decimal(str(b["ClosedNetEUR"]))
            cash=Decimal(str(b["ClosingCashEur"]))
            need(abs(sums-actual_net)<Decimal(".000000001") and
                 abs(cash-Decimal(300)-actual_net)<Decimal(".000000001"),
                 "NATIVE_LEDGER_CASH_FRAGMENT_IDENTITY")
            pub={k:v for k,v in b.items() if k not in ("ClosedFragments",)}
            pub["FragmentCount"]=len(b["ClosedFragments"])
            pub["HistoricalFillProof"]=False
            pub["NetEconomicQualification"]=(
                "NOT_CERTIFIED_OPEN_OR_UNKNOWN" if not b["IsFullySettled"] or
                b["Incomplete"] or b["UnknownFunding"] else
                "MODELED_ONLY_DEVELOPMENT")
            books.append(pub)
        PUBLIC.mkdir(exist_ok=True)
        public={
            "Schema":"rvc1-one-original-source-native-common-book-development-v1",
            "OriginalRuns":result["OriginalSources"],
            "FrozenProtocolSha256":frozen_hash,
            "InputNativeOriginalReceipt":receipt,
            "PrivateWholeNativeOutputSha256":original_sha,
            "CommonM5SourceClocks":result["CommonM5Clocks"],
            "AllSourceISOWeeks":result["CommonISOWeeks"],
            "CurrentTermCostsOnly":True,
            "AllHistoricalPeriodsAlreadyExposed":True,
            "TrueBrokerOrders":0,"CloudEnabled":False,
            "IndependenceOrHistoricalFillCertification":False,
            "Qualification":"NOT_ESTABLISHED_DESCRIPTIVE_EXPOSED",
            "Books":books
        }
        (PUBLIC/"rvc1-original-public.json").write_text(
            json.dumps(public,indent=2,sort_keys=True)+"\n")
        print("RVC1_ORIGINAL_REUSE_CSHARP_ECONOMICS_COMPLETE_NO_BROKER_ORDER",flush=True)

if __name__=="__main__":
    main()

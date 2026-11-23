"""PEL1 ONE original-custody replay. Source I/O only; all economic decisions in native Core.
No broker requests, no orders, no tick/quote publication, no Python financial engine.
"""
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from .custody import unseal_new

ORIGINAL_RUN = "44162043538"
ORIGINAL_NATIVE_SHA = "ccd0cd7b4c659a24045023475c51680b2c8800d6879f6f74430ed429dcc2fee9"
PROTOCOL = Path("research/PEL1_FROZEN_PASSIVE_LIQUIDITY_20261123.md")
INPUT = Path("cvp1-original-source/native-tape.enc")
OUTPUT = Path("pel1-public")
def need(condition,code):
    if not condition:
        raise ValueError("PEL1_"+code)

def execute():
    key=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    need(bool(key.strip()),"EXISTING_CUSTODY_KEY_NOT_AVAILABLE")
    need(PROTOCOL.is_file() and INPUT.is_file(),"ORIGINAL_PROTOCOL_OR_SOURCE_NOT_AVAILABLE")
    protocol_sha=hashlib.sha256(PROTOCOL.read_bytes()).hexdigest()
    original=unseal_new(INPUT.read_bytes(),key,ORIGINAL_RUN)
    need(hashlib.sha256(original).hexdigest()==ORIGINAL_NATIVE_SHA,
         "CVP1_ORIGINAL_NATIVE_TAPE_HASH_MISMATCH")
    # Never print data, prices, account identifiers, tokens or raw records.
    raw=json.loads(original)
    need(raw.get("Start")==1777852800000 and raw.get("End")==1785110400000,
         "ORIGINAL_CALENDAR_MISMATCH")
    need([x.get("Name") for x in raw.get("Markets",[])]==
         ["EURUSD","GBPUSD","AUDUSD"],"FROZEN_MARKET_ORDER_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="pel1-private-source-") as folder:
        folder=Path(folder)
        private=folder/"original-source.json"
        private.write_bytes(original);private.chmod(0o600)
        del raw, original
        result=folder/"economic.json"
        process=subprocess.run([
            "dotnet","run","--no-build","--project","src/Mxm.Replay","-c","Release",
            "--",str(private),str(result),
            "--pel1-one-passive-limit-economic",protocol_sha],
            text=True,capture_output=True,timeout=8000)
        need(process.returncode==0,"NATIVE_CSHARP_ECONOMIC_EXECUTION_FAILED")
        need(result.is_file(),"NATIVE_ORIGINAL_RESULT_MISSING")
        data=result.read_bytes()
        output_sha=hashlib.sha256(data).hexdigest()
        d=json.loads(data)
        need(d.get("Version")==
             "PEL1_PASSIVE_LIMIT_PRICE_IMPROVEMENT_CSHARP_ORIGINAL_EXPOSED",
             "CORE_VERSION_MISMATCH")
        need(d.get("FrozenProtocolSha256")==protocol_sha and
             d.get("SourceSha256")==ORIGINAL_NATIVE_SHA and
             d.get("Orders")==0 and d.get("Cloud") is False,
             "AUTHORITY_CUSTODY_MISMATCH")
        books=d["Books"]
        need(len(books)==12 and
             len({(b["Policy"],str(b["CostMultiplier"])) for b in books})==12,
             "PRESPECIFIED_ALL_BOOKS_MISSING")
        clean=[]
        for b in books:
            # Trip-level signal timing and broker-derived prices remain PRIVATE.
            pub={k:v for k,v in b.items() if k not in ("Trips","Summary")}
            # Compact public signed aggregate/chain/witness; never claim real fills.
            pub["FinalPositionsCount"]=b["Summary"]["OpenPositions"]
            pub["LedgerPendingCount"]=b["Summary"]["PendingIntents"]
            pub["LedgerCashIdentityEur"]=b["FinalCashEur"]-300-float(b["LedgerClosedNetEur"])
            need(abs(pub["LedgerCashIdentityEur"])<1e-6,"CASH_LEDGER_RECONCILIATION")
            pub["FrozenTerminalClassification"]="CONDITIONALLY_SETTLED" if b["FinalFullySettled"] else "OPEN_OR_UNKNOWN"
            clean.append(pub)
        OUTPUT.mkdir(exist_ok=True)
        report=dict(Schema="pel1-original-authentic-custody-native-conditional-v1",
            OriginalSourceRun=int(ORIGINAL_RUN),
            OriginalNativeTapeSha256=ORIGINAL_NATIVE_SHA,
            FrozenProtocolSha256=protocol_sha,
            PrivateNativeCompleteResultSha256=output_sha,
            SourceGloballyExposed=True,
            OriginalHistoricalCostCertification=False,
            BrokerLimitFillCertification=False,
            EquityContinuousDdcertification=False,
            TwelveMonthFutureIndependentConfirmation=False,
            AllPolicyTrialsRecorded=True,
            ResearchAuthorizedOnce=True,
            SourceAcquisitionRequests=0,TradingOrders=0,CloudActivated=False,
            Status="ORIGINAL_DEVELOPMENT_ECONOMIC_EVIDENCE_NOT_PRODUCT_QUALIFICATION",
            Books=clean)
        out=OUTPUT/"original-public.json"
        out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
        print("PEL1_CUSTODY_AND_NATIVE_ORIGINAL_COMPLETED_NO_SECRET_NO_ORDER",flush=True)

if __name__=="__main__":
    execute()

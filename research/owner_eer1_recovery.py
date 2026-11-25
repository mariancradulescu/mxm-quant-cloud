"""EER1 immutable-source recovery diagnostics. No broker credentials or calls."""
import ast
import json
import os
import subprocess
from pathlib import Path
from . import owner_eer1_source as eer
from . import source_history_universe as src
from .decode import need
from .guard import CaptureContractError

ORIGINAL_RUN="45555613548"
ORIGINAL_HEAD="a148bf0ecc954848bc067ee9ff938bebd900ed24"
ARTIFACT_ID=15000522105
ARTIFACT_SHA="107b2bc43e6ff25a5799e253b0ab6ee718ad5b88ef3bb3211d84ad6c20b87a5b"
REQUESTS=10791

def original_collect():
    # Extract only the original function. Globals are the unchanged original
    # dependencies; no source module main or transport constructor is executed.
    source=subprocess.check_output(["git","show",ORIGINAL_HEAD+":research/owner_eer1_source.py"],text=True)
    node=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=="collect_market")
    namespace=dict(vars(eer))
    exec(compile(ast.Module(body=[node],type_ignores=[]),"<frozen EER1 collect_market>","exec"),namespace)
    return namespace["collect_market"]

def request_geometry(q):
    return {k:getattr(q,k) for k in ("symbolId","type","period","fromTimestamp","toTimestamp") if k in q.DESCRIPTOR.fields_by_name and q.HasField(k)}

class DiagnosticJournal(src.ReadbackJournal):
    mismatch=None
    def query(self,q):
        idx=self.index
        try:
            return super().query(q)
        except CaptureContractError as exc:
            if str(exc)=="HISTORY_READBACK_REQUEST_OR_CLOCK" and idx<len(self.packets):
                rec=self.packets[idx]
                expected=src.decode(rec["reqType"],rec["req"])
                self.mismatch=dict(index=idx,expected=request_geometry(expected),reconstructed=request_geometry(q),
                    expectedType=rec["reqType"],reconstructedType=type(q).__name__,
                    sameAccount=expected.ctidTraderAccountId==q.ctidTraderAccountId,
                    validOriginalClock=0<rec["requestAt"]<=rec["availableAt"])
            raise

def verify_original(receipt):
    need(receipt["runId"]==ORIGINAL_RUN and len(receipt["sources"])==16 and
         sum(r["requests"] for r in receipt["sources"])==REQUESTS,"EER1_RECOVERY_ORIGINAL_GEOMETRY")
    need(len({r["name"] for r in receipt["sources"]})==16 and len({r["file"] for r in receipt["sources"]})==16,
         "EER1_RECOVERY_UNIQUE_SHARDS")
    expected={"receipt.json",receipt["metadata"]["file"]}|{r["file"] for r in receipt["sources"]}
    need({p.name for p in eer.OUT.iterdir()}==expected,"EER1_RECOVERY_FILE_INVENTORY")

def prove_shadow(receipt,key,account,rows,chosen,charges,out):
    fn=original_collect()
    ref=next(r for r in receipt["sources"] if r["name"]=="EURUSD")
    data=eer.unpack(eer.OUT,ref,key,ORIGINAL_RUN)
    need(data["runId"]==ORIGINAL_RUN and data["name"]==ref["name"] and data["id"]==ref["id"],"EER1_DIAGNOSTIC_SHARD")
    args=(account,ref["id"],rows.get(ref["name"],{}),ref["name"] in chosen,charges,True,ref["name"])
    bad=DiagnosticJournal(data["packets"])
    try:
        fn(bad,*args)
    except CaptureContractError as exc:
        need(str(exc)=="HISTORY_READBACK_REQUEST_OR_CLOCK" and bad.mismatch is not None and
            bad.mismatch["sameAccount"] and bad.mismatch["validOriginalClock"],"EER1_DIAGNOSTIC_DIFFERENT_FAILURE")
    else:
        need(False,"EER1_ORIGINAL_DEFECT_NOT_REPRODUCED")
    good=src.ReadbackJournal(data["packets"])
    summary,_,quotes,funding=eer.collect_market(good,*args)
    need(summary==ref["summary"]==data["summary"] and good.index==len(data["packets"])==ref["requests"],"EER1_DIAGNOSTIC_FIXED_PARITY")
    proof=dict(originalRun=ORIGINAL_RUN,originalArtifact=ARTIFACT_ID,archiveSha256=ARTIFACT_SHA,
        symbol=ref["name"],originalFailure="HISTORY_READBACK_REQUEST_OR_CLOCK",firstMismatch=bad.mismatch,
        correctedRequests=good.index,summaryIdentical=True,newQuoteMarks=len(quotes),fundingMarks=len(funding),
        originalSourceRecollected=False,brokerRequests=0,orders=0,cloudActivated=False)
    (out/"defect-proof.json").write_bytes(src.canonical(proof))
    print("EER1_ORIGINAL_DEFECT_REPRODUCED_AND_FIXED",ref["name"],bad.mismatch["index"],good.index,flush=True)

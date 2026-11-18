"""OEI1 A1 corrected economics, same untouched original encrypted native tape.

Only existing protected custody key. No Pepperstone/OAuth/network in this module.
No original results overwritten, and never an independent market confirmation.
"""
import hashlib,json,os
from pathlib import Path
from .custody import unseal_new
from .oei1_integrated import run

ORIGINAL_RUN="44247979857"
FROZEN_PROTOCOL_SHA="018af64f3fe2836fa6efe77665a8d3e0655af415"
ROOT=Path("oei1-original-source")
PUBLIC=Path("oei1-original-public")
OUT=Path("oei1-a1-public")

def need(ok,code):
    if not ok:raise ValueError("OEI1_A1_"+code)

def main():
    OUT.mkdir(exist_ok=True)
    summary=dict(Study="OEI1_A1_CAUSAL_SOURCE_REUSE",OriginalRun=int(ORIGINAL_RUN),
                 OriginalSourceRecollected=False,OrdersSubmitted=0,CloudActivated=False,
                 IndependentConfirmation=False,RecoveryProtocolCommit=FROZEN_PROTOCOL_SHA)
    try:
        paths=list(ROOT.rglob("oei1-native-tape.enc"))
        sourcepaths=list(PUBLIC.rglob("source.json"))
        need(len(paths)==1 and len(sourcepaths)==1,"ORIGINAL_ENCRYPTED_TAPE_OR_SOURCE_RECEIPT_UNAVAILABLE")
        source=json.loads(sourcepaths[0].read_text())
        need(str(source.get("OriginalRun"))==ORIGINAL_RUN,"ORIGINAL_RUN_ID_MISMATCH")
        need(source.get("SourceSha256") is not None
             and source.get("SourceCipherSha256") is not None,
             "ORIGINAL_SOURCE_HASH_MISSING")
        cipher=paths[0].read_bytes()
        cipherhash=hashlib.sha256(cipher).hexdigest()
        need(cipherhash==source["SourceCipherSha256"],"ORIGINAL_CIPHERTEXT_HASH_MISMATCH")
        secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
        need(bool(secret.strip()),"INSTALLED_CUSTODY_KEY_MISSING")
        plaintext=unseal_new(cipher,secret,ORIGINAL_RUN)
        sha=hashlib.sha256(plaintext).hexdigest()
        need(sha==source["SourceSha256"],"ORIGINAL_PLAINTEXT_HASH_MISMATCH")
        tape=json.loads(plaintext)
        need(tape["Start"]==source["SourceStartUtc"] and
             tape["End"]==source["SourceEndUtc"],"ORIGINAL_WINDOW_MISMATCH")
        result=run(tape)
        result.update(Study="OEI1_A1_CORRECTED_CAUSAL_3PHASE",
                      OriginalSourceRun=int(ORIGINAL_RUN),
                      OriginalSourceSha256=sha,
                      OriginalCipherSha256=cipherhash,
                      OriginalProtocolSha256=source["ProtocolSha256"],
                      CorrectiveProtocolCommit=FROZEN_PROTOCOL_SHA,
                      CorrectiveTechnicalResult=True,
                      SourceRecollection=False,
                      OriginalResultsReplaced=False,
                      CausalLeakageFixedBeforeOriginalOutcomeInspection=True,
                      OriginalGlobalCalendarExposed=True,
                      Qualified=False,IndependentConfirmation=False,
                      OrdersSubmitted=0,CloudActivated=False)
        (OUT/"economic.json").write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
        summary.update(Status=result["Status"],OriginalSourceSha256=sha,
                       OriginalCipherSha256=cipherhash,
                       Phase1Evaluated=bool(result.get("Phase1")),
                       Phase2Evaluated=bool(result.get("Phase2",{}).get("Evaluation")),
                       Phase3Evaluated=bool(result.get("Phase3",{}).get("adverse")),
                       ResultSha256=hashlib.sha256((OUT/"economic.json").read_bytes()).hexdigest())
        (OUT/"receipt.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        print("OEI1_A1_CORRECTED_SOURCE_REUSE",json.dumps({
            "status":result["Status"],"original_source_sha256":sha,
            "classes":result.get("Phase1",{}).get("ScopeClasses"),
            "phase2_samples":result.get("Phase2",{}).get("EvaluationSampleCount"),
            "adverse_net":{name:book["ClosedNetEur"] for name,book in
                result.get("Phase3",{}).get("adverse",{}).items()}
                if "adverse" in result.get("Phase3",{}) else None},sort_keys=True),flush=True)
    except Exception as exc:
        summary["Status"]="TECHNICAL_RECOVERY_FAILED_NO_PROMOTION"
        summary["FailureType"]=type(exc).__name__
        (OUT/"receipt.json").write_text(json.dumps(summary,sort_keys=True,indent=2)+"\n")
        raise

if __name__=="__main__":main()

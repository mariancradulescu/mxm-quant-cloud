"""Cold, protected, SAME original new-source v2 ciphertext; NO new broker request.

Run-bound v2 decryption, frozen original C# readback parity and a SECOND
native C# causal score mode. Public output contains only pooled statistics.
Never rewrites the source artifact or submits orders; never promotes NET.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from .custody import unseal_new

SOURCE_RUN_ID = "41467047520"

def assess():
    private=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
    if not private.strip():
        raise ValueError("COLD_SOURCE_CUSTODY_MISSING")
    if os.environ.get("MXM_FROZEN_SOURCE_RUN_ID") != SOURCE_RUN_ID:
        raise ValueError("COLD_SOURCE_RUN_ID_NOT_FROZEN")
    folder=Path("sealed-output")
    sealed=(folder/"source.envelope.json").read_bytes()
    source_receipt=json.loads((folder/"receipt.public.json").read_text())
    if source_receipt.get("status")!="NEW_SOURCE_V2_RECEIPT_ONLY" or (
        hashlib.sha256(sealed).hexdigest()!=source_receipt.get("ciphertextSha256")):
        raise ValueError("COLD_SOURCE_SEALED_HASH_MISMATCH")
    payload=json.loads(unseal_new(sealed,private,SOURCE_RUN_ID))
    original_receipt=payload.pop("csharpReceipt")
    if payload.get("source")!="Pepperstone-cTrader-OpenAPI" or (
        payload.get("readOnly") is not True) or len(payload.get("bars",[]))==0:
        raise ValueError("COLD_SOURCE_BUNDLE_NOT_AUTHENTICATED")
    env={k:v for k,v in os.environ.items() if not k.startswith(
        ("R3_","CTRADER_","MXM_V4_"))}
    executable="src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
    with tempfile.TemporaryDirectory(prefix="mxm-cold-source-") as tmp:
        source=Path(tmp)/"source.json"
        source.write_text(json.dumps(payload,sort_keys=True))
        source.chmod(0o600)
        prior=Path(tmp)/"parity.json"
        predicted=Path(tmp)/"prequential.json"
        p=subprocess.run(["dotnet",executable,str(source),str(prior)],
            env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        if p.returncode!=0 or json.loads(prior.read_text())!=original_receipt:
            raise ValueError("COLD_SOURCE_ORIGINAL_CSHARP_PARITY_FAILED")
        q=subprocess.run(["dotnet",executable,str(source),str(predicted),
                          "--score-causal"],env=env,stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
        if q.returncode!=0:
            raise ValueError("COLD_SOURCE_CAUSAL_SCORING_FAILED")
        result=json.loads(predicted.read_text())
    if result.get("schema")!="mxm.causal-range-pressure-authentic-observation-only.v1":
        raise ValueError("COLD_SCORE_SCHEMA_INVALID")
    if result.get("ordersSubmitted")!=0 or result.get("netEurQualified") is not False:
        raise ValueError("COLD_SCORE_CLAIMS_TRADING_OR_NET")
    public={
        "schema":"mxm.authenticated-new-source-causal-score-cold.v1",
        "frozen_source_action_run":int(SOURCE_RUN_ID),
        "frozen_native_csharp_model":"CausalRangePressureResearch (PR #4; no retuning)",
        "encrypted_source_sha256":source_receipt["ciphertextSha256"],
        "custody_v2_readback_and_original_csharp_parity":True,
        "csharp_native_new_evaluation":True,
        "observed_bars":result["sourceBars"],
        "observed_iso_weeks":result["sourceObservedWeeks"],
        "scored_prequential_predictions":result["forecastScored"],
        "brier":result["meanBrier"],
        "constant_half_brier_baseline":result["neutralMeanBrier"],
        "brier_skill_relative_to_neutral":result["brierSkill"],
        "qualification":result["qualification"],
        "candidate_screen_verdict":(
            "INSUFFICIENT_CAUSAL_TARGETS" if not result["publicScoreAdmitted"] else
            "CLOSED_NONPOSITIVE_PREQUENTIAL_SKILL" if result["brierSkill"] <= 0 else
            "PRICE_ONLY_SKILL_POSITIVE_BUT_NET_UNQUALIFIED"),

        "decrypted_private_source_exported":False,
        "broker_requests_this_run":0,
        "historical_rejected_models_reexecuted":0,
        "net_eur_demonstrated":False,
        "broker_compatible_hard21_demonstrated":False,
        "independent_twelve_month_confirmation":False,
        "orders_submitted":0,
        "cloud_activated":False,
    }
    Path("causal-cold-score.public.json").write_text(
        json.dumps(public,sort_keys=True,indent=2)+"\n")
    print("AUTHENTIC_CAUSAL_PREQUENTIAL_COLD_SCORE_COMPLETED_NOT_NET_QUALIFIED")
    return public

def main():
    try:
        public=assess()
        # Public-safe pooled metrics only, to permit independent GitHub LIVE
        # inspection without decrypting or downloading any private artifact.
        fields=("observed_bars","observed_iso_weeks","scored_prequential_predictions",
            "brier","constant_half_brier_baseline",
            "brier_skill_relative_to_neutral","candidate_screen_verdict")
        print("CAUSAL_COLD_PUBLIC_AGGREGATE "+json.dumps(
            {k:public[k] for k in fields},sort_keys=True),flush=True)
    except Exception:
        print("CAUSAL_COLD_SCORE_FAILED_DETAIL_WITHHELD")
        sys.exit(1)

if __name__=="__main__":
    main()

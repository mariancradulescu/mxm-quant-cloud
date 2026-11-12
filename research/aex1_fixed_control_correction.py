"""Revalue ONLY the technically miswired fixed-90 control on original AEX1 source.

No original strategy rerun, original receipts unchanged, zero broker access.
"""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new

SOURCE_RUN = "43036474843"
SOURCE_ARTIFACT = 13863803890
SOURCE_ENVELOPE_SHA = "c780798f12380a3be2a546f1a18f7cf14be774d9377eb535bfa9d82ccee4909d"
SOURCE_TAPE_SHA = "4decd33d6c4c66a5dfbf63b4a790d062e21ff65db3f8eed034db45f72b296d60"
ORIGINAL_AEX1_PUBLIC_SHA = "6c601caa12d91f2f4661460082a18992be791fc0bd7ae1507e07de5b8269fba9"


def main():
    old_receipt = Path("original-receipt/aex1-public.json").read_bytes()
    if sha256(old_receipt).hexdigest() != ORIGINAL_AEX1_PUBLIC_SHA:
        raise ValueError("AEX1_ORIGINAL_RESULT_HASH_MISMATCH")
    original = json.loads(old_receipt)
    if original["Study"] != "AEX1":
        raise ValueError("AEX1_ORIGINAL_STUDY_MISMATCH")
    prior = original["SameOpportunityFixed90Control"]
    if not any(v>0 for k, v in prior.get("ExitReasonCounts",{}).items()
               if k != "FROZEN_LEGACY_TIME"):
        raise ValueError("AEX1_CORRECTION_NOT_APPLICABLE")
    sealed = Path("original-source/fce1-native-tape.v2.enc").read_bytes()
    if sha256(sealed).hexdigest() != SOURCE_ENVELOPE_SHA:
        raise ValueError("AEX1_SOURCE_ENVELOPE_HASH_MISMATCH")
    secret = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    raw = unseal_new(sealed,secret,SOURCE_RUN)
    del secret
    if sha256(raw).hexdigest() != SOURCE_TAPE_SHA:
        raise ValueError("AEX1_SOURCE_PLAINTEXT_HASH_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="mxm-aex1-fixed-correction-") as directory:
        source = Path(directory) / "original.json"
        report = Path(directory) / "technical-control.json"
        source.write_bytes(raw)
        source.chmod(0o600)
        del raw
        subprocess.run([
            "dotnet","src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
            str(source),str(report),"--native-aex1-fixed-control-correction"
        ],check=True,timeout=900)
        correction=json.loads(report.read_text())
    if correction["SourceSha256"] != SOURCE_TAPE_SHA:
        raise ValueError("AEX1_CSHARP_SOURCE_HASH_MISMATCH")
    correction.update({
        "OriginalAex1ReceiptSha256":ORIGINAL_AEX1_PUBLIC_SHA,
        "OriginalAex1JointAdverseNetEur":original["Joint"]["ModelClosedAdverseNetEur"],
        "OriginalMiswiredControlAdverseNetEur":prior["ModelClosedAdverseNetEur"],
        "OriginalMiswiredControlExitReasons":prior["ExitReasonCounts"],
        "OriginalAex1ClosedTrades":original["Joint"]["CompletedModelRoundTrips"],
        "OriginalSourceRunId":int(SOURCE_RUN),
        "OriginalSourceArtifactId":SOURCE_ARTIFACT,
        "OriginalSourceCiphertextSha256":SOURCE_ENVELOPE_SHA,
        "ProtocolSha256":sha256(Path("research/AEX1_FIXED_CONTROL_CORRECTION.md").read_bytes()).hexdigest(),
        "BrokerRequests":0,
        "IndependentConfirmation":False,
        "OrdersSubmitted":0,"CloudActivated":False
    })
    Path("aex1-fixed-control-correction.json").write_text(
        json.dumps(correction,indent=2)+"\n")
    print(json.dumps({
        "Study":correction["Study"],
        "FixedClosures":correction["CorrectedControl"]["CompletedModelRoundTrips"],
        "FixedAdverseNetEur":correction["CorrectedControl"]["ModelClosedAdverseNetEur"],
        "ActualFixedExits":correction["CorrectedControl"]["ExitReasonCounts"],
        "UnchangedJointAdverseNetEur":correction["OriginalAex1JointAdverseNetEur"],
    }),flush=True)


if __name__ == "__main__":
    main()

"""JRA1 new research: verify and reuse original IPC2 sealed Pepperstone tape.

No old study evaluator, no external market requests, no original raw tape output.
The read-only source was independently collected in original Actions 43176793567.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new

SOURCE_RUN = "43176793567"
SOURCE_ARTIFACT = 13925405999
SOURCE_CIPHER = "aceca6ea879201ce16caba708a1ae47a953ad66e6b58977fe044bbd4b740e64a"
SOURCE_RAW = "fd7986487be347376aa1e139915f90786155d2b1b6de1787382aa7d8666faeaf"

def main():
    envelope = Path("original-source/ipc2-native-tape.v2.enc").read_bytes()
    if hashlib.sha256(envelope).hexdigest() != SOURCE_CIPHER:
        raise ValueError("JRA1_ORIGINAL_ENCRYPTED_SOURCE_SHA_MISMATCH")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(envelope, key, SOURCE_RUN)
    del key
    if hashlib.sha256(tape).hexdigest() != SOURCE_RAW:
        raise ValueError("JRA1_ORIGINAL_PLAINTEXT_SHA_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="jra1-source-private-") as folder:
        source = Path(folder) / "original-plaintext.json"
        result = Path(folder) / "original-jra1-result.json"
        source.touch(mode=0o600)
        source.write_bytes(tape)
        del tape
        subprocess.run([
            "dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
            str(source), str(result), "--native-jra1"
        ], check=True, timeout=1000)
        report = json.loads(result.read_text())
    if (report["OriginalSourcePlaintextSha256"] != SOURCE_RAW or
            report["OriginalSourceArtifactId"] != SOURCE_ARTIFACT or
            report["OrdersSent"] != 0 or report["CloudActivated"] is not False or
            report["HistoricalTariffCertified"] is not False or
            report["Qualified"] is not False):
        raise ValueError("JRA1_EVIDENCE_OR_CLAIM_UNSAFE")
    report.update(
        ExecutionRunId=int(os.environ["GITHUB_RUN_ID"]),
        OriginalActionsId=int(SOURCE_RUN),
        OriginalSourceRecollected=False,
        ProtocolSha256=hashlib.sha256(
            Path("research/JRA1_JOINT_RISK_PROTOCOL_20261117.md").read_bytes()
        ).hexdigest()
    )
    Path("jra1-native-original.public.json").write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n")
    for name, value in report["Reports"].items():
        print("JRA1_FUNDED_MODEL", name, json.dumps({
            k: value.get(k) for k in (
                "NativeCompleteFundedModelRoundTrips", "ClosedNetEur",
                "AdverseClosedNetEur", "EndCashEur", "SampledMarkDrawdown",
                "MaxReservedStressEur", "PretradeRiskRejections",
                "NativeSelectorRejections", "HistoryIncomplete",
                "MissingHeldQuoteMarks", "OpenPositions"
            )
        }, sort_keys=True), flush=True)

if __name__ == "__main__":
    main()

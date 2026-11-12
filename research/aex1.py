"""Execute AEX1 once on the original, unchanged FCE1 Pepperstone tape in custody.

This is a NEW exploratory prediction+adaptive exit mechanism, not a rerun of
FCE1, JRS1, WFG1, or any of their closed strategy configurations.
No Open API calls, trading orders, refresh flow or raw-source publication.
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


def main():
    sealed = Path("original-source/fce1-native-tape.v2.enc").read_bytes()
    if sha256(sealed).hexdigest() != SOURCE_ENVELOPE_SHA:
        raise ValueError("AEX1_ENCRYPTED_SOURCE_HASH_MISMATCH")
    secret = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(sealed, secret, SOURCE_RUN)
    del secret
    if sha256(tape).hexdigest() != SOURCE_TAPE_SHA:
        raise ValueError("AEX1_PLAINTEXT_SOURCE_HASH_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="mxm-aex1-original-custody-") as folder:
        source, output = Path(folder) / "source.json", Path(folder) / "result.json"
        source.write_bytes(tape)
        source.chmod(0o600)
        del tape
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source), str(output), "--native-aex1"],
                       check=True, timeout=900)
        report = json.loads(output.read_text())
    if report["SourceSha256"] != SOURCE_TAPE_SHA:
        raise ValueError("AEX1_CSHARP_SOURCE_HASH_MISMATCH")
    report.update(ProtocolSha256=sha256(Path("research/AEX1.md").read_bytes()).hexdigest(),
                  SourceRunId=int(SOURCE_RUN), SourceArtifactId=SOURCE_ARTIFACT,
                  SourceCiphertextSha256=SOURCE_ENVELOPE_SHA,
                  SourceClassification="ORIGINAL_PEPPERSTONE_EXPOSED_DEVELOPMENT",
                  BrokerRequests=0, OrdersSubmitted=0, CloudActivated=False,
                  IndependentConfirmation=False, InitialModelCapitalEur=300)
    Path("aex1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"Study": "AEX1", "Closures": report["Joint"]["CompletedModelRoundTrips"],
                      "AdverseEur": report["Joint"]["ModelClosedAdverseNetEur"],
                      "FixedControlAdverseEur": report["SameOpportunityFixed90Control"]["ModelClosedAdverseNetEur"],
                      "MissingHeldMarks": report["JointHeldMinuteCoverage"]["MissingTradeHeldMinuteMarks"]}))


if __name__ == "__main__":
    main()

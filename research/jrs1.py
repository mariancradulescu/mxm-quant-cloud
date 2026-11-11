"""Evaluate a new policy on the verified, unchanged FCE1 input tape."""
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
        raise ValueError("JRS1_ORIGINAL_ENVELOPE_HASH_MISMATCH")
    secret = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(sealed, secret, SOURCE_RUN)
    del secret
    if sha256(tape).hexdigest() != SOURCE_TAPE_SHA:
        raise ValueError("JRS1_ORIGINAL_TAPE_HASH_MISMATCH")
    with tempfile.TemporaryDirectory(prefix="mxm-jrs1-custody-") as folder:
        source, output = Path(folder) / "tape.json", Path(folder) / "result.json"
        source.write_bytes(tape)
        source.chmod(0o600)
        del tape
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source), str(output), "--native-jrs1"],
                       check=True, timeout=600)
        report = json.loads(output.read_text())
    if report["SourceSha256"] != SOURCE_TAPE_SHA:
        raise ValueError("JRS1_NATIVE_INPUT_HASH_MISMATCH")
    report.update(ProtocolSha256=sha256(Path("research/JRS1.md").read_bytes()).hexdigest(),
                  SourceRunId=int(SOURCE_RUN), SourceArtifactId=SOURCE_ARTIFACT,
                  SourceCiphertextSha256=SOURCE_ENVELOPE_SHA,
                  SourceClassification="ORIGINAL_PEPPERSTONE_REUSED_EXPOSED_DEVELOPMENT",
                  ExpectedMinuteClocks=7200,
                  BrokerRequests=0, OrdersSubmitted=0, CloudActivated=False,
                  IndependentConfirmation=False, InitialModelCapitalEur=300)
    Path("jrs1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    r = report["Receipt"]
    print(json.dumps({"Study": "JRS1", "Closures": r["CompletedModelRoundTrips"],
                      "AdverseEur": r["ModelClosedAdverseNetEur"],
                      "DifferentiatedDecisions": r["DistinctHistoricalStressDecisions"]}))


if __name__ == "__main__":
    main()

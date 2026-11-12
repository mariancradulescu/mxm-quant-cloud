"""Run DCP1 against the already exposed authenticated tape in custody."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new
SOURCE_RUN = "43176793567"
SOURCE_ARTIFACT = 13925405999
SOURCE_ENVELOPE_SHA = "aceca6ea879201ce16caba708a1ae47a953ad66e6b58977fe044bbd4b740e64a"
SOURCE_TAPE_SHA = "fd7986487be347376aa1e139915f90786155d2b1b6de1787382aa7d8666faeaf"


def main():
    envelope = Path("original-source/ipc2-native-tape.v2.enc").read_bytes()
    if sha256(envelope).hexdigest() != SOURCE_ENVELOPE_SHA:
        raise ValueError("DCP1_ENVELOPE_HASH")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(envelope, key, SOURCE_RUN)
    del key
    if sha256(tape).hexdigest() != SOURCE_TAPE_SHA:
        raise ValueError("DCP1_PLAINTEXT_HASH")
    with tempfile.TemporaryDirectory(prefix="mxm-dcp1-custody-") as folder:
        source, result = Path(folder) / "source.json", Path(folder) / "result.json"
        source.touch(mode=0o600)
        source.write_bytes(tape)
        del tape
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source), str(result), "--native-dcp1"], check=True, timeout=1100)
        report = json.loads(result.read_text())
    if report["SourceSha256"] != SOURCE_TAPE_SHA:
        raise ValueError("DCP1_NATIVE_INPUT_HASH")
    report.update(SourceRunId=int(SOURCE_RUN), SourceArtifactId=SOURCE_ARTIFACT,
                  SourceCiphertextSha256=SOURCE_ENVELOPE_SHA, BrokerRequests=0,
                  ProtocolSha256=sha256(Path("research/DCP1.md").read_bytes()).hexdigest(),
                  Classification="AUTHENTIC_EXPOSED_DEVELOPMENT_ONLY",
                  Costs="ORIGINAL_ACCOUNT_CURRENT_AT_COLLECTION_CONDITIONAL_HISTORICAL")
    Path("dcp1-public.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

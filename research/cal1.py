"""Run CAL1 against the already exposed authenticated tape in custody."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new
from .wfg1 import SOURCE_RUN, SOURCE_ARTIFACT, SOURCE_ENVELOPE_SHA, SOURCE_TAPE_SHA


def main():
    envelope = Path("original-source/fce1-native-tape.v2.enc").read_bytes()
    if sha256(envelope).hexdigest() != SOURCE_ENVELOPE_SHA:
        raise ValueError("CAL1_ENVELOPE_HASH")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(envelope, key, SOURCE_RUN)
    del key
    if sha256(tape).hexdigest() != SOURCE_TAPE_SHA:
        raise ValueError("CAL1_PLAINTEXT_HASH")
    with tempfile.TemporaryDirectory(prefix="mxm-cal1-custody-") as folder:
        source, result = Path(folder) / "source.json", Path(folder) / "result.json"
        source.touch(mode=0o600)
        source.write_bytes(tape)
        del tape
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source), str(result), "--native-cal1"], check=True, timeout=600)
        report = json.loads(result.read_text())
    if report["SourceSha256"] != SOURCE_TAPE_SHA:
        raise ValueError("CAL1_NATIVE_INPUT_HASH")
    report.update(SourceRunId=int(SOURCE_RUN), SourceArtifactId=SOURCE_ARTIFACT,
                  SourceCiphertextSha256=SOURCE_ENVELOPE_SHA, BrokerRequests=0,
                  ProtocolSha256=sha256(Path("research/CAL1.md").read_bytes()).hexdigest(),
                  Classification="AUTHENTIC_EXPOSED_DEVELOPMENT_ONLY",
                  Costs="ORIGINAL_ACCOUNT_CURRENT_AT_COLLECTION_CONDITIONAL_HISTORICAL")
    Path("cal1-public.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

"""Compare continuation filters using the exact encrypted SEM1 input."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new

RUN = "43207629492"


def main():
    original = json.loads(Path("original-receipt/sem1-public.json").read_bytes())
    protocol_hash = sha256(Path("research/SEM1.md").read_bytes()).hexdigest()
    if original["Study"] != "SEM1" or original["ProtocolSha256"] != protocol_hash or not original["OriginalPepperstoneAccountAuthenticated"]:
        raise ValueError("SEM1_DIAGNOSTIC_ORIGINAL_RECEIPT")
    envelope = Path("original-source/sem1-native-tape.v2.enc").read_bytes()
    if sha256(envelope).hexdigest() != original["SourceCiphertextSha256"]:
        raise ValueError("SEM1_DIAGNOSTIC_ENVELOPE")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(envelope, key, RUN)
    del key
    if sha256(tape).hexdigest() != original["SourceSha256"]:
        raise ValueError("SEM1_DIAGNOSTIC_TAPE")
    with tempfile.TemporaryDirectory(prefix="mxm-sem1-custody-") as folder:
        source, result = Path(folder) / "source.json", Path(folder) / "result.json"
        source.touch(mode=0o600)
        source.write_bytes(tape)
        del tape
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source), str(result), "--native-sem1-filter-diagnostic"], check=True, timeout=180)
        report = json.loads(result.read_text())
    if report["SourceSha256"] != original["SourceSha256"]:
        raise ValueError("SEM1_DIAGNOSTIC_NATIVE_TAPE")
    report.update(SourceRunId=int(RUN), BrokerRequests=0, IndependentConfirmation=False,
                  SourceCiphertextSha256=original["SourceCiphertextSha256"],
                  ProtocolSha256=sha256(Path("research/SEM1_FILTER_DIAGNOSTIC.md").read_bytes()).hexdigest())
    Path("sem1-filter-diagnostic-public.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

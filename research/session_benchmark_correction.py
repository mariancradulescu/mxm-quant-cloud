"""Read two hash-locked original tapes inside the existing custody environment."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import tempfile

from .custody import unseal_new

SOURCES = (
    ("SEM1", "43207629492", 13938934824, "sem1", "6c2605e7f23133c5e2a728f9190be87d54ff080de5c1d7bba8300916c24f8354",
     "707f533531d426dd5a6b98544c412a656ee0b02c28765c4915bb46dabdf0cad0",
     "afe44d2c795b8d6b17f3af5d006d24ceaffeb00b3573b61e4d02ea7a48495455"),
    ("ESD1", "43202303802", 13935958165, "esd1", "c76cdb042b6c6801908c5cc0a5a38c42a11b89344fe2ec31906389556bf29b9c",
     "1ff928d0fc7863305a2527d1750d786472924e60555b948d287c550c092b0cff",
     "6e58b37db203fe0b2bffeda3598846e09097e23bf7b631f04e9424399cdd1ee1"),
)


def main():
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    originals = {}
    with tempfile.TemporaryDirectory(prefix="mxm-benchmark-custody-") as folder:
        files = []
        for name, run, artifact, stem, plain_sha, cipher_sha, receipt_sha in SOURCES:
            receipt = Path(f"docs/{name}_AUTHENTIC_PUBLIC_RECEIPT_20261112.json").read_bytes()
            envelope = Path(f"original-{stem}/{stem}-native-tape.v2.enc").read_bytes()
            if sha256(receipt).hexdigest() != receipt_sha or sha256(envelope).hexdigest() != cipher_sha:
                raise ValueError("CORRECTION_ORIGINAL_HASH")
            tape = unseal_new(envelope, key, run)
            if sha256(tape).hexdigest() != plain_sha:
                raise ValueError("CORRECTION_SOURCE_HASH")
            path = Path(folder) / f"{stem}.json"
            path.touch(mode=0o600)
            path.write_bytes(tape)
            del tape
            files.append(str(path))
            originals[name] = dict(RunId=int(run), ArtifactId=artifact, ReceiptSha256=receipt_sha,
                                   SourceCiphertextSha256=cipher_sha, SourceSha256=plain_sha)
        del key
        output = Path(folder) / "result.json"
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll", *files,
                        str(output), "--native-session-benchmark-correction"], check=True, timeout=180)
        report = json.loads(output.read_bytes())
    if any(report[f"{name}SourceSha256"] != value["SourceSha256"] for name, value in originals.items()):
        raise ValueError("CORRECTION_NATIVE_SOURCE_HASH")
    report.update(Originals=originals, BrokerRequests=0, Classification="EXPOSED_RETROSPECTIVE_CORRECTION",
                  ProtocolSha256=sha256(Path("research/SESSION_BENCHMARK_CORRECTION.md").read_bytes()).hexdigest())
    Path("session-benchmark-correction-public.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

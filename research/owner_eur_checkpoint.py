"""Run a chronological section and seal its state with the existing custody key."""
import argparse
import gzip
from io import BytesIO
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from cryptography.hazmat.primitives import serialization

from .custody import seal, unseal


PROTOCOL = "research/eur_contextual_net_1.json"
REPLAY = "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll"
KEY = "R3_CUSTODY_PRIVATE_KEY_PEM"


def run(prepared, checkpoint, previous, phase, report, protocol=None):
    private_key = os.environ[KEY].encode()
    with tempfile.TemporaryDirectory(prefix="checkpoint-", dir=prepared) as temp:
        work = Path(temp)
        env = {k: v for k, v in os.environ.items() if k != KEY}
        if previous is not None:
            restored = work / "previous.json"
            compressed = BytesIO(unseal(previous.read_bytes(), private_key))
            with gzip.GzipFile(fileobj=compressed, mode="rb") as archive, restored.open("xb") as stream:
                shutil.copyfileobj(archive, stream)
            env["MXM_ECONOMIC_CHECKPOINT_FROM"] = str(restored)
        if checkpoint is not None:
            plaintext = work / "next.json"
            env["MXM_ECONOMIC_CHECKPOINT_TO"] = str(plaintext)
            env["MXM_ECONOMIC_STOP_AFTER_PHASE"] = str(phase)
        subprocess.run(["dotnet", REPLAY, "--owner-eur-historical-study", str(protocol or PROTOCOL),
                        str(prepared / "source.json"), str(report), str(prepared / "verified-protection")],
                       env=env, check=True)
        if checkpoint is None:
            return
        public_key = serialization.load_pem_private_key(private_key, password=None).public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        checkpoint.mkdir(parents=True, exist_ok=False)
        compressed_path = work / "next.json.gz"
        with plaintext.open("rb") as state, compressed_path.open("xb") as stream:
            with gzip.GzipFile(filename="", fileobj=stream, mode="wb", compresslevel=3, mtime=0) as archive:
                shutil.copyfileobj(state, archive)
        envelope = seal(compressed_path.read_bytes(), public_key)
        with (checkpoint / "checkpoint.sealed").open("xb") as output:
            output.write(envelope)
        for receipt in sorted(Path(os.environ["MXM_ECONOMIC_RECEIPT_DIRECTORY"]).glob("*.json")):
            shutil.copy2(receipt, checkpoint / receipt.name)


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument("prepared", type=Path)
    cli.add_argument("report", type=Path)
    cli.add_argument("--protocol", type=Path)
    cli.add_argument("--previous", type=Path)
    cli.add_argument("--checkpoint", type=Path)
    cli.add_argument("--phase", type=int)
    args = cli.parse_args()
    if (args.phase is None) != (args.checkpoint is None):
        cli.error("--phase and --checkpoint must be used together")
    run(args.prepared, args.checkpoint, args.previous, args.phase, args.report, args.protocol)


if __name__ == "__main__":
    main()

"""WIR1 source binding, collection, and aggregate receipts."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from .custody import seal_new, unseal_new
from .custody_new import checked_public
from .guard import CaptureContractError
from .native_original_openapi_product_replay import collect_and_evaluate
from .wfg1 import SOURCE_RUN, SOURCE_ARTIFACT, SOURCE_ENVELOPE_SHA, SOURCE_TAPE_SHA


def existing():
    envelope = Path("original-source/fce1-native-tape.v2.enc").read_bytes()
    if sha256(envelope).hexdigest() != SOURCE_ENVELOPE_SHA:
        raise ValueError("WIR1_EXISTING_ENVELOPE")
    key = os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode()
    tape = unseal_new(envelope, key, SOURCE_RUN)
    del key
    if sha256(tape).hexdigest() != SOURCE_TAPE_SHA:
        raise ValueError("WIR1_EXISTING_PLAINTEXT")
    with tempfile.TemporaryDirectory(prefix="mxm-wir1-") as folder:
        source, result = Path(folder) / "source.json", Path(folder) / "result.json"
        source.touch(mode=0o600)
        source.write_bytes(tape)
        del tape
        subprocess.run(["dotnet", "src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll",
                        str(source), str(result), "--native-wir1"], check=True, timeout=600)
        report = json.loads(result.read_text())
    if report["SourceSha256"] != SOURCE_TAPE_SHA:
        raise ValueError("WIR1_NATIVE_INPUT_HASH")
    return report | dict(SourceRunId=int(SOURCE_RUN), SourceArtifactId=SOURCE_ARTIFACT,
                         SourceCiphertextSha256=SOURCE_ENVELOPE_SHA, BrokerRequests=0)


def copper():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    encrypted = Path("wir1-copper-source.v2.enc")

    def preserve(tape):
        encrypted.write_bytes(seal_new(tape, recipient, run))

    def utc(day, hour=0):
        return int(datetime.fromisoformat(day).replace(hour=hour, tzinfo=timezone.utc).timestamp()*1000)

    days = ("2026-02-13", "2026-02-20", "2026-02-27", "2026-03-06", "2026-03-13", "2026-03-20")
    try:
        result = collect_and_evaluate({
            "symbols": ("Copper", "EURUSD"),
            "source_start": utc("2026-02-09"), "start": utc("2026-02-09"),
            "end": utc("2026-03-23"), "event_days": days,
            "bar_ranges": tuple((utc(day, 8), utc(day, 19)) for day in days),
            "quote_hour_start": 15, "quote_hour_end": 19,
            "label": "ORIGINAL_PEPPERSTONE_WIR1_COPPER", "mode": "--native-wir1",
            "contract_preflight": "--native-wir1-contracts", "ordered_tick_history": True,
            "tape_consumer": preserve, "two_sided_targets": ("Copper",),
            "margin_grid_targets": ("Copper",), "quote_interval_ms": 300_000,
            "quote_age_ms": 30_000, "replay_timeout": 600,
        })
    except CaptureContractError as exc:
        reason = str(exc)
        if not re.fullmatch(r"[A-Z0-9_]{3,90}", reason):
            raise
        return dict(Study="WIR1", SourceLane="NEW_COPPER", SourceGate=reason,
                    Status="NO_ECONOMIC_RESULT_SOURCE_GATE")
    return result | dict(SourceCiphertextSha256=sha256(encrypted.read_bytes()).hexdigest())


def main():
    lane = sys.argv[1]
    report = existing() if lane == "existing" else copper()
    report.update(ProtocolSha256=sha256(Path("research/WIR1.md").read_bytes()).hexdigest(),
                  IndependentConfirmation=False, OrdersSubmitted=0, CloudActivated=False)
    Path(f"wir1-{lane}-public.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()

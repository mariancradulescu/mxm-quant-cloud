"""IPC2 protected authentic data collection and aggregate receipt."""
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path

from .custody import seal_new
from .custody_new import checked_public
from .native_original_openapi_product_replay import collect_and_evaluate


def utc(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp()*1000)


def main():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    encrypted = Path("ipc2-native-tape.v2.enc")

    def preserve(tape):
        encrypted.write_bytes(seal_new(tape, recipient, run))

    targets = ("AUDUSD", "NZDUSD", "Copper", "Aluminium")
    report = collect_and_evaluate({
        "symbols": (*targets, "EURUSD"), "source_start": utc("2026-07-03"),
        "start": utc("2026-07-06"), "end": utc("2026-09-28"),
        "quote_sessions": ((8, 10), (14, 16)), "quote_interval_ms": 300_000,
        "quote_age_ms": 30_000, "ordered_tick_history": True,
        "label": "ORIGINAL_PEPPERSTONE_IPC2", "mode": "--native-ipc2",
        "contract_preflight": "--native-ipc2-contracts", "two_sided_targets": targets,
        "margin_grid_targets": targets, "optional_symbols": ("Aluminium",),
        "minimum_first_week_bars": 650, "tape_consumer": preserve, "replay_timeout": 600,
    })
    report["SourceCiphertextSha256"] = sha256(encrypted.read_bytes()).hexdigest()
    report["ProtocolSha256"] = sha256(Path("research/IPC2.md").read_bytes()).hexdigest()
    Path("ipc2-public.json").write_text(json.dumps(report, indent=2)+"\n")


if __name__ == "__main__":
    main()

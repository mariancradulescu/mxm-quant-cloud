"""One original-account read-only acquisition for the preregistered FSD1 panel."""
from hashlib import sha256
import json
import os
from pathlib import Path

from .custody import seal_new
from .custody_new import checked_public
from .ipc2 import utc
from .native_original_openapi_product_replay import collect_and_evaluate


def main():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    encrypted = Path("fsd1-native-tape.v2.enc")

    def preserve(tape):
        encrypted.write_bytes(seal_new(tape, recipient, run))

    targets = ("GBPUSD", "NatGas")
    result = collect_and_evaluate({
        "symbols": (*targets, "EURUSD"), "source_start": utc("2025-08-04"),
        "start": utc("2025-08-11"), "end": utc("2026-11-09"),
        "quote_minutes": (840, 900, 960), "symbol_quote_minutes": {"GBPUSD": (840, 960)},
        "quote_interval_ms": 300_000, "quote_age_ms": 30_000,
        "ordered_tick_history": True, "label": "ORIGINAL_PEPPERSTONE_FSD1",
        "mode": "--native-fsd1", "contract_preflight": "--native-fsd1-contracts",
        "two_sided_targets": targets, "margin_grid_targets": targets,
        "minimum_first_week_bars": 650, "tape_consumer": preserve,
        "replay_timeout": 600, "bar_chunk_hours": 72, "quote_chunk_minutes": 5,
        "report_source_progress": True,
    })
    result["SourceCiphertextSha256"] = sha256(encrypted.read_bytes()).hexdigest()
    result["ProtocolSha256"] = sha256(Path("research/FSD1.md").read_bytes()).hexdigest()
    Path("fsd1-public.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

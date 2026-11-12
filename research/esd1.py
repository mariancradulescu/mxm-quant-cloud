"""One original-account read-only acquisition for the preregistered ESD1 panel."""
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
    encrypted = Path("esd1-native-tape.v2.enc")

    def preserve(tape):
        encrypted.write_bytes(seal_new(tape, recipient, run))

    targets = ("NAS100", "LTCUSD", "BTCEUR", "ETHEUR")
    weekday = (7 * 60, 8 * 60, 13 * 60, 14 * 60)
    weekend = (8 * 60, 8 * 60 + 30, 16 * 60, 16 * 60 + 30)
    result = collect_and_evaluate({
        "symbols": (*targets, "EURUSD"), "source_start": utc("2026-07-17"),
        "start": utc("2026-07-20"), "end": utc("2026-11-09"),
        "quote_minutes": (*weekday, *weekend),
        "symbol_quote_minutes": {
            "NAS100": weekday, "LTCUSD": weekday, "EURUSD": weekday,
            "BTCEUR": weekend, "ETHEUR": weekend,
        },
        "symbol_quote_days": {
            "NAS100": range(5), "LTCUSD": range(5), "EURUSD": range(5), "BTCEUR": (5, 6), "ETHEUR": (5, 6),
        },
        "session_holds": {
            "NAS100": ((420, 780), 60), "LTCUSD": ((420, 780), 60),
            "BTCEUR": ((480, 960), 30), "ETHEUR": ((480, 960), 30),
        },
        "extended_sessions": True, "optional_symbols": targets,
        "quote_interval_ms": 300_000, "quote_age_ms": 30_000,
        "ordered_tick_history": True, "label": "ORIGINAL_PEPPERSTONE_ESD1",
        "mode": "--native-esd1", "contract_preflight": "--native-esd1-contracts",
        "two_sided_targets": targets, "margin_grid_targets": targets,
        "minimum_first_week_bars": 650, "tape_consumer": preserve,
        "replay_timeout": 180, "bar_chunk_hours": 72, "quote_chunk_minutes": 5,
        "report_source_progress": True,
    })
    result["SourceCiphertextSha256"] = sha256(encrypted.read_bytes()).hexdigest()
    result["ProtocolSha256"] = sha256(Path("research/ESD1.md").read_bytes()).hexdigest()
    Path("esd1-public.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

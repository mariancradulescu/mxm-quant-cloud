"""Collect the frozen session map on the original Pepperstone account."""
from datetime import date, timedelta
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
    encrypted = Path("sem1-native-tape.v2.enc")
    start = date(2026, 8, 17)
    weekdays = [(start + timedelta(days=7 * week + week % 5)).isoformat() for week in range(10)]
    weekends = [(start + timedelta(days=7 * week + 5 + week % 2)).isoformat() for week in range(10)]
    targets = ("EURUSD", "NAS100", "XAUUSD", "SpotBrent", "XAGEUR", "ETHEUR")
    minutes = tuple(hour * 60 + offset for hour in range(1, 24, 3) for offset in (0, 30, 90))
    result = collect_and_evaluate({
        "symbols": targets, "source_start": utc("2026-08-14"),
        "start": utc(start.isoformat()), "end": utc("2026-10-26"),
        "event_days": (*weekdays, *weekends),
        "bar_ranges": ((utc("2026-08-14"), utc("2026-10-26")),),
        "symbol_event_days": {name: weekdays for name in targets if name != "ETHEUR"},
        "quote_minutes": minutes, "quote_interval_ms": 1_800_000, "quote_age_ms": 30_000,
        "ordered_tick_history": True, "extended_sessions": True, "session_map": True,
        "optional_symbols": targets[1:], "two_sided_targets": targets, "margin_grid_targets": targets,
        "label": "ORIGINAL_PEPPERSTONE_SEM1", "mode": "--native-sem1",
        "contract_preflight": "--native-sem1-contracts", "replay_timeout": 180,
        "bar_chunk_hours": 72, "quote_chunk_minutes": 5, "report_source_progress": True,
        "tape_consumer": lambda tape: encrypted.write_bytes(seal_new(tape, recipient, run)),
    })
    result["SourceCiphertextSha256"] = sha256(encrypted.read_bytes()).hexdigest()
    result["ProtocolSha256"] = sha256(Path("research/SEM1.md").read_bytes()).hexdigest()
    Path("sem1-public.json").write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()

"""Collect the preregistered market tape and run the native EUR300 portfolio."""
from datetime import datetime
from hashlib import sha256
import json
import os
from pathlib import Path

from .custody import seal_new
from .custody_new import checked_public
from .native_original_openapi_product_replay import collect_and_evaluate


def utc(day):
    return int(datetime.fromisoformat(day + "T00:00:00+00:00").timestamp() * 1000)


def main():
    run = os.environ["GITHUB_RUN_ID"]
    recipient = checked_public(Path("new-recipient-output"), run)
    encrypted = Path("fce1-native-tape.v2.enc")

    def preserve_tape(tape):
        encrypted.write_bytes(seal_new(tape, recipient, run))

    targets = ("AUDUSD", "GBPUSD", "NZDUSD", "SpotBrent", "XAUUSD")
    report = collect_and_evaluate({
        "symbols": (*targets, "EURUSD"),
        "source_start": utc("2026-02-04"),
        "start": utc("2026-02-09"),
        "end": utc("2026-03-23"),
        "quote_hour_start": 15,
        "quote_hour_end": 19,
        "label": "ORIGINAL_PEPPERSTONE_FCE1_FEB_MAR_2026",
        "mode": "--native-fce1",
        "contract_preflight": "--native-fce1-contracts",
        "ordered_tick_history": True,
        "tape_consumer": preserve_tape,
        "two_sided_targets": targets,
        "margin_grid_targets": targets,
        "quote_interval_ms": 60_000,
        "quote_age_ms": 30_000,
        "replay_timeout": 600,
    })
    report["CiphertextSha256"] = sha256(encrypted.read_bytes()).hexdigest()
    report["ProtocolSha256"] = sha256(Path("research/FCE1.md").read_bytes()).hexdigest()
    Path("fce1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "Study": report["Study"],
        "ReadOnlyRequests": report["PostAuthenticationReadOnlyRequests"],
        "FundedRoundTrips": report["Receipt"]["CompletedModelRoundTrips"],
        "ClosedCentralNetEur": report["Receipt"]["ModelClosedCentralNetEur"],
        "ClosedAdverseNetEur": report["Receipt"]["ModelClosedAdverseNetEur"],
    }), flush=True)


if __name__ == "__main__":
    main()

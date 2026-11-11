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
    encrypted = Path("prr1-native-tape.v2.enc")

    def preserve_tape(tape):
        encrypted.write_bytes(seal_new(tape, recipient, run))

    report = collect_and_evaluate({
        "symbols": ("EURUSD", "SpotCrude", "US2000", "US500"),
        "source_start": utc("2026-04-01"),
        "start": utc("2026-04-06"),
        "end": utc("2026-05-04"),
        "quote_hour_start": 14,
        "quote_hour_end": 20,
        "label": "ORIGINAL_PEPPERSTONE_PRR1_APRIL_2026",
        "mode": "--native-prr1",
        "contract_preflight": "--native-prr1-contracts",
        "ordered_tick_history": True,
        "tape_consumer": preserve_tape,
        "two_sided_targets": ("SpotCrude", "US2000"),
    })
    report["CiphertextSha256"] = sha256(encrypted.read_bytes()).hexdigest()
    report["ProtocolSha256"] = sha256(Path("research/PRR1.md").read_bytes()).hexdigest()
    Path("prr1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({
        "Study": report["Study"],
        "ReadOnlyRequests": report["PostAuthenticationReadOnlyRequests"],
        "FundedRoundTrips": report["Receipt"]["CompletedModelRoundTrips"],
        "ClosedCentralNetEur": report["Receipt"]["ModelClosedCentralNetEur"],
        "ClosedAdverseNetEur": report["Receipt"]["ModelClosedAdverseNetEur"],
    }), flush=True)


if __name__ == "__main__":
    main()

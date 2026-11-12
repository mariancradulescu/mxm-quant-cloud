"""ETP1: one bounded original Pepperstone read-only technology pair experiment.

This is not a recovery or rerun of closed PDR1. All dates, symbols,
decision clocks, quote age and economic rules were frozen in research/ETP1.md.
Source sealed in existing run-bound custody before runner exit.
"""
from datetime import datetime, date, timedelta, timezone
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
    encrypted = Path("etp1-native-tape.v2.enc")
    origin = date(2026, 8, 31)
    days = tuple((origin+timedelta(days=i)).isoformat()
                 for i in range(56)
                 if (origin+timedelta(days=i)).weekday()<5)
    assert len(days)==40
    names=("EURUSD", "AAPL.US-24", "GOOG.US-24")
    def preserve(tape):
        encrypted.write_bytes(seal_new(tape, recipient, run))
    report=collect_and_evaluate({
        "symbols":names,
        "source_start":utc("2026-08-28"),
        "start":utc("2026-08-31"),
        "end":utc("2026-10-26"),
        "event_days":days,
        "bar_ranges":((utc("2026-08-28"),utc("2026-10-26")),),
        "quote_hour_start":15,
        "quote_hour_end":19,
        "quote_interval_ms":300_000,
        "quote_age_ms":30_000,
        "quote_chunk_minutes":30,
        "bar_chunk_hours":72,
        "ordered_tick_history":True,
        "extended_sessions":True,
        "session_map":True,
        "two_sided_targets":("AAPL.US-24","GOOG.US-24"),
        "margin_grid_targets":("AAPL.US-24","GOOG.US-24"),
        "label":"ORIGINAL_PEPPERSTONE_ETP1_TECH_2026",
        "mode":"--native-etp1",
        "tape_consumer":preserve,
        "report_source_progress":True,
        "replay_timeout":1200,
    })
    if not encrypted.exists():
        raise RuntimeError("ETP1_ORIGINAL_CUSTODY_MISSING")
    report["SourceCiphertextSha256"]=sha256(encrypted.read_bytes()).hexdigest()
    report["ProtocolSha256"]=sha256(Path("research/ETP1.md").read_bytes()).hexdigest()
    report["NoOrders"]=True
    report["CloudActivated"]=False
    report["IndependentConfirmation"]=False
    Path("etp1-public.json").write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({
        "Study":"ETP1",
        "SourceReadOnlyRequests":report.get("PostAuthenticationReadOnlyRequests"),
        "ClosedModelRoundTrips":report["Joint"]["CompletedModelRoundTrips"],
        "AdverseNetEur":report["Joint"]["ModelClosedAdverseNetEur"]
    }),flush=True)


if __name__=="__main__":
    main()

"""MSE1: one new original Pepperstone multi-class read-only causal experiment.

Frozen independent study distinct from closed US index, oil and JPY rules.
Original raw tape is sealed before attempting any native EUR300 score.
"""
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import os
from pathlib import Path

from .custody import seal_new
from .custody_new import checked_public
from .native_original_openapi_product_replay import collect_and_evaluate


def utc(day):
    return int(datetime.fromisoformat(day + "T00:00:00+00:00").timestamp()*1000)


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    encrypted=Path("mse1-original-native-tape.v2.enc")

    def preserve(raw):
        encrypted.write_bytes(seal_new(raw,recipient,run))

    start=date(2026,8,31)
    days=tuple((start+timedelta(days=i)).isoformat()
               for i in range(56) if (start+timedelta(days=i)).weekday()<5)
    assert len(days)==40
    names=("US2000","SpotCrude","Coffee","US500","EURUSD")
    result=collect_and_evaluate({
        "symbols":names,
        "source_start":utc("2026-08-28"),
        "start":utc("2026-08-31"),
        "end":utc("2026-10-26"),
        "event_days":days,
        "bar_ranges":((utc("2026-08-28"),utc("2026-10-26")),),
        "quote_hour_start":14,
        "quote_hour_end":20,
        "quote_interval_ms":300_000,
        "quote_age_ms":30_000,
        "quote_chunk_minutes":30,
        "bar_chunk_hours":72,
        "extended_sessions":True,
        "session_map":True,
        "ordered_tick_history":True,
        "optional_symbols":("Coffee",),
        "two_sided_targets":("US2000","SpotCrude","Coffee"),
        "margin_grid_targets":("US2000","SpotCrude","Coffee"),
        "label":"ORIGINAL_PEPPERSTONE_MSE1_MULTI_CLASS_2026",
        "mode":"--native-mse1",
        "tape_consumer":preserve,
        "replay_timeout":1200,
        "report_source_progress":True,
    })
    if not encrypted.is_file():
        raise RuntimeError("MSE1_ORIGINAL_CUSTODY_MISSING")
    result["SourceCiphertextSha256"]=sha256(encrypted.read_bytes()).hexdigest()
    result["ProtocolSha256"]=sha256(Path("research/MSE1.md").read_bytes()).hexdigest()
    result["NoOrders"]=True
    result["CloudTradingActivated"]=False
    result["IndependentConfirmation"]=False
    Path("mse1-public.json").write_text(json.dumps(result,indent=2)+"\n")
    receipt=result["Receipt"]
    print(json.dumps({
        "Study":"MSE1",
        "ReadOnlyRequests":result.get("PostAuthenticationReadOnlyRequests"),
        "AcceptedOriginalBarCounts":result.get("OriginalBarsBySymbol"),
        "AuthenticBidAskMarks":result.get("OriginalBidAskAsOfMarks"),
        "ExcludedOptionalSymbols":result.get("ExcludedOptionalSymbols",{}),
        "ClosedFundedRoundTrips":receipt["CompletedModelRoundTrips"],
        "CentralNetEUR":receipt["ModelClosedCentralNetEur"],
        "AdverseNetEUR":receipt["ModelClosedAdverseNetEur"],
        "OrdersSubmitted":0,"CloudActivated":False
    }),flush=True)


if __name__=="__main__":
    main()

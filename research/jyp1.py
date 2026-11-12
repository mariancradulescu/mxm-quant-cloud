"""JYP1: frozen new NZDJPY/AUDJPY causal EUR300 portfolio on Pepperstone.

Existing authenticated EUR account only. Original historical BID/ASK and M5,
ordered paginated tick requests, encrypted source custody, no trading APIs.
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
    return int(datetime.fromisoformat(day + "T00:00:00+00:00").timestamp() * 1000)


def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    ciphertext=Path("jyp1-native-original-tape.v2.enc")

    def preserve(tape):
        ciphertext.write_bytes(seal_new(tape,recipient,run))

    start=date(2026,8,31)
    days=tuple((start+timedelta(days=i)).isoformat() for i in range(56)
               if (start+timedelta(days=i)).weekday()<5)
    assert len(days)==40
    targets=("AUDJPY","NZDJPY")
    context=("USDJPY","EURUSD")
    symbols=(*targets,*context)
    report=collect_and_evaluate({
        "symbols":symbols,
        "source_start":utc("2026-08-28"),
        "start":utc("2026-08-31"),
        "end":utc("2026-10-26"),
        "event_days":days,
        "bar_ranges":((utc("2026-08-28"),utc("2026-10-26")),),
        "quote_hour_start":3,
        "quote_hour_end":8,
        "quote_interval_ms":300000,
        "quote_age_ms":30000,
        "quote_chunk_minutes":30,
        "bar_chunk_hours":72,
        "jpy_route":True,
        "extended_sessions":True,
        "session_map":True,
        "ordered_tick_history":True,
        "two_sided_targets":targets,
        "margin_grid_targets":targets,
        "label":"ORIGINAL_PEPPERSTONE_JYP1_PACIFIC_2026",
        "mode":"--native-jyp1",
        "tape_consumer":preserve,
        "replay_timeout":1200,
        "report_source_progress":True,
    })
    if not ciphertext.is_file():
        raise RuntimeError("JYP1_ORIGINAL_ENCRYPTED_CUSTODY_MISSING")
    report["SourceCiphertextSha256"]=sha256(ciphertext.read_bytes()).hexdigest()
    report["ProtocolSha256"]=sha256(Path("research/JYP1.md").read_bytes()).hexdigest()
    report["BrokerRequestsAfterAuthentication"]=report.get("PostAuthenticationReadOnlyRequests")
    report["OriginalSourceEncrypted"]=True
    report["OrdersSubmitted"]=0
    report["CloudActivated"]=False
    report["IndependentConfirmation"]=False
    Path("jyp1-public.json").write_text(json.dumps(report,indent=2)+"\n")
    receipt=report["Receipt"]
    print(json.dumps({
        "Study":"JYP1",
        "ReadOnlyRequests":report.get("PostAuthenticationReadOnlyRequests"),
        "OriginalBarsBySymbol":report.get("OriginalBarsBySymbol"),
        "OriginalMarks":report.get("OriginalBidAskAsOfMarks"),
        "CompletedModelRoundTrips":receipt["CompletedModelRoundTrips"],
        "CentralNetEur":receipt["ModelClosedCentralNetEur"],
        "AdverseNetEur":receipt["ModelClosedAdverseNetEur"],
        "OrdersSubmitted":0,"IndependentConfirmation":False
    }),flush=True)


if __name__=="__main__":
    main()

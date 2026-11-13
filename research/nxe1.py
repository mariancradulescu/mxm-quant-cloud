"""NXE1 original Pepperstone read-only economic discovery, both permanent directions.

The two causal C# predictors are frozen in NativeNextEconomicResearch.cs BEFORE
this module acquires a single new market mark. Original raw source sealed
before the C# outcomes are read. Historical current tariffs cannot be
backdated as prospective order admission.
"""
from datetime import date,datetime,timedelta
from hashlib import sha256
from pathlib import Path
import json,os
from .custody import seal_new
from .custody_new import checked_public
from .native_original_openapi_product_replay import collect_and_evaluate

def utc(d):
    return int(datetime.fromisoformat(d+"T00:00:00+00:00").timestamp()*1000)

def main():
    run=os.environ["GITHUB_RUN_ID"]
    recipient=checked_public(Path("new-recipient-output"),run)
    cipher=Path("nxe1-original-native-tape.v2.enc")
    def preserve(raw):
        cipher.write_bytes(seal_new(raw,recipient,run))
    begin=date(2026,7,13)
    end=date(2026,11,9)
    days=tuple((begin+timedelta(days=i)).isoformat() for i in
        range((end-begin).days) if (begin+timedelta(days=i)).weekday()<5)
    assert len(days)==85
    result=collect_and_evaluate({
        "symbols":("EURUSD","US500","US30"),
        "source_start":utc("2026-07-10"),
        "start":utc("2026-07-13"),
        "end":utc("2026-11-09"),
        "event_days":days,
        "bar_ranges":((utc("2026-07-10"),utc("2026-11-09")),),
        "quote_hour_start":8,"quote_hour_end":21,
        "quote_interval_ms":300000,
        "quote_age_ms":30000,
        "quote_chunk_minutes":120,
        "bar_chunk_hours":72,
        "extended_sessions":True,
        "session_map":True,
        "ordered_tick_history":True,
        "optional_symbols":("US30",),
        "two_sided_targets":("US30","US500","EURUSD"),
        "margin_grid_targets":("US30","US500","EURUSD"),
        "label":"ORIGINAL_PEPPERSTONE_NXE1_CROSS_ASSET_INDUSTRIAL_2026",
        "mode":"--native-nxe1",
        "tape_consumer":preserve,
        "replay_timeout":1500,
        "report_source_progress":True,
    })
    if not cipher.is_file():raise ValueError("NXE1_ORIGINAL_CUSTODY_NOT_PRESERVED")
    result["SourceCiphertextSha256"]=sha256(cipher.read_bytes()).hexdigest()
    result["ProtocolSha256"]=sha256(Path("research/NXE1.md").read_bytes()).hexdigest()
    result["NoOrders"]=True
    result["CloudTradingActivated"]=False
    result["IndependentConfirmation"]=False
    Path("nxe1-public.json").write_text(json.dumps(result,indent=2)+"\n")
    print("NXE1_ORIGINAL_READONLY_ECONOMICS",json.dumps({
        "OriginalAccountAuthenticated":result["OriginalPepperstoneAccountAuthenticated"],
        "OriginalReadOnlyRequests":result["PostAuthenticationReadOnlyRequests"],
        "ActualInstruments":result["Symbols"],
        "SourceBars":result["OriginalBarsBySymbol"],
        "PairedMarks":result["OriginalBidAskAsOfMarks"],
        "CausalPrequentialPredictions":result["CausalPrequentialForecasts"],
        "HypotheticalSignals":result["CrossFamilyHypotheticalSignals"],
        "AdmittedFundedModelTrades":result["AdmittedModelTrades"],
        "OrdersSubmitted":0
    }),flush=True)

if __name__=="__main__":
    main()

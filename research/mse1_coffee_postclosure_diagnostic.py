"""Read-only postclosure reconciliation of the MSE1 public financial receipt.

Usage: python -m research.mse1_coffee_postclosure_diagnostic /path/to/mse1-public.json
OR:  python -m research.mse1_coffee_postclosure_diagnostic /path/to/original_artifact.zip
No cTrader calls, ciphertext decryption, strategy rerun or synthetic prices.
"""
import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def examine(artifact):
    if str(artifact).endswith(".zip"):
        with zipfile.ZipFile(artifact) as z:
            original=z.read("mse1-public.json")
    else:
        from pathlib import Path
        original=Path(artifact).read_bytes()
    data=json.loads(original)
    assert data["Study"]=="MSE1"
    assert data["SourceSha256"]=="068cf7a396d0cddfc59b856f95f930b7bff83eddef4c8beae556243e168c4f7e"
    assert hashlib.sha256(original).hexdigest()=="53db93ff14866b703ea77051e9859033df39e17401991d485e2323f13feb3535"
    assert data["Receipt"]["CompletedModelRoundTrips"]==9
    schedule=data["CurrentScheduleBySymbol"]["Coffee"]
    zone=ZoneInfo(schedule["TimeZone"])
    observed=[x for x in data["Receipt"]["SampledEquity"]
        if x["UsedMarginEur"] is not None and x["UsedMarginEur"]>100]
    assert len(observed)==21
    entry=observed[0]["At"]
    close=entry+1350*60000
    assert datetime.fromtimestamp(entry/1000,timezone.utc).isoformat()=="2026-09-02T15:35:01.500000+00:00"
    assert datetime.fromtimestamp(close/1000,timezone.utc).isoformat()=="2026-09-03T14:05:01.500000+00:00"
    assert observed[-1]["At"]==close-300000
    marks={x["At"] for x in observed}|{close}
    counts={"observed":0,"closed_schedule":0,"open_unrequested":0,"open_requested_unobserved":0}
    unresolved=[]
    for at in range(entry,close+1,300000):
        utc=datetime.fromtimestamp(at/1000,timezone.utc)
        local=utc.astimezone(zone)
        second=((local.weekday()+1)%7)*86400+local.hour*3600+local.minute*60+local.second
        open_now=any(a<=second<b for a,b in schedule["Intervals"])
        requested=14<=utc.hour<20
        if at in marks:
            assert open_now
            counts["observed"]+=1
        elif not open_now: counts["closed_schedule"]+=1
        elif not requested: counts["open_unrequested"]+=1
        else:
            counts["open_requested_unobserved"]+=1
            unresolved.append(utc.isoformat())
    assert counts=={"observed":22,"closed_schedule":177,
        "open_unrequested":69,"open_requested_unobserved":3}
    assert data["JointRequiredHeldQuoteClocks"]==371
    assert sum(counts.values())==271
    assert 371-271==100
    assert data["JointMissingHeldQuoteClocks"]==249
    return {
        "kind":"POSTCLOSURE_PUBLIC_RECEIPT_RECONSTRUCTION_NOT_EXECUTION",
        "original_source_sha256_reported":data["SourceSha256"],
        "original_public_receipt_sha256":hashlib.sha256(original).hexdigest(),
        "coffee_entry_inferred_utc":datetime.fromtimestamp(entry/1000,timezone.utc).isoformat(),
        "protective_deadline_inferred_utc":datetime.fromtimestamp((entry+120*60000)/1000,timezone.utc).isoformat(),
        "coffee_model_close_inferred_utc":datetime.fromtimestamp(close/1000,timezone.utc).isoformat(),
        "missing_quote_classification":counts,
        "unresolved_inside_collection_window":unresolved,
        "current_schedule_does_not_certify_historical_holidays":True,
        "broker_stop_fills_certified":False,
        "replay_original_modified":False
    }

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("Provide original MSE1 public artifact ZIP path")
    print(json.dumps(examine(sys.argv[1]),indent=2,sort_keys=True))

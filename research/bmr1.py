"""Collect only the locked official BLS release-day windows for BMR1."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .native_original_openapi_product_replay import collect_and_evaluate

CPI = ("2026-05-12", "2026-06-10", "2026-07-14", "2026-08-12", "2026-09-11", "2026-10-14")
EMPLOYMENT = ("2026-05-08", "2026-06-05", "2026-07-02", "2026-08-07", "2026-09-04", "2026-10-02")


def utc(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)


def main():
    days = sorted(CPI + EMPLOYMENT)
    windows = [(utc(day + "T02:00:00"), utc(day + "T15:05:00")) for day in days]
    report = collect_and_evaluate(dict(
        symbols=("EURUSD", "GBPUSD", "XAUUSD"),
        source_start=windows[0][0],
        start=utc(days[0]),
        end=utc("2026-10-15"),
        quote_hour_start=12,
        quote_hour_end=15,
        event_days=days,
        bar_ranges=windows,
        label="ORIGINAL_PEPPERSTONE_BMR1_BLS_MAY_OCT",
        mode="--native-bmr1",
        contract_preflight="--native-bmr1-contracts",
    ))
    report["ReleaseCalendar"] = {"CPI": CPI, "EmploymentSituation": EMPLOYMENT, "ReleaseUtc": "12:30"}
    report["ProtocolSha256"] = sha256(Path("research/BMR1.md").read_bytes()).hexdigest()
    Path("bmr1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "Receipt"}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in report["Receipt"].items() if k != "SampledEquity"},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()

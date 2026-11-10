"""Run the registered RRP1 profile through the existing original native adapter."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .native_original_openapi_product_replay import collect_and_evaluate


def utc(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)


def main():
    report = collect_and_evaluate(dict(
        symbols=("EURUSD", "NAS100", "US500", "XAUUSD"),
        source_start=utc("2026-09-18T08:00:00"),
        start=utc("2026-09-21"),
        end=utc("2026-11-02"),
        label="ORIGINAL_PEPPERSTONE_RRP1_W39_W44",
        mode="--native-rrp1",
    ))
    report["ProtocolSha256"] = sha256(Path("research/RRP1.md").read_bytes()).hexdigest()
    Path("rrp1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "Receipt"}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in report["Receipt"].items() if k != "SampledEquity"},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()

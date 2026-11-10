"""Run the registered LDP1 profile through the existing original native adapter."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .native_original_openapi_product_replay import collect_and_evaluate


def utc(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)


def main():
    report = collect_and_evaluate(dict(
        symbols=("AUDUSD", "EURUSD", "NZDUSD", "XAGUSD"),
        source_start=utc("2026-06-19T08:00:00"),
        start=utc("2026-06-22"),
        end=utc("2026-07-27"),
        quote_hour_start=7,
        quote_hour_end=13,
        label="ORIGINAL_PEPPERSTONE_LDP1_W26_W30",
        mode="--native-ldp1",
        contract_preflight="--native-ldp1-contracts",
    ))
    report["ProtocolSha256"] = sha256(Path("research/LDP1.md").read_bytes()).hexdigest()
    Path("ldp1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "Receipt"}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in report["Receipt"].items() if k != "SampledEquity"},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()

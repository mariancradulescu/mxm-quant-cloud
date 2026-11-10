"""Run the registered MCT2 profile through the existing original native adapter."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .native_original_openapi_product_replay import collect_and_evaluate


def utc(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)


def main():
    report = collect_and_evaluate(dict(
        symbols=("ETHUSD", "EURUSD", "NAS100", "XAUUSD"),
        source_start=utc("2026-08-28T08:00:00"),
        start=utc("2026-08-31"),
        end=utc("2026-10-05"),
        quote_hour_start=13,
        quote_hour_end=19,
        label="ORIGINAL_PEPPERSTONE_MCT2_W36_W40",
        mode="--native-mct2",
        contract_preflight="--native-mct2-contracts",
    ))
    report["ExecutionRecovery"] = "CANCEL_UNFINANCED_OPEN_ON_MARK_RECHECK"
    report["ProtocolSha256"] = sha256(Path("research/MCT2.md").read_bytes()).hexdigest()
    Path("mct2-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "Receipt"}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in report["Receipt"].items() if k != "SampledEquity"},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()

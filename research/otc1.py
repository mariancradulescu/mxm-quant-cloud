"""Run the registered OTC1 profile through the existing original native adapter."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .native_original_openapi_product_replay import collect_and_evaluate


def utc(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)


def main():
    report = collect_and_evaluate(dict(
        symbols=("EURUSD", "GBPUSD", "SpotBrent", "SpotCrude"),
        source_start=utc("2026-05-22T08:00:00"),
        start=utc("2026-05-25"),
        end=utc("2026-06-29"),
        quote_hour_start=13,
        quote_hour_end=19,
        label="ORIGINAL_PEPPERSTONE_OTC1_W22_W26",
        mode="--native-otc1",
        contract_preflight="--native-otc1-contracts",
    ))
    report["ExecutionRecovery"] = "CANCEL_UNFINANCED_OPEN_ON_MARK_RECHECK"
    report["ProtocolSha256"] = sha256(Path("research/OTC1.md").read_bytes()).hexdigest()
    Path("otc1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "Receipt"}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in report["Receipt"].items() if k != "SampledEquity"},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()

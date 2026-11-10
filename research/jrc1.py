"""Run the registered JRC1 profile through the existing original native adapter."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from .native_original_openapi_product_replay import collect_and_evaluate


def utc(value):
    return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp() * 1000)


def main():
    report = collect_and_evaluate(dict(
        symbols=("AUDJPY", "EURJPY", "EURUSD", "USDJPY"),
        source_start=utc("2026-07-31T08:00:00"),
        start=utc("2026-08-03"),
        end=utc("2026-09-07"),
        quote_hour_start=7,
        quote_hour_end=13,
        label="ORIGINAL_PEPPERSTONE_JRC1_W31_W35",
        jpy_route=True,
        mode="--native-jrc1",
        contract_preflight="--native-jrc1-contracts",
    ))
    report["ExecutionRecovery"] = "CANCEL_UNFINANCED_OPEN_ON_MARK_RECHECK"
    report["ProtocolSha256"] = sha256(Path("research/JRC1.md").read_bytes()).hexdigest()
    Path("jrc1-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "Receipt"}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in report["Receipt"].items() if k != "SampledEquity"},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()

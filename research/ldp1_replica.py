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
        source_start=utc("2026-09-18T08:00:00"),
        start=utc("2026-09-21"),
        end=utc("2026-10-26"),
        quote_hour_start=7,
        quote_hour_end=13,
        label="ORIGINAL_PEPPERSTONE_LDP1_REPLICA_W39_W43",
        mode="--native-ldp1-replica-w39w43",
        contract_preflight="--native-ldp1-contracts",
    ))
    report["FrozenOriginalRun"] = 42797204156
    report["FrozenOriginalCoreCommit"] = "230e29f49ad26e5d0e12a1f7bcf97dcb70debeff"
    report["ExecutionRecovery"] = "CANCEL_UNFINANCED_OPEN_ON_MARK_RECHECK"
    report["ProtocolSha256"] = sha256(Path("research/LDP1_REPLICA_W39_W43.md").read_bytes()).hexdigest()
    Path("ldp1-replica-public.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: v for k, v in report.items() if k != "Receipt"}, separators=(",", ":")))
    print(json.dumps({k: v for k, v in report["Receipt"].items() if k != "SampledEquity"},
                     separators=(",", ":")))


if __name__ == "__main__":
    main()

"""XMH2 NEW original 274-day M15 Pepperstone historical source-only collection.

Reuse original HXC1 trusted authenticated official OpenAPI collector implementation,
but with a new prospectively frozen XMH2 protocol and run-bound source artifact.
NO HXC1 original workflow rerun, model fitting or market outcome assessment.
"""
from pathlib import Path
from . import hxc1_historical_source as existing

PROTOCOL=Path("research/xmh2_complete_earlier_m15_source_protocol.json")
SOURCE_CLASS="MXM_XMH2_COMPLETE_EARLIER_274DAY_PEPPERSTONE_M15_SOURCE_V1"


def execute() -> None:
    # Process-local configuration, original HXC1 files byte-identical.
    existing.PROTOCOL=PROTOCOL
    existing.OUTPUT=Path("xmh2-sealed-output")
    existing.SCHEMA=SOURCE_CLASS
    existing.collect()
    print("XMH2_274DAY_NEW_PEPPERSTONE_M15_SOURCE_SEALED_NO_TRADING",flush=True)


if __name__=="__main__":
    try:
        execute()
    except Exception:
        print("XMH2_SOURCE_GUARDED_FAILURE_DETAILS_WITHHELD",flush=True)
        raise SystemExit(1)

"""XMH2 NEW original broker M15 274-day collection, source-only.
Reusable identical authenticated cTrader and recipient code as HXC1/XMH1,
but NEW frozen plan, NEW run id and NEW sealed source; no closed workflow rerun.
"""
from pathlib import Path
from . import xmh1_m15_source as reuse

PROTOCOL = Path("research/xmh2_complete_earlier_m15_source_protocol.json")
SOURCE_CLASS = "MXM_XMH2_COMPLETE_EARLIER_274DAY_PEPPERSTONE_M15_SOURCE_V1"


def execute() -> None:
    reuse.PROTOCOL = PROTOCOL
    reuse.SOURCE_CLASS = SOURCE_CLASS
    # XMH1 only injects source configuration into the shared authenticated
    # read-only collector, never imports predictive mechanisms.
    reuse.execute()
    print("XMH2_NEW_FULL_PREAUGUST_M15_ORIGINAL_BROKER_SOURCE_SEALED",
          flush=True)


if __name__ == "__main__":
    try:
        execute()
    except Exception:
        print("XMH2_AUTHENTIC_SOURCE_FAILURE_DETAILS_WITHHELD", flush=True)
        raise SystemExit(1)

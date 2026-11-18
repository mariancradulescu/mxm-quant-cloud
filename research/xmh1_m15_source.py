"""XMH1 new source-only original broker M15 availability test.

Reuse the existing independently proven HXC1 *collector implementation* with a
different, prospectively frozen XMH1 protocol, new workflow run, new encrypted
source run binding and new source artifact. Never rerun the HXC1 experiment,
never change HXC1 files, and never fit any prediction here.
"""
from pathlib import Path
from . import hxc1_historical_source as existing

PROTOCOL = Path("research/xmh1_m15_probe_source_protocol.json")
SOURCE_CLASS = "MXM_XMH1_EARLIER_M15_BROKER_READONLY_SOURCE_V1"


def execute() -> None:
    # Configuration injection is limited to this dedicated isolated Python job;
    # the original HXC1 script, original run, source artifacts and protocol
    # remain byte-for-byte unchanged.
    existing.PROTOCOL = PROTOCOL
    existing.OUTPUT = Path("xmh1-sealed-output")
    existing.SCHEMA = SOURCE_CLASS
    existing.collect()
    print("XMH1_NEW_PROSPECTIVE_EARLIER_M15_SOURCE_ONLY_CUSTODIED", flush=True)


if __name__ == "__main__":
    try:
        execute()
    except Exception:
        print("XMH1_SOURCE_FAILED_CLOSED_NO_PRIVATE_ERROR", flush=True)
        raise SystemExit(1)

"""Protected CPE1 recovery using the original source and result bridge."""
import json
import os
import subprocess
import time
from pathlib import Path

from .cpe1_one_integrated_original_execute import execute, need

OWNER_AUTHORIZATION = Path("ops/cpe1-recovery-1-owner-authorization.json")
OUTPUT = Path("cpe1-recovery-public")
REPLAY = Path("src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll")
RECOVERY = "CPE1_TECHNICAL_RECOVERY_1"


def run_native(private_input, native, protocol_sha):
    environment = os.environ.copy()
    environment.pop("R3_CUSTODY_PRIVATE_KEY_PEM", None)
    # Execute the assembly directly so the timeout also stops the native
    # process. Inherit stdout for real-time, flushed EPM1 records.
    subprocess.run(["dotnet", str(REPLAY), str(private_input), str(native),
                    "--cpe1-recovery-native-funded-economics", protocol_sha],
                   env=environment, stderr=subprocess.DEVNULL,
                   check=True, timeout=8400)


def main():
    started = time.monotonic()

    def report(stage):
        print("EPM1 " + json.dumps(dict(stage=stage,
                                       elapsedSeconds=int(time.monotonic()-started))), flush=True)

    try:
        need(os.environ.get("GITHUB_REF") == "refs/heads/main" and
             os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and
             os.environ.get("GITHUB_ACTOR") == "mariancradulescu" and
             os.environ.get("GITHUB_EVENT_NAME") == "push", "RECOVERY_WORKFLOW_IDENTITY")
        authorization = json.loads(OWNER_AUTHORIZATION.read_text(encoding="utf-8"))
        need(authorization["RecoveryIdentity"] == RECOVERY, "DISTINCT_RECOVERY_AUTHORIZATION")
        recovery = dict(authorization, RecoveryRunId=int(os.environ["GITHUB_RUN_ID"]),
                        RecoveryHead=os.environ["GITHUB_SHA"])
        execute(OUTPUT, run_native, report_stage=report, recovery=recovery)
    except Exception as exc:
        report("RECOVERY_FAILED_NO_ECONOMIC_VERDICT_" + type(exc).__name__)
        return 1
    report("RECOVERY_RECEIPTS_WRITTEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

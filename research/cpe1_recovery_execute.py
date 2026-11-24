"""Protected CPE1 recovery using the original source and result bridge."""
import json
import os
import subprocess
import tempfile
import threading
import time
from pathlib import Path

OWNER_AUTHORIZATION = Path("ops/cpe1-recovery-1-owner-authorization.json")
OUTPUT = Path("cpe1-recovery-public")
REPLAY = Path("src/Mxm.Replay/bin/Release/net8.0/Mxm.Replay.dll")
RECOVERY = "CPE1_TECHNICAL_RECOVERY_1"
NATIVE_TIMEOUT_SECONDS = 8400
NATIVE_STAGES = {
    "READ_NATIVE_INPUT", "ADVANCE_SOURCE_CLOCKS", "RECONCILE_BOOK_EVENTS",
    "SCORE_AND_REPORT_BOOK", "WRITE_NATIVE_RECEIPT",
}
NATIVE_ERRORS = {
    "REPLAY_INVALID_INPUT_JSON", "REPLAY_FILE_MISSING", "REPLAY_FILE_ACCESS_DENIED",
    "REPLAY_IO_FAILED", "REPLAY_NUMERIC_OVERFLOW", "REPLAY_PROTOCOL_HASH_INVALID",
    "REPLAY_INPUT_CONTRACT_FAILED", "REPLAY_EVENT_CHAIN_RECONCILIATION_FAILED",
    "REPLAY_STATE_VALIDATION_FAILED", "REPLAY_UNEXPECTED_ERROR",
}


class ReplayFailure(Exception):
    def __init__(self, stage, code, exit_code):
        super().__init__(code)
        self.stage = stage
        self.code = code
        self.exit_code = exit_code


def parse_event(line, prefix, fields):
    if not line.startswith(prefix) or len(line) > 1024:
        return None
    try:
        event = json.loads(line[len(prefix):])
    except (ValueError, RecursionError):
        return None
    if (not isinstance(event, dict) or event.keys() != fields or
            not isinstance(event["stage"], str) or event["stage"] not in NATIVE_STAGES):
        return None
    return event


def relay_progress(stdout, completed_events):
    for line in stdout:
        event = parse_event(line, b"EPM1 ", {"stage", "completed", "total", "book", "elapsedSeconds"})
        if event is None:
            continue
        completed, total, book, elapsed = (event[k] for k in ("completed", "total", "book", "elapsedSeconds"))
        if (type(completed) is not int or completed < 0 or
                total is not None and (type(total) is not int or total < completed) or
                book is not None and (type(book) is not int or not 1 <= book <= 9) or
                type(elapsed) is not int or elapsed < 0):
            continue
        completed_events.append(event["stage"])
        print("EPM1 " + json.dumps(event), flush=True)


def safe_native_error(stderr, stage, exit_code):
    stderr.seek(max(0, stderr.seek(0, os.SEEK_END) - 8192))
    lines = stderr.read(8192).splitlines()
    for line in reversed(lines):
        event = parse_event(line, b"EPM1_REPLAY_ERROR ", {"stage", "code"})
        if event is not None and isinstance(event["code"], str) and event["code"] in NATIVE_ERRORS:
            return ReplayFailure(event["stage"], event["code"], exit_code)
    if stage == "START_NATIVE_REPLAY":
        return ReplayFailure(stage, "REPLAY_HOST_EXIT_BEFORE_PROGRESS", exit_code)
    return ReplayFailure(stage, "REPLAY_EXIT_WITHOUT_STRUCTURED_ERROR", exit_code)


def run_replay_process(command, environment, timeout):
    # Keep raw diagnostics in a private temporary file. Emit only allowlisted
    # fields, and relay native progress while the child is still running.
    stages = ["START_NATIVE_REPLAY"]
    with tempfile.TemporaryFile() as stderr:
        try:
            child = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE, stderr=stderr)
        except OSError:
            raise ReplayFailure(stages[-1], "REPLAY_PROCESS_START_FAILED", None) from None
        with child:
            reader = threading.Thread(target=relay_progress, args=(child.stdout, stages))
            reader.start()
            timed_out = False
            try:
                child.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
                reader.join()
            if timed_out:
                raise ReplayFailure(stages[-1], "REPLAY_TIMEOUT", child.returncode)
            if child.returncode != 0:
                raise safe_native_error(stderr, stages[-1], child.returncode)


def run_native(private_input, native, protocol_sha):
    environment = os.environ.copy()
    environment.pop("R3_CUSTODY_PRIVATE_KEY_PEM", None)
    run_replay_process(["dotnet", str(REPLAY), str(private_input), str(native),
                        "--cpe1-recovery-native-funded-economics", protocol_sha],
                       environment, NATIVE_TIMEOUT_SECONDS)


def main():
    started = time.monotonic()
    active_stage = "VERIFY_RECOVERY_WORKFLOW_IDENTITY"

    def report(stage, **details):
        nonlocal active_stage
        active_stage = stage
        print("EPM1 " + json.dumps(dict(stage=stage, elapsedSeconds=int(time.monotonic()-started),
                                       **details)), flush=True)

    try:
        from .cpe1_one_integrated_original_execute import execute, need
        need(os.environ.get("GITHUB_REF") == "refs/heads/main" and
             os.environ.get("GITHUB_RUN_ATTEMPT") == "1" and
             os.environ.get("GITHUB_ACTOR") == "mariancradulescu" and
             os.environ.get("GITHUB_ACTOR_ID") == "322088485" and
             os.environ.get("GITHUB_EVENT_NAME") == "push", "RECOVERY_WORKFLOW_IDENTITY")
        authorization = json.loads(OWNER_AUTHORIZATION.read_text(encoding="utf-8"))
        need(authorization["RecoveryIdentity"] == RECOVERY, "DISTINCT_RECOVERY_AUTHORIZATION")
        recovery = dict(authorization, RecoveryRunId=int(os.environ["GITHUB_RUN_ID"]),
                        RecoveryHead=os.environ["GITHUB_SHA"])
        execute(OUTPUT, run_native, report_stage=report, recovery=recovery)
    except ReplayFailure as exc:
        report("RECOVERY_FAILED_NO_ECONOMIC_VERDICT", failedStage=exc.stage,
               errorCode=exc.code, exitCode=exc.exit_code)
        return 1
    except Exception as exc:
        report("RECOVERY_FAILED_NO_ECONOMIC_VERDICT", failedStage=active_stage,
               errorCode=type(exc).__name__, exitCode=None)
        return 1
    report("RECOVERY_RECEIPTS_WRITTEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Offline checks for the final CPE1 diagnostic and authorization controls."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from .cpe1_recovery_authority import (
    OWNER_ACCOUNT_ID,
    OWNER_REVIEW_ENVIRONMENT,
    verify_independent_audit,
    verify_owner_review,
)
from .cpe1_recovery_execute import ReplayFailure, run_native, run_replay_process

ISSUE = "https://api.github.com/repos/mariancradulescu/mxm-quant-cloud/issues/393"
HEAD = "a" * 40
CI = "45358870951"
AUDITOR_ACCOUNT_ID = 1234
PRIVATE = "TECHNICAL_FIXTURE_PRIVATE_TAPE_AND_CUSTODY_SENTINEL"


class AuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.comment = dict(
            user=dict(id=AUDITOR_ACCOUNT_ID, type="User"),
            issue_url=ISSUE,
            created_at="2026-11-24T09:00:00Z",
            updated_at="2026-11-24T09:00:00Z",
            body=f"Verified.\nCPE1_TECHNICAL_RECOVERY_1_INDEPENDENT_APPROVAL {HEAD} {CI}\n",
        )

    def test_distinct_registered_auditor_and_scoped_comment_pass(self):
        verify_independent_audit(self.comment, str(AUDITOR_ACCOUNT_ID), ISSUE, HEAD, CI)

    def test_correct_text_without_authenticated_registered_author_is_rejected(self):
        for auditor, user in (
            ("", self.comment["user"]),
            (str(OWNER_ACCOUNT_ID), dict(id=OWNER_ACCOUNT_ID, type="User")),
            (str(AUDITOR_ACCOUNT_ID), dict(id=OWNER_ACCOUNT_ID, type="User")),
            (str(AUDITOR_ACCOUNT_ID), dict(id=AUDITOR_ACCOUNT_ID, type="Bot")),
        ):
            with self.subTest(auditor=auditor, user=user), self.assertRaises(ValueError):
                verify_independent_audit(dict(self.comment, user=user), auditor, ISSUE, HEAD, CI)

    def test_edited_comment_or_approval_for_a_different_revision_is_rejected(self):
        for comment, issue, head, ci in (
            (dict(self.comment, updated_at="2026-11-24T09:01:00Z"), ISSUE, HEAD, CI),
            (self.comment, ISSUE + "0", HEAD, CI),
            (self.comment, ISSUE, "b" * 40, CI),
            (self.comment, ISSUE, HEAD, "45358870952"),
        ):
            with self.subTest(issue=issue, head=head, ci=ci), self.assertRaises(ValueError):
                verify_independent_audit(comment, str(AUDITOR_ACCOUNT_ID), issue, head, ci)

    def test_only_owner_review_of_the_dedicated_environment_is_accepted(self):
        review = dict(state="approved", user=dict(id=OWNER_ACCOUNT_ID, type="User"),
                      environments=[dict(name=OWNER_REVIEW_ENVIRONMENT)])
        verify_owner_review([review])
        for reviews in (
            [],
            [dict(review, state="rejected")],
            [dict(review, user=dict(id=AUDITOR_ACCOUNT_ID, type="User"))],
            [dict(review, user=dict(id=OWNER_ACCOUNT_ID, type="Bot"))],
            [dict(review, environments=[dict(name="mxm-r3-custody-v1")])],
        ):
            with self.subTest(reviews=reviews), self.assertRaises(ValueError):
                verify_owner_review(reviews)


class ReplayDiagnosticsTests(unittest.TestCase):
    def test_structured_error_preserves_exit_code_and_filters_raw_streams(self):
        invalid_progress = json.dumps(dict(stage="READ_NATIVE_INPUT", detail=PRIVATE))
        fixture = f"""
import sys
print({PRIVATE!r}, flush=True)
print('EPM1 {{"stage":"ADVANCE_SOURCE_CLOCKS","completed":4,"total":9,"book":null,"elapsedSeconds":1}}', flush=True)
print('EPM1 ' + {invalid_progress!r}, flush=True)
print({PRIVATE!r}, file=sys.stderr, flush=True)
print('EPM1_REPLAY_ERROR {{"stage":"RECONCILE_BOOK_EVENTS","code":"REPLAY_EVENT_CHAIN_RECONCILIATION_FAILED"}}',
      file=sys.stderr, flush=True)
sys.exit(23)
"""
        with contextlib.redirect_stdout(io.StringIO()) as logs, self.assertRaises(ReplayFailure) as raised:
            run_replay_process([sys.executable, "-c", fixture], os.environ, 5)
        self.assertEqual(raised.exception.stage, "RECONCILE_BOOK_EVENTS")
        self.assertEqual(raised.exception.code, "REPLAY_EVENT_CHAIN_RECONCILIATION_FAILED")
        self.assertEqual(raised.exception.exit_code, 23)
        self.assertIn('"completed": 4', logs.getvalue())
        self.assertNotIn(PRIVATE, logs.getvalue() + str(raised.exception))

    def test_unstructured_child_error_never_reveals_raw_diagnostic(self):
        fixture = f"import sys; print({PRIVATE!r}, file=sys.stderr); sys.exit(9)"
        with self.assertRaises(ReplayFailure) as raised:
            run_replay_process([sys.executable, "-c", fixture], os.environ, 5)
        self.assertEqual(raised.exception.code, "REPLAY_HOST_EXIT_BEFORE_PROGRESS")
        self.assertEqual(raised.exception.exit_code, 9)
        self.assertNotIn(PRIVATE, str(raised.exception))

    def test_progress_is_forwarded_before_child_exits(self):
        with tempfile.TemporaryDirectory() as tmp:
            witness = Path(tmp, "progress-forwarded")

            class ProgressLog(io.StringIO):
                def write(self, value):
                    if value.startswith("EPM1 "):
                        witness.touch()
                    return super().write(value)

            fixture = """
import pathlib, sys, time
print('EPM1 {"stage":"ADVANCE_SOURCE_CLOCKS","completed":1,"total":2,"book":null,"elapsedSeconds":0}', flush=True)
witness = pathlib.Path(sys.argv[1])
while not witness.exists():
    time.sleep(0.01)
"""
            with contextlib.redirect_stdout(ProgressLog()):
                run_replay_process([sys.executable, "-c", fixture, str(witness)], os.environ, 5)
            self.assertTrue(witness.exists())

    def test_timeout_preserves_the_last_live_stage_and_terminates_the_child(self):
        fixture = """
import time
print('EPM1 {"stage":"ADVANCE_SOURCE_CLOCKS","completed":1,"total":2,"book":null,"elapsedSeconds":0}', flush=True)
time.sleep(30)
"""
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ReplayFailure) as raised:
            run_replay_process([sys.executable, "-c", fixture], os.environ, 2)
        self.assertEqual(raised.exception.code, "REPLAY_TIMEOUT")
        self.assertEqual(raised.exception.stage, "ADVANCE_SOURCE_CLOCKS")
        self.assertLess(raised.exception.exit_code, 0)

    def test_native_replay_reports_safe_invalid_json_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, output = Path(tmp, PRIVATE), Path(tmp, "result.json")
            source.write_text(PRIVATE, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()) as logs, self.assertRaises(ReplayFailure) as raised:
                run_native(source, output, "a" * 64)
            self.assertEqual(raised.exception.stage, "READ_NATIVE_INPUT")
            self.assertEqual(raised.exception.code, "REPLAY_INVALID_INPUT_JSON")
            self.assertEqual(raised.exception.exit_code, 1)
            self.assertFalse(output.exists())
            self.assertNotIn(PRIVATE, logs.getvalue() + str(raised.exception))

    def test_custody_secret_is_removed_before_native_launch(self):
        with patch.dict(os.environ, {"R3_CUSTODY_PRIVATE_KEY_PEM": PRIVATE}):
            with patch("research.cpe1_recovery_execute.run_replay_process") as start:
                run_native("private.json", "result.json", "a" * 64)
        command, child_env, timeout = start.call_args.args
        self.assertNotIn("R3_CUSTODY_PRIVATE_KEY_PEM", child_env)
        self.assertEqual(command[-2], "--cpe1-recovery-native-funded-economics")
        self.assertEqual(timeout, 8400)

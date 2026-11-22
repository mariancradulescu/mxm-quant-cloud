"""No-credentials tests for distinct NAS100-only owner gate and interval plan."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import funded_nas100_gap_collection as b
from .guard import CaptureContractError
from .test_funded_history_economic_development import AuthenticatedEconomicDevelopmentTests


class Nas100PreparedWorkflowTests(unittest.TestCase):
    def test_not_authorized_without_separate_marker_and_first_attempt(self):
        with patch.dict(b.os.environ, {"GITHUB_EVENT_NAME": "pull_request",
                 "GITHUB_REF": "refs/heads/main", "GITHUB_ACTOR": "mariancradulescu",
                 "GITHUB_RUN_ATTEMPT": "1"}), patch.object(
                     Path, "read_bytes", return_value=(b.MARKER + "\n").encode()):
            with self.assertRaisesRegex(CaptureContractError, "NAS100_GAP_OWNER_MARKER_NOT_AUTHORIZED"):
                b.protected_owner_gate()
        with patch.dict(b.os.environ, {"GITHUB_EVENT_NAME": "push",
                 "GITHUB_REF": "refs/heads/main", "GITHUB_ACTOR": "mariancradulescu",
                 "GITHUB_RUN_ATTEMPT": "2"}), patch.object(
                     Path, "read_bytes", return_value=(b.MARKER + "\n").encode()):
            with self.assertRaisesRegex(CaptureContractError, "NAS100_GAP_OWNER_MARKER_NOT_AUTHORIZED"):
                b.protected_owner_gate()

    def test_distinct_exact_marker_accepts_only_first_owner_push(self):
        with patch.dict(b.os.environ, {"GITHUB_EVENT_NAME": "push",
                 "GITHUB_REF": "refs/heads/main", "GITHUB_ACTOR": "mariancradulescu",
                 "GITHUB_RUN_ATTEMPT": "1"}), patch.object(
                     Path, "read_bytes", return_value=(b.MARKER + "\n").encode()):
            b.protected_owner_gate()

    def test_frozen_plan_is_nas100_only_and_still_unexecuted(self):
        blobs = AuthenticatedEconomicDevelopmentTests().fixture()
        plan = json.loads(blobs[3])
        selected = json.loads(blobs[2])["CompleteMarketNames"]
        with patch.object(b, "verify_recovery_binding", return_value=(
                    {"Markets": {"NAS100": {"Name": "NAS100"}}}, {}, selected)), \
             patch.object(b, "verify_plan_receipt", return_value=(plan["Requests"], [])), \
             patch.object(Path, "read_bytes", side_effect=[
                 blobs[0], blobs[1], blobs[2], blobs[3], blobs[3], blobs[1], blobs[1]]):
            queries = b.planned_gaps()
        self.assertEqual(len(queries), 263)
        self.assertEqual({q["Market"] for q in queries}, {"NAS100"})
        self.assertEqual({q["Timeframe"] for q in queries}, {"TICKS"})
        self.assertEqual({q["Side"] for q in queries}, {"ASK", "BID"})
        self.assertEqual(b.MAX_MARKET_REQUESTS, 2048)


if __name__ == "__main__":
    unittest.main()

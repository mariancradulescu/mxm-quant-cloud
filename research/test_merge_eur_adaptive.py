import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from . import owner_eur_checkpoint as checkpoint
from .merge_eur_adaptive import collect
from .test_owner_eur_checkpoint import fixture


class AdaptiveReplay(unittest.TestCase):
    def test_groups_join_on_identical_observer_folds(self):
        with tempfile.TemporaryDirectory() as storage:
            work = Path(storage)
            fixture(work)
            protocol = work / "protocol.json"
            synthetic = json.loads(protocol.read_bytes())
            plan = json.loads(Path("research/eur_adaptive_calibration_1.json").read_bytes())
            for key in ("InitialFitFrom", "TestBoundaries", "SourceProtocolSha256", "EvidenceManifestSha256", "StopWitness"):
                plan[key] = synthetic[key]
            plan["Stresses"] = [0.5]
            protocol.write_text(json.dumps(plan))
            evidence = []
            for group in plan["TrialGroups"]:
                report = work / (group + ".json")
                env = dict(os.environ, MXM_ECONOMIC_SCENARIO_INDEX="0", MXM_ECONOMIC_TRIAL_GROUP=group,
                           MXM_ECONOMIC_BOUNDED_NEIGHBORS="1", MXM_ECONOMIC_PAIRED_DISTRIBUTION="1",
                           MXM_ECONOMIC_REUSE_FRAMES="1")
                subprocess.run(["dotnet", checkpoint.REPLAY, "--owner-eur-historical-study", str(protocol),
                                str(work / "source.json"), str(report), str(work / "verified-protection")],
                               env=env, check=True, stdout=subprocess.DEVNULL)
                evidence.append(report)
            merged = collect(protocol, evidence)["Summary"]
            result = merged["Results"][0]
            self.assertEqual(merged["DeclaredScenarioTrialCount"], 9)
            self.assertEqual(len(result["OpportunityObservations"]), 3)
            self.assertTrue(all(len(f["EstimatorFits"]) == 7 for f in result["Fits"]))
            self.assertTrue(any(f["Fit"]["Grid"][0]["Labels"] > 0 for f in result["Fits"][-1]["EstimatorFits"]))

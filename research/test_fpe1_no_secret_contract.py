"""Public no-secrets native FPE1 smoke contract; synthetic fixture never economic evidence."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

SOURCE_IDS = ["41724643418", "41735441128", "43817213663", "44352570167", "45134137836"]

class NativeFpe1SafetyContract(unittest.TestCase):
    def test_zero_observation_does_not_fabricate_funded_edge(self):
        tape = {
            "SourceRuns": SOURCE_IDS,
            "ProtocolSha256": "a" * 64,
            "PriceNormalization": "ORIGINAL_PROTOWIRE_1E5_NO_SYNTHETIC_BAR",
            "DevelopmentOnly": True,
            "Markets": [
                {"Symbol": "SYNTHETIC_%02d" % i, "Terms": None, "Bars": {"M15": []}}
                for i in range(48)
            ],
        }
        with tempfile.TemporaryDirectory(prefix="fpe1-safety-") as d:
            src, dst = Path(d) / "input.json", Path(d) / "output.json"
            src.write_text(json.dumps(tape))
            subprocess.run(
                ["dotnet", "run", "--no-build", "-c", "Release", "--project",
                 "src/Mxm.Replay", "--", str(src), str(dst),
                 "--fpe1-complete-position-economic", "f" * 64],
                check=True, capture_output=True, text=True, timeout=120)
            got = json.loads(dst.read_text())
            self.assertEqual(got["Schema"], "FPE1_COMPLETE_POSITION_NET_FUNDED_EUR300_DEV")
            self.assertEqual(len(got["Results"]), 21)
            self.assertTrue(got["TargetIsCompletedPositionNetEUR"])
            self.assertTrue(got["NoFixedPredictionHorizon"])
            self.assertFalse(got["HistoricalExecutablePricesCertified"])
            self.assertFalse(got["HARD21Certified"])
            self.assertEqual(got["Orders"], 0)
            for row in got["Results"]:
                self.assertEqual(row["InitialCapitalEur"], 300)
                self.assertEqual(row["Completed"], 0)
                self.assertEqual(row["NET_EUR"], 0)
                self.assertFalse(row["HARD21Certified"])

if __name__ == "__main__":
    unittest.main()

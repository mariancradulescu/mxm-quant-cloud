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

    def test_completed_shadow_labels_are_not_financed_trades(self):
        # Fully synthetic contiguous bars; the test is ONLY a causal accounting fixture.
        import math
        market = {
            "Symbol": "EURUSD",
            "Terms": {
                "Symbol": "EURUSD", "QuoteAsset": "USD",
                "MinimumUnits": 1, "StepUnits": 1,
                "MaximumUnits": 100000, "LotUnits": 100000,
                "CommissionType": 2, "PreciseRateWire": 0,
                "MinimumCommissionType": 2, "PreciseMinimumWire": 0,
                "MinimumCommissionAsset": "USD", "PnlConversionFeeBps": 0,
                "SwapCalculationType": None, "LongSwap": None, "ShortSwap": None,
                "PipPosition": 5, "SwapPeriodHours": None,
                "SwapTimeUtcMinute": None, "TripleSwapWeekday": None,
                "MarginMinimumEur": 1, "SpreadBps": 1,
                "ObservedAtUtcMs": 1762128000000,
                "HistoricallyCertified": False,
            },
            "Bars": {"M15": []},
        }
        start = 1762128000000
        for i in range(160):
            op = round(1.10 + 0.0002 * math.sin(i / 5), 7)
            close = round(1.10 + 0.0002 * math.sin((i + 1) / 5), 7)
            market["Bars"]["M15"].append({
                "OpenAt": start + i * 900000, "Open": op,
                "High": max(op, close) + 0.0002,
                "Low": min(op, close) - 0.0002,
                "Close": close, "TickVolume": 100 + (i % 5),
            })
        tape = {
            "SourceRuns": SOURCE_IDS, "ProtocolSha256": "a" * 64,
            "PriceNormalization": "ORIGINAL_PROTOWIRE_1E5_NO_SYNTHETIC_BAR",
            "DevelopmentOnly": True, "Markets": [market] + [
                {"Symbol": "SYNTHETIC_%02d" % i, "Terms": None, "Bars": {"M15": []}}
                for i in range(47)
            ],
        }
        with tempfile.TemporaryDirectory(prefix="fpe1-shadow-causality-") as d:
            src, dst = Path(d) / "input.json", Path(d) / "output.json"
            src.write_text(json.dumps(tape))
            subprocess.run(
                ["dotnet", "run", "--no-build", "-c", "Release", "--project",
                 "src/Mxm.Replay", "--", str(src), str(dst),
                 "--fpe1-complete-position-economic", "f" * 64],
                check=True, capture_output=True, text=True, timeout=120)
            result = json.loads(dst.read_text())
            source = next(x for x in result["SourceCoverage"] if x["Symbol"] == "EURUSD")
            self.assertGreater(source["LabelsMatured"], 0)
            self.assertEqual(source["LabelsMatured"], source["ShadowClosed"])
            self.assertTrue(result["UnfinancedLearningLabels"])
            self.assertEqual(len(result["Results"]), 21)
            self.assertTrue(all(x["Orders"] == 0 and not x["HARD21Certified"]
                                for x in result["Results"]))
            for book in result["Results"]:
                self.assertEqual(
                    sum(w["NET_EUR"] for w in book["Weekly"]), book["NET_EUR"])
                self.assertEqual(
                    sum(x["NetEur"] for x in book["AllModeledLedgerFragments"]),
                    book["NET_EUR"])
                self.assertEqual(
                    book["CompletedLifecycleStatistics"]["Count"],
                    book["Completed"])

if __name__ == "__main__":
    unittest.main()

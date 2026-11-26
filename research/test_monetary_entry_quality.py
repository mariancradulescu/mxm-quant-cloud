"""Synthetic validation of real admission and source registration; no broker or Cloud."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from .test_owner_eur_checkpoint import fixture,START,END,DAY
from .owner_eur_checkpoint import REPLAY
from .owner_monetary_entry_quality import registered

class EntryQuality(unittest.TestCase):
    def test_registered_gate_ablation(self):
        p,_=registered()
        for mechanism in {v["Mechanism"] for v in p["Variants"]}:
            variants=[v for v in p["Variants"] if v["Mechanism"]==mechanism]
            self.assertEqual(len(variants),4)
            self.assertEqual(sum(v.get("MonetaryTraining",False) for v in variants),1)
            self.assertEqual({v.get("GateMode") for v in variants},{None,"LEGACY_MARKS","CORRECTED","COST_BAND"})
            self.assertTrue(all(v["Profile"]==variants[0]["Profile"] for v in variants))

    def test_native_actual_gate_and_training(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work)
            source=json.loads((work/"source.json").read_bytes())
            for market in source["Markets"]:market["ClosedRolloverClocks"]=[]
            (work/"source.json").write_text(json.dumps(source))
            p,_=registered()
            plan={k:p[k] for k in ("Study","Exposure","SamplingIntervalMs","Stresses")}
            variants=[v for v in p["Variants"] if v["Mechanism"]=="M5_FOLLOW"]
            # Synthetic fixture uses M5 for predictable available signals.
            for v in variants:
                profile=v["Profile"]
                profile.pop("EconomicGeometryTimeframe",None);profile.pop("EconomicStopRanges",None)
                profile.update(EconomicManagement="BRACKET",DistributionTargetRanges=1.5)
            plan.update(SourceProtocolSha256=source["ProtocolSha256"],EvidenceManifestSha256=source["EvidenceManifestSha256"],
                        Start=START,SelectionFrom=START+3*DAY,EvaluationFrom=START+6*DAY,End=END,Variants=variants)
            protocol=work/"entry-quality.json";protocol.write_text(json.dumps(plan))
            report=work/"result.json"
            subprocess.run(["dotnet",REPLAY,"--owner-opportunity-screen",str(protocol),str(work/"source.json"),
                            str(report),str(work/"verified-protection")],check=True,stdout=subprocess.DEVNULL,
                           env=dict(os.environ,MXM_OPPORTUNITY_MECHANISM="M5_FOLLOW"))
            result=json.loads(report.read_bytes())
            self.assertEqual(result["Study"],"MONETARY_ENTRY_QUALITY_2")
            self.assertEqual(result["Orders"],0)
            self.assertEqual(len(result["HeldOut"]),12)
            self.assertEqual(len(result["Candidates"]),3)
            for h in result["HeldOut"]:
                if h["Id"].endswith("__TRAINER"):
                    t=h["TrainingEvidence"]
                    self.assertGreaterEqual(t["AllReconciled"],t["NoUnknownHistory"])
                    self.assertGreaterEqual(t["NoUnknownHistory"],t["LegacyMarks"])
                    self.assertGreater(t["AllReconciled"],0)
                else:
                    self.assertEqual(h["Raw"]["Admitted"],len(h["Episodes"]))
                    for e in h["Episodes"]:
                        self.assertGreater(e["ScoreNetLowerEur"],0)
                        self.assertGreater(e["ScoreGrossLowerEur"],0)
                    self.assertEqual(h["Raw"]["Admitted"],sum(e["Scp1Admitted"] for e in h["Episodes"]))
            self.assertGreater(sum(n for h in result["HeldOut"] for k,n in h["Reasons"].items()
                                   if k.startswith("WAIT_SCORE")),0)

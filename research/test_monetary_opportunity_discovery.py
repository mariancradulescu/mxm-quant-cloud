"""Test chronology and source-overlay preservation on synthetic inputs."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from .test_owner_eur_checkpoint import fixture,START,END,DAY
from .owner_eur_checkpoint import REPLAY
from .owner_monetary_opportunity_discovery import merge_overlay,registered

class OpportunityDiscovery(unittest.TestCase):
    def test_registered_distinct_grid(self):
        p,_=registered()
        self.assertEqual(len({v["Mechanism"] for v in p["Variants"]}),7)
        for mechanism in {v["Mechanism"] for v in p["Variants"]}:
            rows=[v for v in p["Variants"] if v["Mechanism"]==mechanism]
            self.assertEqual(len(rows),7)
            self.assertEqual(sum(v["Reference"] for v in rows),1)
            self.assertEqual(sum(v["Profile"].get("EconomicOpportunityVolumeIndex")==1 for v in rows),1)
            self.assertEqual({v["Profile"]["EconomicManagement"] for v in rows},{"BRACKET","TRANSITION_VALUE","CAPTURE_VALUE"})
    def test_merge_preserves_legacy_quotes_and_conflicts(self):
        source=dict(Start=0,End=10,Tapes=[dict(Name="A",FundingQuotes=[dict(At=5,RequestedCoverage=True,Bid="1",Ask="2")])])
        prefix=dict(Status="AUTHENTIC_LATEST_PREFIX",At=4,Price="1")
        overlay=dict(QuotesBySymbol={"A":[dict(At=5,RequestedCoverage=False,Bid=None,LatestBidPrefix=prefix)]})
        self.assertEqual(merge_overlay(source,overlay),1)
        q=source["Tapes"][0]["FundingQuotes"][0]
        self.assertEqual((q["Bid"],q["Ask"],q["RequestedCoverage"],q["LatestBidPrefix"]),("1","2",True,prefix))
        with self.assertRaises(Exception):
            merge_overlay(source,dict(QuotesBySymbol={"A":[dict(At=5,LatestBidPrefix=dict(prefix,Price="3"))]}))
    def test_native_screen_isolated_and_chronological(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work)
            src=json.loads((work/"source.json").read_bytes())
            for m in src["Markets"]:m["ClosedRolloverClocks"]=[]
            (work/"source.json").write_text(json.dumps(src))
            p,_=registered()
            plan={k:p[k] for k in ("Study","Exposure","SamplingIntervalMs","Stresses")}
            variants=[v for v in p["Variants"] if v["Mechanism"]=="M5_FOLLOW" and
                      (v["Reference"] or v["Id"].endswith("__SPECIFIC_CAPTURE"))]
            plan.update(SourceProtocolSha256=src["ProtocolSha256"],EvidenceManifestSha256=src["EvidenceManifestSha256"],
                        Start=START,SelectionFrom=START+3*DAY,EvaluationFrom=START+6*DAY,End=END,Variants=variants)
            protocol=work/"screen.json";protocol.write_text(json.dumps(plan))
            report=work/"result.json"
            subprocess.run(["dotnet",REPLAY,"--owner-opportunity-screen",str(protocol),str(work/"source.json"),
                str(report),str(work/"verified-protection")],check=True,stdout=subprocess.DEVNULL,
                env=dict(os.environ,MXM_OPPORTUNITY_MECHANISM="M5_FOLLOW"))
            result=json.loads(report.read_bytes())
            self.assertEqual(result["SharedPortfolioEvaluations"],0)
            self.assertEqual(result["Orders"],0)
            self.assertEqual(len(result["Selection"]),6)
            self.assertGreater(sum(x["Raw"]["Admitted"] for x in result["Selection"]),0)
            for h in result["HeldOut"]:
                for e in h["Episodes"]:
                    self.assertGreaterEqual(e["At"],plan["EvaluationFrom"])
                    self.assertLess(e["At"],END)
                    if e["NetEur"] is not None:self.assertLess(e["AvailableAt"],END)
                    if e["Status"]=="RIGHT_CENSORED":self.assertIsNone(e["NetEur"])

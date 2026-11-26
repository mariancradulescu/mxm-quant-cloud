"""Synthetic tests for the registered broad geometry/fill experiment."""
import json,os,subprocess,tempfile,unittest
from pathlib import Path
from .test_owner_eur_checkpoint import fixture,START,END,DAY
from .owner_eur_checkpoint import REPLAY
from .owner_monetary_geometry_breadth import registered,verify_original
from .source_history_universe import digest,canonical

class GeometryBreadth(unittest.TestCase):
    def test_registered_ablation_and_full_scope(self):
        p,_=registered()
        self.assertEqual(len(p["Instruments"]),21)
        for mechanism in {v["Mechanism"] for v in p["Variants"]}:
            rows={v["Id"].split("__")[1]:v["Profile"] for v in p["Variants"] if v["Mechanism"]==mechanism}
            self.assertEqual(set(rows),{"BASE","FILL_RISK","STRUCTURE","STRUCTURE_RISK","STRUCTURE_RISK_MANAGEMENT","STRUCTURE_RISK_VOLUME"})
            self.assertEqual(rows["FILL_RISK"],dict(rows["BASE"],KeepAdmissionRiskAtFill=True,ResizeWithinAdmissionRiskAtFill=True))
            self.assertEqual(rows["STRUCTURE"],dict(rows["BASE"],AnchorEconomicGeometryToClosedStructure=True))
            self.assertEqual(rows["STRUCTURE_RISK"],dict(rows["STRUCTURE"],KeepAdmissionRiskAtFill=True,ResizeWithinAdmissionRiskAtFill=True))
            self.assertEqual(rows["STRUCTURE_RISK_MANAGEMENT"]["EconomicManagementTimeframe"],"M5")
            self.assertEqual(rows["STRUCTURE_RISK_VOLUME"],dict(rows["STRUCTURE_RISK"],MinimumContractVolumeOnly=False,OptimizeEconomicOpportunityVolume=True))

    def test_source_byte_identity_and_scope(self):
        p,_=registered()
        raw=canonical(dict(Start=p["Start"],End=p["End"],Markets=[dict(Market=dict(Name=m)) for m in p["Instruments"]]))
        p["OriginalBreadthSourceSha256"]=digest(raw)
        receipt=dict(SourceSha256=digest(raw),ProtocolSha256="a"*64,EvidenceManifestSha256="b"*64,
                     Proof=dict(MarketCount=21),SourceBrokerRequests=0)
        self.assertEqual(len(verify_original(p,raw,receipt,receipt)["Markets"]),21)
        with self.assertRaises(Exception):
            verify_original(p,raw+b" ",receipt,receipt)

    def test_native_geometry_fill_ablation(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);fixture(work)
            source=json.loads((work/"source.json").read_bytes())
            p,_=registered()
            plan={k:p[k] for k in ("Study","Exposure","SamplingIntervalMs","Stresses")}
            variants=[v for v in p["Variants"] if v["Mechanism"]=="M5_FOLLOW"]
            for v in variants:
                profile=v["Profile"]
                profile.update(EconomicGeometryTimeframe="M5",EconomicStopRanges=1,DistributionTargetRanges=1.5)
            plan.update(SourceProtocolSha256=source["ProtocolSha256"],EvidenceManifestSha256=source["EvidenceManifestSha256"],
                        Start=START,SelectionFrom=START+3*DAY,EvaluationFrom=START+6*DAY,End=END,Variants=variants)
            protocol=work/"geometry.json";protocol.write_text(json.dumps(plan))
            report=work/"result.json"
            subprocess.run(["dotnet",REPLAY,"--owner-opportunity-screen",str(protocol),str(work/"source.json"),
                            str(report),str(work/"verified-protection")],check=True,stdout=subprocess.DEVNULL,
                           env=dict(os.environ,MXM_OPPORTUNITY_MECHANISM="M5_FOLLOW"))
            r=json.loads(report.read_bytes())
            self.assertEqual(r["Study"],p["Study"])
            self.assertEqual(r["RegisteredMarketCount"],2)
            self.assertEqual(len(r["HeldOut"]),18)
            self.assertEqual(len(r["Candidates"]),6)
            self.assertEqual(r["Orders"],0)
            for h in r["HeldOut"]:
                q=h["BreadthQuality"]
                self.assertEqual(len(q["Instruments"]),2)
                self.assertEqual(sum(x["Quality"]["Known"] for x in q["Instruments"]),h["Raw"]["KnownClosed"])
                self.assertEqual(q["All"]["PeerForecasts"],0) # two symbols cannot supply two excluded peers
                if "RISK" in h["Id"]:
                    self.assertEqual(q["All"]["RiskGrowthAtFill"],0)
            self.assertGreater(sum(h["Raw"]["KnownClosed"] for h in r["HeldOut"]),0)

"""Distinct causal entry-quality study; reuse verified source without broker reads."""
import argparse,json,os
from pathlib import Path
from . import owner_monetary_opportunity_discovery as prior
from . import owner_eur_recent_archive as archive
from . import source_history_universe as src
from .decode import need

REGISTRY=Path("research/monetary_entry_quality_2.json")

def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    old,_=prior.registered()
    need(p["Study"]=="MONETARY_ENTRY_QUALITY_2" and p["SamplingIntervalMs"]==1800000 and
         p["DiscoveryOriginalArtifact"]==15101501689 and p["Orders"]==0 and
         p["CloudActivated"] is p["IndependentConfirmationCertified"] is False and len(p["Variants"])==28,
         "ENTRY_QUALITY_REGISTRY")
    for k in ("Start","SelectionFrom","EvaluationFrom","End","Stresses","Instruments","OriginalMechanismArtifact",
              "OriginalMechanismSha256","PrefixArtifact","PrefixSha256"):
        need(p[k]==old[k],"ENTRY_QUALITY_ORIGINAL_SCOPE")
    return p,src.digest(raw)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("stage",choices=("download","materialize"))
    ap.add_argument("--work",type=Path);ap.add_argument("--receipt",type=Path);a=ap.parse_args()
    p,digest=registered();old,old_digest=prior.registered()
    if a.stage=="download":
        prior.download(old)
        archive.download_archive(p["DiscoveryOriginalArtifact"],p["DiscoveryOriginalRun"],p["DiscoveryOriginalSha256"],
            Path("original-discovery-result"))
        return
    prior.materialize(old,old_digest,a.work,a.receipt)
    base=json.loads(a.receipt.read_bytes());source=json.loads((a.work/"source.json").read_bytes())
    original=json.loads(Path("original-discovery-result/opportunity-source.json").read_bytes())
    need(base["Proof"]["BaseByteIdentical"] is True and original["Proof"]["BaseByteIdentical"] is True and
         base["Proof"]["BaseSourceSha256"]==original["Proof"]["BaseSourceSha256"] and
         base["Proof"]["PrefixArchiveSha256"]==original["Proof"]["PrefixArchiveSha256"],"ENTRY_QUALITY_SOURCE_REUSE")
    proof=dict(Base=base,DiscoveryOriginalArtifact=p["DiscoveryOriginalArtifact"],DiscoveryOriginalSha256=p["DiscoveryOriginalSha256"],
        OriginalResultsModified=False,SourceBrokerRequests=0)
    source.update(ProtocolSha256=digest,EvidenceManifestSha256=src.digest(src.canonical(proof)))
    protocol={k:p[k] for k in ("Study","Exposure","Start","SelectionFrom","EvaluationFrom","End","SamplingIntervalMs","Stresses","Variants")}
    protocol.update(SourceProtocolSha256=digest,EvidenceManifestSha256=source["EvidenceManifestSha256"])
    private,pr=src.canonical(source),src.canonical(protocol)
    (a.work/"source.json").write_bytes(private);(a.work/"opportunity-protocol.json").write_bytes(pr)
    a.receipt.write_bytes(src.canonical(dict(Study=p["Study"],Proof=proof,SourceSha256=src.digest(private),
        ProtocolSha256=src.digest(pr),EvidenceManifestSha256=source["EvidenceManifestSha256"],SourceBrokerRequests=0,
        Orders=0,CloudActivated=False,IndependentConfirmationCertified=False)))
    print("ENTRY_QUALITY_SOURCE_REUSED",p["DiscoveryOriginalArtifact"],flush=True)

if __name__=="__main__":main()

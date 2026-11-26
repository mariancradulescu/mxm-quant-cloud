"""Materialize the archived 21-market source once; no broker requests.
Original source reconstruction is verified byte for byte before new protocol
identity is attached. No original economic replay is executed.
"""
import argparse,json,os
from pathlib import Path
from . import owner_eur_recent_archive as archive
from . import owner_eur_recent_funded as recent
from . import source_history_universe as src
from .decode import need

REGISTRY=Path("research/monetary_geometry_breadth_1.json")
OLD=Path("original-21-market-result")
SUMMARY=Path("bound-21-market-summary")
ENTRY=Path("original-entry-quality-result")

def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    need(p["Study"]=="MONETARY_GEOMETRY_BREADTH_1" and
         p["Exposure"]=="PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT" and
         p["OriginalBreadthRun"]==45748263383 and p["OriginalBreadthArtifact"]==15085058948 and
         p["OriginalEntryQualityArtifact"]==15103549478 and p["CollectionRun"]==45716198383 and
         p["Start"]<p["SelectionFrom"]<p["EvaluationFrom"]<p["End"] and
         len(p["Instruments"])==len(set(p["Instruments"]))==21 and "XAUUSD" in p["Instruments"] and
         p["Stresses"]==[0,.5,1] and p["SamplingIntervalMs"]==1800000 and
         p["Orders"]==0 and p["CloudActivated"] is p["IndependentConfirmationCertified"] is False,
         "GEOMETRY_BREADTH_REGISTRY")
    variants=p["Variants"]
    groups={v["Mechanism"] for v in variants}
    need(len(variants)==35 and len(groups)==7 and len({v["Id"] for v in variants})==35,
         "GEOMETRY_BREADTH_VARIANTS")
    for m in groups:
        rows=[v for v in variants if v["Mechanism"]==m]
        need(len(rows)==5 and sum(v["Reference"] for v in rows)==1 and
             all(v["MonetaryTraining"] and v["Profile"]["EconomicMechanism"]==m and
                 not v["Profile"].get("ModelFundingAtPriorClosedSessionQuote") for v in rows),
             "GEOMETRY_BREADTH_PROFILE")
    return p,src.digest(raw)

def download(p):
    for art,run,digest,dest in (
        ("OriginalBreadthArtifact","OriginalBreadthRun","OriginalBreadthSha256",OLD),
        ("CollectionSummaryArtifact","CollectionRun","CollectionSummarySha256",SUMMARY),
        ("OriginalEntryQualityArtifact","OriginalEntryQualityRun","OriginalEntryQualitySha256",ENTRY)):
        archive.download_archive(p[art],p[run],p[digest],dest)
    need((SUMMARY/"recent-source-summary.json").read_bytes()==Path("recent-source-summary.json").read_bytes(),
         "GEOMETRY_BREADTH_COLLECTION_SUMMARY_IDENTITY")
    entry=json.loads((ENTRY/"economic-opportunities.json").read_bytes())
    need(entry["Study"]=="MONETARY_ENTRY_QUALITY_2" and len(entry["Results"])==7 and
         all(r["SelectedDecision"]=="WAIT" for r in entry["Results"]),"GEOMETRY_BREADTH_PRIOR_RESULT")

def verify_original(p,source_raw,receipt,original):
    source_hash=src.digest(source_raw)
    need(source_hash==p["OriginalBreadthSourceSha256"]==receipt["SourceSha256"]==original["SourceSha256"] and
         receipt["ProtocolSha256"]==original["ProtocolSha256"] and
         receipt["EvidenceManifestSha256"]==original["EvidenceManifestSha256"] and
         receipt["Proof"]==original["Proof"] and receipt["SourceBrokerRequests"]==0,
         "GEOMETRY_BREADTH_SOURCE_BYTE_IDENTITY")
    source=json.loads(source_raw)
    need(source["Start"]<=p["Start"] and source["End"]==p["End"] and
         sorted(m["Market"]["Name"] for m in source["Markets"])==p["Instruments"] and
         len(source["Markets"])==21,"GEOMETRY_BREADTH_SOURCE_SCOPE")
    return source

def materialize(p,digest,work,receipt_path):
    original=json.loads((OLD/"recent-funded-source.json").read_bytes())
    # The earlier base-recovery routine uses its own frozen original revision.
    # Preserve the previously published source bytes before assigning this study.
    revision=os.environ["GITHUB_SHA"]
    os.environ["GITHUB_SHA"]=p["OriginalBreadthRevision"]
    try:
        recent.materialize(work,receipt_path)
    finally:
        os.environ["GITHUB_SHA"]=revision
    base_raw=(work/"source.json").read_bytes()
    receipt=json.loads(receipt_path.read_bytes())
    source=verify_original(p,base_raw,receipt,original)
    proof=dict(OriginalBreadthArtifact=p["OriginalBreadthArtifact"],OriginalBreadthSha256=p["OriginalBreadthSha256"],
        OriginalBreadthSourceSha256=p["OriginalBreadthSourceSha256"],OriginalEntryQualityArtifact=p["OriginalEntryQualityArtifact"],
        OriginalEntryQualitySha256=p["OriginalEntryQualitySha256"],CollectionSummaryArtifact=p["CollectionSummaryArtifact"],
        CollectionSummarySha256=p["CollectionSummarySha256"],SourceByteIdentity=True,PriorProof=receipt["Proof"],
        MarketCount=len(source["Markets"]),OriginalResultsModified=False,SourceBrokerRequests=0,
        FundingBasis=p["FundingBasis"])
    source.update(ProtocolSha256=digest,EvidenceManifestSha256=src.digest(src.canonical(proof)),EngineRevision=revision)
    plan={k:p[k] for k in ("Study","Exposure","Start","SelectionFrom","EvaluationFrom","End","SamplingIntervalMs","Stresses","Variants")}
    plan.update(SourceProtocolSha256=digest,EvidenceManifestSha256=source["EvidenceManifestSha256"])
    raw,pr=src.canonical(source),src.canonical(plan)
    (work/"source.json").write_bytes(raw)
    (work/"opportunity-protocol.json").write_bytes(pr)
    receipt_path.write_bytes(src.canonical(dict(Study=p["Study"],Proof=proof,SourceSha256=src.digest(raw),
        ProtocolSha256=src.digest(pr),EvidenceManifestSha256=source["EvidenceManifestSha256"],
        SourceBrokerRequests=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False)))
    print("GEOMETRY_BREADTH_SOURCE_BYTE_IDENTITY",len(source["Markets"]),"MARKETS",flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=("download","materialize"))
    parser.add_argument("--work",type=Path);parser.add_argument("--receipt",type=Path);a=parser.parse_args()
    p,digest=registered()
    if a.stage=="download":download(p)
    else:materialize(p,digest,a.work,a.receipt)

if __name__=="__main__":main()

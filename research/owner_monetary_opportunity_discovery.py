"""Source-only reuse for monetary opportunity discovery. No network to broker."""
import argparse
import json
import os
from pathlib import Path
from . import owner_economic_mechanisms as prior
from . import owner_funding_prefix_settlement as prefix
from . import owner_eur_recent_archive as archive
from . import owner_eer1_source as eer
from . import source_history_universe as src
from .decode import need

REGISTRY=Path("research/monetary_opportunity_discovery_1.json")
PREFIX=Path("verified-prefix-overlay")

def registered():
    raw=REGISTRY.read_bytes();p=json.loads(raw)
    need(p["Study"]=="MONETARY_OPPORTUNITY_DISCOVERY_1" and p["OriginalMechanismRun"]==45769642512 and
         p["PrefixRun"]==45775907825 and p["Orders"]==0 and p["CloudActivated"] is p["IndependentConfirmationCertified"] is False,
         "OPPORTUNITY_REGISTRATION")
    need(p["Start"]<p["SelectionFrom"]<p["EvaluationFrom"]<p["End"] and p["SamplingIntervalMs"]==3600000 and
         p["Stresses"]==[0,.5,1] and len(p["Variants"])==49 and
         len({v["Id"] for v in p["Variants"]})==49,"OPPORTUNITY_GRID")
    return p,src.digest(raw)

def download(p):
    archive.download_archive(p["MechanismFundingArtifact"],p["OriginalMechanismRun"],p["MechanismFundingSha256"],prior.OUT)
    archive.download_archive(p["PrefixArtifact"],p["PrefixRun"],p["PrefixSha256"],PREFIX)
    archive.download_archive(p["PrefixProtectedArtifact"],p["PrefixRun"],p["PrefixProtectedSha256"],prefix.OUT)

def overlay_from_rows(rows):
    overlay={}
    for row in rows:
        target=row["Target"];key=(target["Symbol"],target["At"])
        need(row["Witness"]["Status"]=="AUTHENTIC_LATEST_PREFIX","OPPORTUNITY_PREFIX_UNRESOLVED")
        quote=overlay.setdefault(key,dict(At=target["At"],RequestedCoverage=False,BidAt=None,AskAt=None,Bid=None,Ask=None))
        field="LatestBidPrefix" if target["Side"]=="BID" else "LatestAskPrefix"
        need(field not in quote,"OPPORTUNITY_PREFIX_DUPLICATE")
        quote[field]=row["Witness"]
    return {name:[q for (symbol,_),q in sorted(overlay.items()) if symbol==name] for name in sorted({x[0] for x in overlay})}

def verify_overlay(p):
    rid=str(p["PrefixRun"]);raw=prefix.PLAN.read_bytes();reg=json.loads(raw)
    receipt=json.loads((prefix.OUT/"receipt.json").read_bytes())
    data=eer.unpack(prefix.OUT,receipt["sealed"],os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode(),rid)
    need(data["runId"]==rid and data["protocolSha256"]==src.digest(raw),"OPPORTUNITY_PREFIX_BINDING")
    packets=data["packets"];account=src.decode(packets[0]["reqType"],packets[0]["req"]).ctidTraderAccountId
    need(src.original_account(account),"OPPORTUNITY_PREFIX_ACCOUNT")
    journal=src.ReadbackJournal(packets);rows=prefix.collect(journal,account,reg)
    need(rows==data["rows"] and journal.index==len(packets)==receipt["requests"]==7,"OPPORTUNITY_PREFIX_READBACK")
    overlay=json.loads((PREFIX/"prefix-funding-overlay.json").read_bytes())
    settlement=json.loads((PREFIX/"latest-prefix-settlement.json").read_bytes())
    need(overlay["QuotesBySymbol"]==overlay_from_rows(rows) and overlay["Receipt"]==receipt and
         overlay["RegistrySha256"]==src.digest(raw) and settlement["OriginalRun"]==p["OriginalMechanismRun"] and
         settlement["OriginalArchiveSha256"]==p["OriginalMechanismSha256"] and
         settlement["OriginalResultModified"] is settlement["OriginalDecisionsReplayed"] is False,
         "OPPORTUNITY_PREFIX_OVERLAY_PARITY")
    return overlay,settlement,max(x["availableAt"] for x in packets)

def merge_overlay(source,overlay):
    count=0
    tapes={t["Name"]:t for t in source["Tapes"]}
    for name,rows in overlay["QuotesBySymbol"].items():
        need(name in tapes,"OPPORTUNITY_PREFIX_SYMBOL")
        tape=tapes[name];original={q["At"]:q for q in tape["FundingQuotes"]}
        for q in rows:
            at=q["At"];need(source["Start"]<=at<source["End"],"OPPORTUNITY_PREFIX_CLOCK")
            previous=original.get(at,dict(At=at,RequestedCoverage=False))
            merged=dict(previous)
            for k in ("LatestBidPrefix","LatestAskPrefix"):
                if k not in q:continue
                need(k not in merged or merged[k]==q[k],"OPPORTUNITY_PREFIX_CONFLICT")
                merged[k]=q[k];count+=1
            original[at]=merged
        tape["FundingQuotes"]=[original[t] for t in sorted(original)]
    return count

def materialize(p,digest,work,receipt_path):
    old,old_digest=prior.registered()
    # Reconstruct the preserved base under its original source revision.
    # This is a byte-identity check, not an economic execution or checkout.
    saved=os.environ.get("MXM_ECONOMIC_ARCHIVE_CHECKPOINT_ORIGINAL_REVISION")
    os.environ["MXM_ECONOMIC_ARCHIVE_CHECKPOINT_ORIGINAL_REVISION"]=p["OriginalMechanismRevision"]
    try:
        prior.materialize(work,receipt_path,old,old_digest,source_run=p["OriginalMechanismRun"])
    finally:
        if saved is None:os.environ.pop("MXM_ECONOMIC_ARCHIVE_CHECKPOINT_ORIGINAL_REVISION",None)
        else:os.environ["MXM_ECONOMIC_ARCHIVE_CHECKPOINT_ORIGINAL_REVISION"]=saved
    source_raw=(work/"source.json").read_bytes();base=json.loads(receipt_path.read_bytes())
    source=json.loads(source_raw)
    overlay,settlement,acquired=verify_overlay(p)
    need(source["Start"]==p["Start"] and source["End"]==p["End"] and
         sorted(x["Market"]["Name"] for x in source["Markets"])==sorted(p["Instruments"]),"OPPORTUNITY_SOURCE_SCOPE")
    added=merge_overlay(source,overlay)
    need(added==7,"OPPORTUNITY_PREFIX_COUNT")
    proof=dict(Base=base,BaseSourceSha256=src.digest(source_raw),OriginalSourceSha256=settlement["OriginalSourceSha256"],
        BaseByteIdentical=src.digest(source_raw)==settlement["OriginalSourceSha256"],PrefixArtifact=p["PrefixArtifact"],
        PrefixArchiveSha256=p["PrefixSha256"],PrefixPacketsReconciled=added,
        PrefixBasis="AUTHENTIC_AS_OF_PREFIX_CONDITIONAL_TARIFF_NOT_BROKER_SETTLEMENT",
        OriginalResultsModified=False,SourceBrokerRequests=0)
    source.update(ProtocolSha256=digest,EvidenceManifestSha256=src.digest(src.canonical(proof)),
        SourceAcquiredAt=max(source["SourceAcquiredAt"],acquired),EngineRevision=os.environ["GITHUB_SHA"])
    protocol={k:p[k] for k in ("Study","Exposure","Start","SelectionFrom","EvaluationFrom","End","SamplingIntervalMs","Stresses","Variants")}
    protocol.update(SourceProtocolSha256=digest,EvidenceManifestSha256=source["EvidenceManifestSha256"])
    private,pr=src.canonical(source),src.canonical(protocol)
    (work/"source.json").write_bytes(private);(work/"opportunity-protocol.json").write_bytes(pr)
    receipt_path.write_bytes(src.canonical(dict(Study=p["Study"],Proof=proof,SourceSha256=src.digest(private),
        ProtocolSha256=src.digest(pr),EvidenceManifestSha256=source["EvidenceManifestSha256"],
        SourceBrokerRequests=0,Orders=0,CloudActivated=False,IndependentConfirmationCertified=False)))
    print("OPPORTUNITY_SOURCE_REUSED",added,"PREFIX_WITNESSES","BASE_BYTE_IDENTITY",proof["BaseByteIdentical"],flush=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("stage",choices=("download","materialize"))
    parser.add_argument("--work",type=Path);parser.add_argument("--receipt",type=Path)
    a=parser.parse_args();p,digest=registered()
    if a.stage=="download":download(p)
    else:materialize(p,digest,a.work,a.receipt)

if __name__=="__main__":main()

"""Materialize the frozen dense source into the existing native historical Replay.

Private packets and protection tapes stay inside the custody runner.
No new account requests, no historical-tariff or execution-continuity certification.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from . import owner_eur_authentic_expansion as expansion
from . import owner_eur_dense_monetary as dense
from . import source_history_universe as src
from .custody import unseal_new
from .decode import need

REGISTRY = Path("research/eur_dense_funded_2.json")


def download(entry, members):
    repo=os.environ["GITHUB_REPOSITORY"]
    endpoint=f"repos/{repo}/actions/artifacts/{entry['Artifact']}"
    meta=json.loads(subprocess.check_output(["gh","api",endpoint]))
    need(meta["workflow_run"]["id"]==entry["Run"] and
         meta["digest"]=="sha256:"+entry["ArchiveSha256"] and not meta["expired"],
         "DENSE_FUNDED_ARCHIVE_IDENTITY")
    if "Name" in entry:
        need(meta["name"]==entry["Name"],"DENSE_FUNDED_ARCHIVE_NAME")
    dest=Path(entry["Folder"])
    dest.mkdir(parents=True,exist_ok=False,mode=0o700)
    with tempfile.TemporaryDirectory() as work:
        archive=Path(work)/"original.zip"
        with archive.open("xb") as stream:
            subprocess.run(["gh","api",endpoint+"/zip"],stdout=stream,check=True)
        need(hashlib.sha256(archive.read_bytes()).hexdigest()==entry["ArchiveSha256"],"DENSE_FUNDED_ARCHIVE_HASH")
        with zipfile.ZipFile(archive) as z:
            for member in members:
                (dest/member).write_bytes(z.read(member))


def readback(registration,key):
    verified={a["Name"].replace("dense-monetary-verified-",""):a for a in registration["VerifiedArchives"]}
    totals=dict(partitions=0,requests=0,marks=0,hours=0)
    seen=set()
    for a in registration["DenseArchives"]:
        identity=a["Name"].replace("dense-monetary-protected-","")
        need(identity in verified and identity not in seen,"DENSE_FUNDED_PARTITION")
        seen.add(identity)
        folder=Path(a["Folder"])
        receipt=json.loads((folder/"receipt.json").read_bytes())
        public=json.loads((Path(verified[identity]["Folder"])/"dense-monetary-verified.json").read_bytes())
        need(public==dict(receipt,packetsReconciled=receipt["requests"],readbackBrokerRequests=0),
             "DENSE_FUNDED_VERIFIED_RECEIPT")
        cipher=(folder/"packets.sealed").read_bytes()
        run=str(registration["DenseRun"])
        need(str(receipt["runId"])==run and src.digest(cipher)==receipt["ciphertextSha256"],"DENSE_FUNDED_CIPHER")
        raw=unseal_new(cipher,key,run)
        need(src.digest(raw)==receipt["plaintextSha256"],"DENSE_FUNDED_PLAINTEXT")
        original=json.loads(raw)
        packets=original["packets"]
        plan,digest,sid,start=dense.registered(receipt["symbol"],receipt["window"])
        need(bool(packets),"DENSE_FUNDED_EMPTY_PACKETS")
        account=src.decode(packets[0]["reqType"],packets[0]["req"]).ctidTraderAccountId
        need(src.original_account(account),"DENSE_FUNDED_ACCOUNT")
        journal=src.ReadbackJournal(packets)
        report=dense.collect(journal,account,plan,receipt["symbol"],sid,receipt["window"],start,digest)
        report.update(runId=run,requests=len(packets))
        need(journal.index==len(packets) and report==original["report"] and
             receipt==dict(report,ciphertextSha256=src.digest(cipher),plaintextSha256=src.digest(raw)),
             "DENSE_FUNDED_PACKET_PARITY")
        totals["partitions"]+=1
        totals["requests"]+=len(packets)
        totals["marks"]+=report["verifiedTwoSidedMarks"]
        totals["hours"]+=report["completeResponseHours"]
    need(seen==set(verified) and totals["partitions"]==registration["ExpectedVerifiedPartitions"] and
         totals["requests"]==registration["ExpectedVerifiedRequests"] and
         totals["marks"]==registration["ExpectedVerifiedMarks"],"DENSE_FUNDED_TOTALS")
    return totals


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage",choices=("download","materialize"))
    parser.add_argument("--work",type=Path)
    parser.add_argument("--receipt",type=Path)
    args=parser.parse_args()
    raw=REGISTRY.read_bytes()
    registration=json.loads(raw)
    if args.stage=="download":
        dense_folders={a["Folder"]:a for a in registration["DenseArchives"]}
        for a in registration["Earlier"]["Archives"]:
            download(dense_folders.get(a["Folder"],a),("receipt.json","packets.sealed"))
        for a in registration["VerifiedArchives"]:
            download(a,("dense-monetary-verified.json",))
        return
    key=os.environ["R3_CUSTODY_PRIVATE_KEY_PEM"].encode()
    totals=readback(registration,key)
    args.work.mkdir(mode=0o700)
    source,proof=expansion.earlier(registration,key,args.work)
    proof["DenseReadback"]=totals
    proof["DenseVerifiedArchives"]=registration["VerifiedArchives"]
    proof["Mode"]="EARLIER_DENSE_AND_SAMPLED_TICKS"
    proof["PriorSampledQuoteControl"]="EUR_AUTHENTIC_EXPANSION_1_EARLIER"
    source["ProtocolSha256"]=src.digest(raw)
    source["EvidenceManifestSha256"]=src.digest(src.canonical(proof))
    template=json.loads(Path("research/eur_predictive_calibration_2.json").read_bytes())
    scope=registration["Earlier"]
    calibrations=template["Calibrations"]
    broad=calibrations[0]["Id"]
    trials=[dict(Id="CASH_CONTROL",Policy="EUR_GENERAL_CASH",Calibration=broad),
            dict(Id="FINANCEABLE_PROBE",Policy="EUR_GENERAL_PROBE",Calibration=broad)]
    trials.extend(t for t in template["Trials"] if t["Id"] in scope["Trials"])
    need([t["Id"] for t in trials]==scope["Trials"],"DENSE_FUNDED_REGISTERED_TRIALS")
    plan=dict(Study=registration["Study"],Exposure=template["Exposure"],
              SourceProtocolSha256=source["ProtocolSha256"],EvidenceManifestSha256=source["EvidenceManifestSha256"],
              InitialFitFrom=scope["InitialFitFrom"],TestBoundaries=scope["TestBoundaries"],Stresses=template["Stresses"],
              Calibrations=calibrations,Trials=trials,ArchivedSampledQuotes=True,
              TrialGroups={"DENSE":[t["Id"] for t in trials]})
    source_bytes=src.canonical(source)
    plan_bytes=src.canonical(plan)
    for path,data in ((args.work/"source.json",source_bytes),(args.work/"protocol.json",plan_bytes)):
        with path.open("xb") as stream:
            stream.write(data)
        path.chmod(0o600)
    public=dict(Study=registration["Study"],RegistrationSha256=source["ProtocolSha256"],
        EvidenceManifestSha256=source["EvidenceManifestSha256"],SourceSha256=src.digest(source_bytes),
        ProtocolSha256=src.digest(plan_bytes),Proof=proof,Orders=0,SourceBrokerRequests=0,CloudActivated=False)
    args.receipt.write_bytes(src.canonical(public))
    print("DENSE_FUNDED_MATERIALIZED",totals,proof["coverage"],flush=True)


if __name__=="__main__":
    main()

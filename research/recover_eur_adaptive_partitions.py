"""Preserve and verify the unchanged native estimator partitions of the interrupted study."""
import json
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from .merge_eur_scenarios import require


def gh(path):
    return json.loads(subprocess.check_output(["gh","api",path]))


def recover(destination, evidence_path):
    plan=json.loads(Path("research/eur_adaptive_calibration_1_portfolio_recovery.json").read_bytes())
    run,revision=plan["OriginalRun"],plan["OriginalRevision"]
    root=f"repos/{os.environ['GITHUB_REPOSITORY']}/actions"
    prior=gh(f"{root}/runs/{run}")
    require(prior["head_sha"]==revision and prior["event"]=="push","EUR_ORIGINAL_ESTIMATOR_RUN")
    expected={f"eur-adaptive-result-{i}-ESTIMATORS" for i in range(3)}
    deadline=time.monotonic()+100*60
    while True:
        artifacts={a["name"]:a for a in gh(f"{root}/runs/{run}/artifacts?per_page=100")["artifacts"]
                   if a["name"] in expected and not a["expired"]}
        if expected==set(artifacts):
            break
        jobs=gh(f"{root}/runs/{run}/jobs?per_page=100")["jobs"]
        require(not any("ESTIMATORS" in x["name"] and x["status"]=="completed" and x["conclusion"]!="success" for x in jobs),
                "EUR_ORIGINAL_ESTIMATOR_PARTITION_FAILED")
        require(time.monotonic()<deadline,"EUR_ORIGINAL_ESTIMATOR_RESULT_PENDING")
        print("VERIFIED_ORIGINAL_ESTIMATOR_REPORTS_AVAILABLE",len(artifacts),"/",len(expected),flush=True)
        time.sleep(30)
    receipts=[]
    for name in sorted(artifacts):
        receipt=artifacts[name]
        require(receipt["workflow_run"]["id"]==run and receipt["workflow_run"]["head_sha"]==revision,
                "EUR_ORIGINAL_ESTIMATOR_ARTIFACT_REVISION")
        folder=destination/name
        folder.mkdir(parents=True,exist_ok=False)
        archive=folder/"original.zip"
        with archive.open("xb") as f:
            subprocess.run(["gh","api",f"{root}/artifacts/{receipt['id']}/zip"],stdout=f,check=True)
        require("sha256:"+sha256(archive.read_bytes()).hexdigest()==receipt["digest"],"EUR_ORIGINAL_ESTIMATOR_ARTIFACT_SHA256")
        with zipfile.ZipFile(archive) as z:
            (folder/"adaptive-partition.json").write_bytes(z.read("adaptive-partition.json"))
        archive.unlink()
        receipts.append(dict(Artifact=receipt["id"],Name=name,ArchiveDigest=receipt["digest"]))
    evidence_path.write_text(json.dumps(dict(Run=run,Revision=revision,EstimatorArchives=receipts),indent=2)+"\n")


if __name__=="__main__":
    recover(Path(sys.argv[1]),Path(sys.argv[2]))

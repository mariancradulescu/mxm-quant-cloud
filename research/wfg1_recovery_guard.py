"""Authorize a new WFG1 attempt only after an unused original is terminal."""
import datetime as dt
import json
import os
import time
import urllib.error
import urllib.request

REPOSITORY = "mariancradulescu/mxm-quant-cloud"
ORIGINAL = 43096900076
PIN = "8772dd45dc7768c48d44b50ea8bd909bd7075b28"
BASE = f"https://api.github.com/repos/{REPOSITORY}/actions/runs/{ORIGINAL}"
ECONOMIC_JOB = "original-source-development"


def request(suffix="", method="GET"):
    req = urllib.request.Request(BASE + suffix, method=method, headers={
        "Authorization": "Bearer " + os.environ["GH_TOKEN"],
        "Accept": "application/vnd.github+json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            return json.load(response) if method == "GET" else response.status
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub {method} {suffix or '/'} returned HTTP {exc.code}") from None


def original_state():
    run = request()
    if (run["id"], run["head_sha"], run["head_branch"], run["run_attempt"]) != (
        ORIGINAL, PIN, "main", 1
    ):
        raise RuntimeError("Original run identity or attempt changed")
    jobs = request("/attempts/1/jobs?per_page=100")
    artifacts = request("/artifacts?per_page=100")
    if jobs["total_count"] != len(jobs["jobs"]) or artifacts["total_count"]:
        raise RuntimeError("Incomplete job listing or original artifact already exists")
    for job in jobs["jobs"]:
        if job["name"] == ECONOMIC_JOB and (
            job["conclusion"] != "skipped" or job.get("steps")
        ):
            raise RuntimeError("Original economic job may have executed")
    return run, jobs["total_count"]


def verify_terminal(run):
    if run["status"] != "completed" or run["conclusion"] not in {
        "cancelled", "failure", "timed_out", "stale", "startup_failure"
    }:
        raise RuntimeError("Original is not in a verified terminal non-economic state")
    return run["conclusion"]


def recover():
    run, job_count = original_state()
    if run["status"] == "completed":
        return verify_terminal(run)
    created = dt.datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
    age = dt.datetime.now(dt.timezone.utc) - created
    if run["status"] != "queued" or job_count or age < dt.timedelta(minutes=45):
        raise RuntimeError("Original can still progress or already has jobs")
    if request("/cancel", method="POST") != 202:
        raise RuntimeError("GitHub did not accept original cancellation")
    for _ in range(24):
        run, _ = original_state()
        if run["status"] == "completed":
            return verify_terminal(run)
        time.sleep(5)
    raise RuntimeError("GitHub accepted cancellation but original is not terminal")


if __name__ == "__main__":
    if os.environ["GITHUB_REPOSITORY"] != REPOSITORY or os.environ["GITHUB_REF"] != "refs/heads/main":
        raise SystemExit("Wrong repository or ref")
    result = recover()
    print(f"Original run {ORIGINAL}, attempt 1, terminal {result}; no economic execution found")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        print(f"original_conclusion={result}", file=output)

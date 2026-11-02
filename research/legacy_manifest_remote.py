"""Read-only admission of 100 ORIGINAL encrypted GitHub Release assets.

This validates remote archive identities only. It never downloads ciphertext,
reads account values, decrypts, collects from a broker, or evaluates a strategy.
Release/manifest are pinned to immutable historical source repository/version.
"""
import datetime as dt
import hashlib
import json
import os
import urllib.request
from pathlib import Path

SOURCE = "mariancradulescu/mxm-quant-greenfield"
COMMIT = "0e5349115de72f9824986acb00cdb410a3097dcf"
PATH = "research_core_v4/state/BREADTH_FIRST_SHALLOW_M5_SUPPORT_V2_FINAL_DURABLE_MANIFEST_V1.json"
TAG = "mxm-shallow-m5-v2-v4-ac8322bd8e44786c3f6e1c5707079bc7eaa370c8db44f9053b9b84dfac3a2ce0"

def load(url):
    headers={
        "User-Agent":"MXM-Quant-ReadOnly-Archive-Identity/1.0",
        "Accept":"application/vnd.github+json"}
    # Public GitHub release metadata uses the native ephemeral, read-only
    # Actions token to avoid anonymous REST rate limits. The token never
    # reaches raw.githubusercontent.com and is never logged or published.
    temporary=os.environ.get("MXM_GITHUB_METADATA_READ_TOKEN","")
    if url.startswith("https://api.github.com/") and temporary:
        headers["Authorization"]="Bearer "+temporary
    req = urllib.request.Request(url,headers=headers)
    with urllib.request.urlopen(req, timeout=45) as response:
        data=response.read(3_000_001)
    if len(data)>3_000_000:
        raise ValueError("REMOTE_METADATA_TOO_LARGE")
    return data

def validate(manifest, release, manifest_bytes):
    if (manifest.get("schema")!="mxm.v4.shallow-m5-v2.final-durable-manifest.v2"
        or manifest.get("status")!="COMPLETE"
        or manifest.get("DURABLE_RELEASE_IDENTITY")!=TAG
        or manifest.get("PROTECTED_FORWARD_ROW_COUNT")!=0):
        raise ValueError("FROZEN_SOURCE_CONTRACT_MISMATCH")
    entries=manifest.get("entries")
    if not isinstance(entries,list) or len(entries)!=100 or (
        sum(int(e["ROW_COUNT"]) for e in entries)!=3_355_389):
        raise ValueError("ORIGINAL_SOURCE_MANIFEST_INCOMPLETE")
    if release.get("tag_name")!=TAG or (
        release.get("target_commitish")!=manifest["ARM_COMMIT"]):
        raise ValueError("RELEASE_BINDING_MISMATCH")
    assets=release.get("assets",[])
    if len(assets)!=100:
        raise ValueError("REMOTE_ASSET_COUNT_MISMATCH")
    indexed={a["name"]:a for a in assets}
    if len(indexed)!=100:
        raise ValueError("DUPLICATE_REMOTE_ASSET")
    names=set()
    for e in entries:
        name=e["ENCRYPTED_ASSET_NAME"]
        if name in names or len(e["ENCRYPTED_ASSET_SHA256"])!=64:
            raise ValueError("ORIGINAL_MANIFEST_IDENTITY_INVALID")
        names.add(name)
        asset=indexed.get(name)
        if asset is None or asset.get("state")!="uploaded" or (
            asset.get("digest")!="sha256:"+e["ENCRYPTED_ASSET_SHA256"]):
            raise ValueError("ORIGINAL_CIPHERTEXT_IDENTITY_NOT_VERIFIED")
    first=min(e["FIRST_TIMESTAMP"] for e in entries)
    last=max(e["LAST_TIMESTAMP"] for e in entries)
    return {
        "schema":"mxm.legacy-authentic-encrypted-source-admission.v1",
        "status":"ENCRYPTED_SOURCE_IDENTITIES_VERIFIED_NOT_DECRYPTED",
        "source_commit":COMMIT,
        "manifest_sha256":hashlib.sha256(manifest_bytes).hexdigest(),
        "original_cipher_asset_count_verified":100,
        "original_manifest_row_count":3_355_389,
        "earliest_public_coverage":first,
        "latest_public_coverage":last,
        "broker_requests":0,
        "original_shards_decrypted_in_this_run":0,
        "economic_replays_in_this_run":0,
        "net_edge_proven":False,
        "hard21_proven":False,
        "twelve_calendar_months_proven":False,
        "trading_orders_submitted":0,
    }

def main():
    raw=load(f"https://raw.githubusercontent.com/{SOURCE}/{COMMIT}/{PATH}")
    manifest=json.loads(raw)
    release=json.loads(load(f"https://api.github.com/repos/{SOURCE}/releases/tags/{TAG}"))
    receipt=validate(manifest,release,raw)
    Path("legacy-archive-public-receipt.json").write_text(
        json.dumps(receipt,sort_keys=True,indent=2)+"\n")
    # Sanitized summary only. No source rows, ciphertext or account fingerprint.
    print(receipt["status"], "ASSETS",receipt["original_cipher_asset_count_verified"],
          "ROWS",receipt["original_manifest_row_count"],
          "12_MONTHS_PROVEN",receipt["twelve_calendar_months_proven"])

if __name__=="__main__":
    main()

"""Safe ZIP-level original/receipt integrity preflight before durable encrypted backup.

No private key is used. Original sealed bytes remain encrypted. This script does
not upload anything; storage requires separate explicitly gated OWNER workflow.
"""
import hashlib
import json
import os
import zipfile
from pathlib import Path

from .decode import need
from .funded_history_economic_development import (
    SOURCE_RECEIPT_SHA256, RECOVERY_RECEIPT_SHA256, MANIFEST_SHA256, GAP_SHA256,
)

ARCHIVES = {
    "original-encrypted.zip": ("5f6b232d2e8b892da3e9488399f65c72fe1bb2ff8c908dfff3e9f2661d81dec8", 869032678),
    "original-public.zip": ("06c0181ba732c8fcf70ffe554d532522daa2e5af6e83336baad665028aeae5ed", 51143),
    "recovery-public.zip": ("de2b998117180e9e364be5d9e7d81851449db4ab0a8dc8dee3e94244fa885f64", 230148),
}


def file_digest(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def verify_archives(root):
    root = Path(root)
    verified = {}
    for filename, (expected, size) in ARCHIVES.items():
        path = root / filename
        need(path.stat().st_size == size and file_digest(path) == expected,
             "DURABLE_ARCHIVE_ORIGINAL_ZIP_SHA256")
        verified[filename] = {"Sha256": expected, "Bytes": size}
    with zipfile.ZipFile(root / "original-public.zip") as z:
        need(z.namelist() == ["source.json"], "DURABLE_ARCHIVE_ORIGINAL_PUBLIC_ZIP")
        source_bytes = z.read("source.json")
    need(hashlib.sha256(source_bytes).hexdigest() == SOURCE_RECEIPT_SHA256,
         "DURABLE_ARCHIVE_ORIGINAL_SOURCE_HASH")
    original = json.loads(source_bytes)
    need(original["Status"] == "SOURCE_FAILED_CLOSED" and
         original["RunId"] == "44824462289" and original["Requests"] == 30473
         and len(original["Shards"]) == 606,
         "DURABLE_ARCHIVE_ORIGINAL_IDENTITY")
    with zipfile.ZipFile(root / "original-encrypted.zip") as z:
        names = z.namelist()
        meta = {v["File"]: v["CipherSha256"] for v in original["Shards"]}
        need(len(names) == len(set(names)) == len(meta) and set(names) == set(meta),
             "DURABLE_ARCHIVE_ENCRYPTED_MEMBER_INVENTORY")
        for name in names:
            with z.open(name) as f:
                need(hashlib.file_digest(f, "sha256").hexdigest() == meta[name],
                     "DURABLE_ARCHIVE_ENCRYPTED_MEMBER_HASH")
    with zipfile.ZipFile(root / "recovery-public.zip") as z:
        need(set(z.namelist()) == {"recovery-receipt.json", "coverage-manifest.json",
                                  "gap-requests.json"}, "DURABLE_ARCHIVE_RECOVERY_MEMBERS")
        rec = z.read("recovery-receipt.json")
        coverage = z.read("coverage-manifest.json")
        gap = z.read("gap-requests.json")
    need((hashlib.sha256(rec).hexdigest(), hashlib.sha256(coverage).hexdigest(),
          hashlib.sha256(gap).hexdigest()) ==
         (RECOVERY_RECEIPT_SHA256, MANIFEST_SHA256, GAP_SHA256),
         "DURABLE_ARCHIVE_RECOVERY_SHA256")
    recovery = json.loads(rec)
    need(recovery["Status"] == "CUSTODY_VERIFIED_PARTIAL_SOURCE" and
         recovery["RecoveryRun"] == "44910122403" and
         recovery["OriginalRun"] == original["RunId"] and
         recovery["SourceReceiptSha256"] == SOURCE_RECEIPT_SHA256 and
         recovery["OriginalShardsVerified"] == 606 and
         recovery["OriginalRequestsVerified"] == 30473,
         "DURABLE_ARCHIVE_CUSTODY_PROVENANCE")
    return {"Status": "THREE_ENCRYPTED_OR_SAFE_ZIPS_SHA256_VERIFIED",
            "OriginalRun": "44824462289", "RecoveryRun": "44910122403",
            "ArchiveInventory": verified, "OriginalShardsVerified": 606,
            "ArchivedPrivateKey": False, "UnsealedOriginalData": False,
            "OrdersSubmitted": 0, "CloudActivated": False}


def main():
    root = Path(os.environ.get("MXM_ARCHIVE_ROOT", "encrypted-archive-zip"))
    result = verify_archives(root)
    Path("durable-archive-public").mkdir(exist_ok=True)
    (Path("durable-archive-public") / "integrity.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    print("DURABLE_ARCHIVE_ENCRYPTED_ZIP_INTEGRITY_VERIFIED", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("DURABLE_ARCHIVE_VERIFICATION_FAILED_CLOSED", flush=True)
        raise SystemExit(1) from None

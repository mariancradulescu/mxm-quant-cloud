"""Offline verification of strong archive ZIP + original ciphertext inventory contract."""
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from . import funded_history_archive_verify as a
from .guard import CaptureContractError


def digest(data):
    return hashlib.sha256(data).hexdigest()


class DurableArchiveTests(unittest.TestCase):
    def fixture(self, root):
        contents = {}
        members = {}
        for n in range(606):
            name = f"slice-{n:04d}.enc"
            raw = f"SEALED_ONLY_{n}".encode()
            members[name] = raw
        source = {
            "Status": "SOURCE_FAILED_CLOSED", "RunId": "44824462289",
            "Requests": 30473,
            "Shards": [{"File": name, "CipherSha256": digest(raw)}
                       for name, raw in members.items()],
        }
        source_bytes = (json.dumps(source) + "\n").encode()
        recovered = {"Status": "CUSTODY_VERIFIED_PARTIAL_SOURCE", "RecoveryRun": "44910122403",
                     "OriginalRun": "44824462289", "SourceReceiptSha256": digest(source_bytes),
                     "OriginalShardsVerified": 606, "OriginalRequestsVerified": 30473}
        recovery_bytes = (json.dumps(recovered) + "\n").encode()
        coverage, gap = b'{"markets":"test only"}\n', b'{"gap":"fixture"}\n'
        for filename, parts in (
            ("original-encrypted.zip", members),
            ("original-public.zip", {"source.json": source_bytes}),
            ("recovery-public.zip", {"recovery-receipt.json": recovery_bytes,
                                     "coverage-manifest.json": coverage, "gap-requests.json": gap}),
        ):
            with zipfile.ZipFile(Path(root) / filename, "w", compression=zipfile.ZIP_STORED) as z:
                for name, data in parts.items():
                    z.writestr(name, data)
        archives = {n: (a.file_digest(Path(root) / n), (Path(root) / n).stat().st_size)
                    for n in a.ARCHIVES}
        return archives, digest(source_bytes), digest(recovery_bytes), digest(coverage), digest(gap)

    def test_valid_all_606_encrypted_members_without_opening_private_contents(self):
        with tempfile.TemporaryDirectory() as d:
            archives, source, rec, cov, gap = self.fixture(d)
            with patch.object(a, "ARCHIVES", archives), patch.object(a, "SOURCE_RECEIPT_SHA256", source), \
                 patch.object(a, "RECOVERY_RECEIPT_SHA256", rec), patch.object(a, "MANIFEST_SHA256", cov), \
                 patch.object(a, "GAP_SHA256", gap):
                status = a.verify_archives(d)
            self.assertEqual(status["OriginalShardsVerified"], 606)
            self.assertFalse(status["ArchivedPrivateKey"])
            self.assertFalse(status["UnsealedOriginalData"])

    def test_zip_mutation_fails_before_any_copy(self):
        with tempfile.TemporaryDirectory() as d:
            archives, source, rec, cov, gap = self.fixture(d)
            with (Path(d) / "original-encrypted.zip").open("ab") as file:
                file.write(b"tampering")
            with patch.object(a, "ARCHIVES", archives):
                with self.assertRaisesRegex(CaptureContractError, "DURABLE_ARCHIVE_ORIGINAL_ZIP_SHA256"):
                    a.verify_archives(d)


if __name__ == "__main__":
    unittest.main()

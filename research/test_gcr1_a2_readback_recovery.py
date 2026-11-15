"""GCR1 F1 strict formatting-only readback recovery, synthetic no broker."""
import json
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from research.gcr1_reused_source_readback import (
    GCR_SOURCE_RUN, source_public_receipt,
)


class GCR1OriginalReceiptRecoveryTests(unittest.TestCase):
    def test_original_and_new_run_ids_are_not_conflated(self):
        self.assertEqual(GCR_SOURCE_RUN, "43723906148")

    def test_trailing_exact_two_byte_escape_only(self):
        receipt={"schema":"MXM_GCR1_A2_SOURCE_ONLY_NO_FINANCIAL_SCORING",
                 "originalRunId": int(GCR_SOURCE_RUN),
                 "sourceEncryptedBeforeAllGCR1OutcomeScoring": True,
                 "conditionalNetEur": None, "ordersSubmitted": 0}
        malformed = json.dumps(receipt, indent=2, allow_nan=False).encode() + b"\\n"
        with TemporaryDirectory() as d:
            p=Path(d)/"original.json"
            p.write_bytes(malformed)
            recovered,audit=source_public_receipt(p)
            self.assertEqual(recovered,receipt)
            self.assertEqual(audit["originalPublicMetadataSha256"],sha256(malformed).hexdigest())
            self.assertEqual(audit["formatRecovery"],"EXACT_TRAILING_BACKSLASH_N_ONLY_ORIGINAL_PRESERVED")
            self.assertEqual(p.read_bytes(),malformed)

    def test_reject_unknown_original_trailing_mutation(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"original.json"
            p.write_bytes(b'{"x":1}XYZ')
            with self.assertRaises(ValueError):
                source_public_receipt(p)
            p.write_bytes(b'{"x":1}\n\\n')
            with self.assertRaises(ValueError):
                source_public_receipt(p)

    def test_valid_newline_requires_no_recovery(self):
        with TemporaryDirectory() as d:
            p=Path(d)/"original.json"
            p.write_bytes(b'{"x":1}\n')
            data,audit=source_public_receipt(p)
            self.assertEqual(data,{"x":1})
            self.assertEqual(audit["formatRecovery"],"NONE")


if __name__ == "__main__":
    unittest.main()

"""Correct monetary attribution from the existing EURJPY parity ciphertext."""
from hashlib import sha256
import json
import os
from pathlib import Path

from .custody import unseal_new
from .eurjpy_quote_parity import evaluate, need

RUN = "43440166826"
CIPHER = "46cda823d1fe7ddee5a69f5988fca59998a12e514928ff8a84ea05d3ea0ac619"
PLAIN = "cd3cf6145c5c91e29329fddebf65c638e81b36c6e3892755b871881e284a6b48"
RECEIPT = "8bd1cafe0527d733f53ee29dcebb06a229e81aa92da55c8c222d6ff00a304603"


def main():
    cipher = Path("original-parity/eurjpy-quote-parity-source.v2.enc").read_bytes()
    public = Path("original-parity-public/eurjpy-quote-parity-public.json").read_bytes()
    need(sha256(cipher).hexdigest() == CIPHER and sha256(public).hexdigest() == RECEIPT,
         "ORIGINAL_ARTIFACT_DIGEST_MISMATCH")
    raw = unseal_new(cipher, os.environ.pop("R3_CUSTODY_PRIVATE_KEY_PEM").encode(), RUN)
    need(sha256(raw).hexdigest() == PLAIN, "ORIGINAL_PLAINTEXT_DIGEST_MISMATCH")
    original = json.loads(public)
    tape = json.loads(raw)
    need(tape["SourceLabel"] == "ORIGINAL_PEPPERSTONE_EURJPY_QUOTE_PARITY"
         and original["source_cipher_sha256"] == CIPHER
         and original["source_plain_sha256"] == PLAIN, "ORIGINAL_SOURCE_MISMATCH")
    result = evaluate(tape)
    count_fields = ("scheduled", "missing_decision", "intents", "missing_path", "priced", "long_intents")
    need(result["counts"] == original["counts"] and len(result["weekly"]) == len(original["weekly"])
         and all(all(a[k] == b[k] for k in count_fields)
                 for a, b in zip(result["weekly"], original["weekly"])), "SIGNAL_COVERAGE_CHANGED")
    result.update({k: v for k, v in original.items() if k not in result})
    result.update(classification="EXPOSED_CONDITIONAL_EUR_SINGLE_LEG_CORRECTED_JPY_ROUTE",
                  correction_run=int(os.environ["GITHUB_RUN_ID"]), new_read_only_requests=0,
                  original_receipt_sha256=RECEIPT, original_receipt_artifact=14044329005,
                  original_cipher_artifact=14044698526)
    Path("eurjpy-parity-corrected.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()

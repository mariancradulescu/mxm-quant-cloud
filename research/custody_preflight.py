"""Check the EXISTING custody recipient without collecting account data."""
import os
import sys
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .custody import seal, unseal

def verify(private_pem, public_pem):
    if not private_pem.strip():
        return "CUSTODY_CONFIGURATION_MISSING"
    try:
        key = serialization.load_pem_private_key(private_pem, password=None)
    except Exception:
        return "CUSTODY_PEM_INVALID_OR_ENCRYPTED"
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        return "CUSTODY_KEY_TYPE_INVALID"
    expected = serialization.load_pem_public_key(public_pem)
    if key.public_key().public_numbers() != expected.public_numbers():
        return "CUSTODY_EXISTING_RECIPIENT_MISMATCH"
    challenge = os.urandom(32)
    if unseal(seal(challenge, public_pem), private_pem) != challenge:
        return "CUSTODY_CHALLENGE_FAILED"
    return "EXISTING_CUSTODY_KEY_VERIFIED_NOT_SOURCE_READBACK"

def main():
    try:
        status = verify(os.environ.get('R3_CUSTODY_PRIVATE_KEY_PEM', '').encode(),
                        Path(__file__).with_name('custody_public.pem').read_bytes())
    except Exception:
        status = "CUSTODY_PREFLIGHT_FAILED_DETAIL_WITHHELD"
    print(status, flush=True)
    return 0 if status == "EXISTING_CUSTODY_KEY_VERIFIED_NOT_SOURCE_READBACK" else 1

if __name__ == '__main__':
    sys.exit(main())

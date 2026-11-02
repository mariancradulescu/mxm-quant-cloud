"""Derive a NEW SOURCE recipient from the EXISTING installed private key.

No new RSA identity, credentials, or historical-custody recipient changes.
Only public SPKI and a run-bound fingerprint may leave the protected job.
"""
import hashlib
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from .custody import seal_new, unseal_new

PUBLIC = "new-source-recipient.public.pem"
RECEIPT = "new-source-recipient.public.json"

def _run_id():
    value=os.environ.get("GITHUB_RUN_ID", "")
    if not value.isdigit() or int(value) <= 0:
        raise ValueError("NEW_CUSTODY_RUN_BINDING_MISSING")
    return value

def derive_recipient(private_pem: bytes):
    try:
        key=serialization.load_pem_private_key(private_pem,password=None)
    except Exception as exc:
        raise ValueError("NEW_CUSTODY_INSTALLED_PRIVATE_INVALID") from exc
    if not isinstance(key,rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("NEW_CUSTODY_INSTALLED_PRIVATE_NOT_RSA2048")
    public=key.public_key().public_bytes(serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    spki=key.public_key().public_bytes(serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    challenge=b"MXM-NEW-SOURCE-RECIPIENT-INSTALLED-KEY-CHALLENGE-v2"
    if unseal_new(seal_new(challenge,public,"1"),private_pem,"1") != challenge:
        raise ValueError("NEW_CUSTODY_PRIVATE_PUBLIC_CHALLENGE_FAILED")
    return public,hashlib.sha256(spki).hexdigest()

def emit_public(private_pem:bytes, dest:Path, run_id:str):
    if not run_id.isdigit() or int(run_id)<=0:
        raise ValueError("NEW_CUSTODY_RUN_BINDING_MISSING")
    public,fingerprint=derive_recipient(private_pem)
    dest.mkdir(parents=True,exist_ok=True)
    (dest/PUBLIC).write_bytes(public)
    (dest/RECEIPT).write_text(json.dumps({
        "schema":"mxm.new-source-recipient.v2",
        "workflow_run_id":run_id,
        "rsa_public_spki_sha256":fingerprint,
        "recipient_origin":"PUBLIC_DERIVED_FROM_EXISTING_INSTALLED_CUSTODY_PRIVATE",
        "historical_recipient_modified":False,
        "new_rsa_keypair_generated":False,
        "trading_authority":False,
    },sort_keys=True)+"\n")
    return fingerprint

def checked_public(directory:Path,run_id:str):
    receipt=json.loads((directory/RECEIPT).read_text())
    if receipt.get("schema")!="mxm.new-source-recipient.v2" or (
        receipt.get("workflow_run_id")!=run_id):
        raise ValueError("NEW_CUSTODY_RECIPIENT_RUN_MISMATCH")
    public=(directory/PUBLIC).read_bytes()
    key=serialization.load_pem_public_key(public)
    if not isinstance(key,rsa.RSAPublicKey) or key.key_size<2048:
        raise ValueError("NEW_CUSTODY_RECIPIENT_INVALID")
    spki=key.public_bytes(serialization.Encoding.DER,
        serialization.PublicFormat.SubjectPublicKeyInfo)
    if hashlib.sha256(spki).hexdigest()!=receipt.get("rsa_public_spki_sha256"):
        raise ValueError("NEW_CUSTODY_RECIPIENT_HASH_MISMATCH")
    return public

def main():
    try:
        secret=os.environ.get("R3_CUSTODY_PRIVATE_KEY_PEM","").encode()
        if not secret.strip():
            raise ValueError("NEW_CUSTODY_PRIVATE_MISSING")
        emit_public(secret,Path("new-recipient-output"),_run_id())
        print("NEW_SOURCE_RECIPIENT_DERIVED_FROM_INSTALLED_RSA_KEY",flush=True)
    except Exception:
        # No private PEM or exception detail ever logged.
        print("NEW_SOURCE_CUSTODY_PREFLIGHT_FAILED_DETAIL_WITHHELD",flush=True)
        raise SystemExit(1)

if __name__=="__main__":
    main()

"""New versioned envelope, existing RSA recipient; no new identity/keypair."""
import base64
import hashlib
import json
import os
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AAD = b"MXM-CUSTODY-AESGCM-RSAOAEP-v1"

def seal(plaintext, public_pem):
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 2048:
        raise ValueError("CUSTODY_KEY_INVALID")
    spki = key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    session = os.urandom(32)
    nonce = os.urandom(12)
    wrapped = key.encrypt(session, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    cipher = AESGCM(session).encrypt(nonce, plaintext, AAD)
    b64 = lambda x: base64.b64encode(x).decode("ascii")
    return json.dumps(dict(version=1, recipient=hashlib.sha256(spki).hexdigest(), wrapped=b64(wrapped), nonce=b64(nonce), ciphertext=b64(cipher)), sort_keys=True).encode()

def unseal(envelope, private_pem):
    data = json.loads(envelope)
    if data["version"] != 1:
        raise ValueError("CUSTODY_VERSION")
    key = serialization.load_pem_private_key(private_pem, password=None)
    spki = key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    if hashlib.sha256(spki).hexdigest() != data["recipient"]:
        raise ValueError("CUSTODY_RECIPIENT_MISMATCH")
    b64 = lambda x: base64.b64decode(x, validate=True)
    session = key.decrypt(b64(data["wrapped"]), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return AESGCM(session).decrypt(b64(data["nonce"]), b64(data["ciphertext"]), AAD)

# Independent NEW-SOURCE recipient namespace. Existing v1 envelopes are unchanged
# and cannot be relabelled as v2. Bind the run ID in authenticated AES-GCM AAD.
NEW_AAD = b"MXM-NEW-SOURCE-RSA-OAEP-AES-GCM-v2:"

def _checked_run(run_id):
    if not isinstance(run_id, str) or not run_id.isdecimal() or int(run_id) <= 0:
        raise ValueError("CUSTODY_NEW_RUN_INVALID")
    return run_id

def seal_new(plaintext, public_pem, run_id):
    run_id = _checked_run(run_id)
    key = serialization.load_pem_public_key(public_pem)
    if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 2048:
        raise ValueError("CUSTODY_NEW_RECIPIENT_INVALID")
    spki = key.public_bytes(serialization.Encoding.DER,
                            serialization.PublicFormat.SubjectPublicKeyInfo)
    session, nonce = os.urandom(32), os.urandom(12)
    wrapped = key.encrypt(session, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()),
                             algorithm=hashes.SHA256(),label=None))
    encrypted = AESGCM(session).encrypt(nonce, plaintext, NEW_AAD + run_id.encode("ascii"))
    b64 = lambda x: base64.b64encode(x).decode("ascii")
    return json.dumps({
        "version": 2,
        "namespace": "MXM_NEW_PEPPERSTONE_READ_ONLY_SOURCE",
        "workflowRunId": run_id,
        "recipient": hashlib.sha256(spki).hexdigest(),
        "wrapped": b64(wrapped),
        "nonce": b64(nonce),
        "ciphertext": b64(encrypted),
    }, sort_keys=True).encode("ascii")

def unseal_new(envelope, private_pem, run_id):
    run_id = _checked_run(run_id)
    data = json.loads(envelope)
    if data.get("version") != 2 or data.get("namespace") != "MXM_NEW_PEPPERSTONE_READ_ONLY_SOURCE":
        raise ValueError("CUSTODY_NEW_ENVELOPE_DOMAIN_INVALID")
    if data.get("workflowRunId") != run_id:
        raise ValueError("CUSTODY_NEW_CROSS_RUN_REPLAY_BLOCKED")
    key = serialization.load_pem_private_key(private_pem, password=None)
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size < 2048:
        raise ValueError("CUSTODY_NEW_PRIVATE_KEY_INVALID")
    spki = key.public_key().public_bytes(serialization.Encoding.DER,
                                         serialization.PublicFormat.SubjectPublicKeyInfo)
    if data.get("recipient") != hashlib.sha256(spki).hexdigest():
        raise ValueError("CUSTODY_NEW_RECIPIENT_MISMATCH")
    b64 = lambda x: base64.b64decode(x, validate=True)
    session = key.decrypt(b64(data["wrapped"]),padding.OAEP(
        mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(),label=None))
    return AESGCM(session).decrypt(b64(data["nonce"]),b64(data["ciphertext"]),
                                  NEW_AAD + run_id.encode("ascii"))

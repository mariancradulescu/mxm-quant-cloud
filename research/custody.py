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

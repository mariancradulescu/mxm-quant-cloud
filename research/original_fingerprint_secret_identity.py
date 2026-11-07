"""OWNER one-shot check: does the *misnamed* protected secret match pinned account identity?

No OAuth/broker calls. No secret content, size, prefix, raw hash or comparison
digest is printed or recorded. A mismatch is UNKNOWN TYPE, not a refresh proof.
Only the original public historic double-SHA256 commitment is used; never
construct a new account binding, change a credential, or authenticate an account.
"""
from __future__ import annotations
import hashlib
import hmac
import json
import os
from pathlib import Path
from .collect import HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT, normalize_binding

NAME="R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256"
# Intentionally not a collector/authentication environment variable.
AUDIT_ONLY_ENV_NAME="MXM_SUSPECT_FINGERPRINT_AUDIT_ONLY"
RESULT_MATCH="MATCHES_ORIGINAL_HISTORIC_ACCOUNT_FINGERPRINT"
RESULT_UNKNOWN="DOES_NOT_MATCH_ORIGINAL_FINGERPRINT_VALUE_TYPE_UNKNOWN"
RESULT_UNAVAILABLE="NOT_AVAILABLE_OR_EMPTY_IN_PROTECTED_ENVIRONMENT"
SCHEMA="MXM_OWNER_ORIGINAL_FINGERPRINT_SECRET_IDENTITY_ONLY_V1"

def compare_secret_to_original(secret: str | None, *,
                               commitment: str = HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT):
    """Use only in-memory cryptographic comparison; never emit source/digest."""
    if not secret:
        return RESULT_UNAVAILABLE
    try:
        normalized=normalize_binding(secret)
        digest=hashlib.sha256(normalized.encode("ascii")).hexdigest()
        if hmac.compare_digest(digest, commitment):
            return RESULT_MATCH
    except Exception:
        # Deliberately discard malformed-value details, including lengths.
        pass
    return RESULT_UNKNOWN

def sanitized_receipt(environ):
    code=compare_secret_to_original(environ.get(AUDIT_ONLY_ENV_NAME))
    return {
        "schema":SCHEMA,
        "environment":"mxm-r3-pepperstone-v1",
        "inspectedSecretName":NAME,
        "identityComparison":code,
        "isOriginalFingerprintConfirmed":code==RESULT_MATCH,
        "unknownValueMayBeRefreshTokenButNotProven":code==RESULT_UNKNOWN,
        "matchesOriginalIdentityInCurrentReadOnlyCode":True,
        "originalAccountIdentityModified":False,
        "githubMetadataInspected":False,
        "refreshTokenValidityTested":False,
        "secretValueOrLengthOrPrefixOrHashDisclosed":False,
        "accessTokenValidityTested":False,
        "brokerRequests":0,
        "refreshedOrRotatedAnyToken":False,
        "updatedAnyGitHubSecret":False,
        "openedOriginalAccount":False,
        "researchDataCollected":False,
        "ordersSubmitted":0,
        "cloudActivated":False
    }

def main():
    output=sanitized_receipt(os.environ)
    Path("original-fingerprint-secret-identity.public.json").write_text(
        json.dumps(output,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    # Only a static receipt-written flag; result is in a sanitized artifact.
    print("ORIGINAL_FINGERPRINT_SECRET_CHECK_COMPLETED_REDACTED",flush=True)

if __name__=="__main__":
    main()

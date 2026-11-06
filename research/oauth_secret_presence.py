"""One-shot, protected, *presence only* audit of pre-existing OAuth environment secrets.

This reads NO secret metadata from GitHub and NEVER logs a value, length,
hash, prefix, expiration, issuer or token. The only observable property is
whether GitHub Actions injected a non-empty value for each fixed name.
No Spotware request, no refresh, no GitHub secret writes.
"""
import json
import os
from pathlib import Path

SECRET_NAMES=(
    "R3_CTRADER_CLIENT_ID",
    "R3_CTRADER_CLIENT_SECRET",
    "R3_CTRADER_ACCESS_TOKEN",
    "R3_CTRADER_REFRESH_TOKEN",
)
ENVIRONMENT="mxm-r3-pepperstone-v1"

def presence_only(environ):
    status={name:("AVAILABLE_IN_PROTECTED_JOB" if bool(environ.get(name))
                  else "NOT_AVAILABLE_OR_EMPTY_IN_PROTECTED_JOB")
            for name in SECRET_NAMES}
    return {
        "schema":"MXM_ORIGINAL_OAUTH_SECRET_PRESENCE_ONLY_V1",
        "environment":ENVIRONMENT,
        "valuesBySecretName":status,
        "allFourAvailable":all(x=="AVAILABLE_IN_PROTECTED_JOB" for x in status.values()),
        "readGitHubSecretMetadata":False,
        "missingMeansProvenAbsentFromGitHub":False,
        "validityOfAnyCredentialTested":False,
        "scopeTested":False,
        "originalAccountReauthenticated":False,
        "secretValuesOrLengthsOrFingerprintsEmitted":False,
        "refreshTokenConsumed":False,
        "tokenRotationPerformed":False,
        "durablePairWritten":False,
        "brokerCalls":0,
        "liveOrDemoOrders":0,
        "cloudActivated":False,
    }

def main():
    result=presence_only(os.environ)
    Path("oauth-secret-presence.public.json").write_text(
        json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    # Only the two boolean-level result classes; never print environ.
    print("ORIGINAL_OAUTH_SECRET_PRESENCE_ONLY_WRITTEN",flush=True)

if __name__=="__main__":
    main()

# OWNER v2.0 — isolated check of possibly misnamed account fingerprint secret

This is a bounded correction to the original four-secret configuration. It does not reopen GEP1 or BCF1, change the Pepperstone account identity, switch app/scope/broker, reset EUR300, score source research, activate Cloud, or send orders.

## Reconciliation

GitHub main before this change: `fae328322e5baeb0e6203111474b37a5c07bd3ac` (PR #114–#116 received and CI passed, zero open PR). Authentic original environment presence job [#42246587372](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42246587372) confirmed nonempty injections for `R3_CTRADER_CLIENT_ID`, `R3_CTRADER_CLIENT_SECRET`, and `R3_CTRADER_ACCESS_TOKEN`, but **not** `R3_CTRADER_REFRESH_TOKEN` under that name. OWNER directly inspected the environment and reported that the fourth named secret actually is `R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256`, which could contain a mistakenly named original refresh token. These facts are consistent; no token value/validity has been proved.

## Original account identity and why this check is non-destructive

Historical frozen `research/collect.py` uses `HISTORIC_ACCOUNT_FINGERPRINT_COMMITMENT` and derives each listed cTrader account's candidate fingerprint as SHA256(`ctrader-account:<original internal account id>`). It compares SHA256(candidate fingerprint ASCII) with the pinned commitment. This is the **exact original LIVE account identity** and never depends on `R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256` supplied through current GitHub Environment. The original account id, historic commitment and byte-for-byte frozen source file remain unchanged.

The protected read-only file `research/original_fingerprint_secret_identity.py` loads **only** `R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256` inside original environment `mxm-r3-pepperstone-v1`. It applies the existing strict fingerprint normalization **in memory** and compares SHA256(normalized text) to the existing pinned commitment with constant-time `hmac.compare_digest`. It emits only one of these fixed categories:

- `MATCHES_ORIGINAL_HISTORIC_ACCOUNT_FINGERPRINT`: the stored value is the correct original fingerprint; **not** evidence that any OAuth refresh exists.
- `DOES_NOT_MATCH_ORIGINAL_FINGERPRINT_VALUE_TYPE_UNKNOWN`: the stored value is **not** the required original fingerprint, and its type is unknown; it *may* be the old refresh token but is **NOT** confirmed, validated, consumed or rotated.
- `NOT_AVAILABLE_OR_EMPTY_IN_PROTECTED_ENVIRONMENT`: the secret was not injected or was empty (not proof of GitHub metadata absence).

There is NO disclosure of secret value, length, prefix, hash/digest, comparison intermediary, error exception string or account number. Only public categories and Boolean safety conditions are uploaded. No REST/TLS/Spotware requests are possible from this script, and the workflow job has repository contents **read-only**. No secret changes, refresh consumption or extra data collection.

## Recovery boundary and minimal secure route

Official Spotware [OAuth](https://help.ctrader.com/open-api/account-authentication/) permits original refresh token exchange for a **new access+refresh pair**, invalidating the previous pair. Merely having a secret under another name and failing a fingerprint comparison does **not** prove that it contains a valid or correctly scoped refresh token. Never call the refresh endpoint or `ProtoOARefreshTokenReq` from this job.

GitHub [Environment secret updates](https://docs.github.com/en/rest/actions/secrets) require an authorized environment-secrets write route and encryption via the environment public key; the connected GitHub actions do not expose such a write. Current workflows' `GITHUB_TOKEN` has repository `contents: read`, not an available environment-secrets writer, and two secret updates are not a transaction. No known secure and durable autonomous installation of both new tokens exists. Therefore do **not** rotate the suspect token until the complete securely persistent pair-update operation is proven.

After a mismatch, the minimal safe next OWNER action, if needed, is **not** creating a new app or obtaining a new token. Instead: keep all existing secrets intact; if OWNER still possesses the original refresh token outside GitHub, they may place that same value in a correctly named secret in the existing environment via GitHub's protected UI, without deleting the misnamed one. This does NOT by itself make token rotation safe or prove its validity. Because GitHub secret values cannot be read back through the connected GitHub tool, a misnamed value cannot simply be copied between secret names by the Director. A separate **authorized** secure mechanism for persisting both rotated values remains necessary before any consumption. Do not ask OWNER to paste any values into chat.

The exposed 52 historical weeks remain non-independent, BCF1 remains `SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS`; no funded EUR300 NET or system HARD21 or 30% equity DD compliance is demonstrated. Trading and Cloud stay disabled.

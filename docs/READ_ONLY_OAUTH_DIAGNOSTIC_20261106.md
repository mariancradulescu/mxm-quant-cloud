# Read-only Pepperstone OAuth diagnosis — OWNER v2.0, 2026-11-06

This is an operational continuation, not a new research framework, economic strategy or authority. The single capital account, native C# finance, closed GEP1/BCF1 protocols and all data-holdout decisions remain unchanged.

## Reconciled source and offline root-cause boundary

At GitHub main `0e3cc345f30c19791c0b3cdff14018472e72619c`, Actions #42173332160 = SUCCESS. BCF1 #42172375939 attempts 1–2 each reached `APPLICATION_AUTH_VERIFIED` but did not reach `ACCESS_TOKEN_EXPLICIT_VIEW_VERIFIED`. Existing `research/collect.py` used to label **any unexpected protobuf response type** as `TOKEN_INVALID_OR_EXPIRED`, which is an ambiguous internal assertion and **not** a broker confirmation. Application auth success proves only the current client application handshake.

Official Spotware Open API [auth guide](https://help.ctrader.com/open-api/account-authentication/) and [error handling](https://help.ctrader.com/open-api/error-handling/) distinguish `ProtoOAApplicationAuthReq`, `ProtoOAGetAccountListByAccessTokenReq`, and `ProtoOAAccountAuthReq`, with broker `ProtoOAErrorRes.errorCode` and `ProtoErrorRes.errorCode`. `GetAccountListByAccessTokenRes.permissionScope` is **optional** and must be present and exactly `SCOPE_VIEW` (never `SCOPE_TRADE`). The original account is the single LIVE match against the historic double-SHA256 commitment; no new account discovery or fallback. The error's description and original protobuf replies may contain sensitive data and cannot be disclosed.

Corrected `collect.authenticate` retains strict SCOPE_VIEW and fixed identity. Unexpected response types now receive **only documented exact error classifications**, or `AUTH_CAUSE_UNDETERMINED`; a missing/wrong permission stays `SCOPE_NOT_EXPLICIT_VIEW`. Transport/timeout is not mislabeled token expiry. No source data requests follow an unsuccessful auth gate.

One extremely narrow `research/auth_scope_diagnostic.py` reuses existing TLS, protobuf and allowlist: maximum 3 messages (application, token-listed accounts, original-account authorization), no trader contract, candles, BID/ASK, positions, broker cash, token refresh or orders. It outputs exactly a fixed category, stage and boolean success flags; **never** token, refresh value, account ID, protobuf, error description or unexpected error string. The one-shot job is gated by an exact OWNER/main single-file commit and isolated `mxm-r3-pepperstone-v1`. Registering this implementation does **not** trigger it; an independently checked one-shot intent merge triggers it once.

## Safe error categories

- `AUTH_TOKEN_INVALID_OR_EXPIRED_EXPLICIT` — only when the broker actually returns a recognized explicit token error, e.g. `OA_AUTH_TOKEN_EXPIRED`; no inference from missing response.
- `AUTH_SCOPE_INCOMPATIBLE_OR_MISSING` — reply present but `permissionScope` absent or not `SCOPE_VIEW`.
- `AUTH_ORIGINAL_ACCOUNT_UNAUTHORIZED_OR_ABSENT` — the historical LIVE binding is not present or broker explicitly rejects account authorization.
- `AUTH_TRANSPORT_SERVER_INVALID_OR_TIMEOUT` — known proxy/server transport error code or transport exception.
- `AUTH_CAUSE_UNDETERMINED` — unrecognized broker code, malformed/unexpected response, or incomplete configuration.
- `AUTH_SCOPE_VIEW_ORIGINAL_LIVE_ACCOUNT_VERIFIED` — success of all three required auth messages and historical identity, but NOT EUR/broker terms/finance proof.

## Refresh and durable credential constraints

Official Spotware OAuth supports `apps/token?grant_type=refresh_token` and protobuf `ProtoOARefreshTokenReq`. A successful refresh returns a new **access + refresh** pair and invalidates the preceding pair. **Do not call refresh** unless both new values can be stored durably and securely before discarding old state.

Current workflow has only `R3_CTRADER_CLIENT_ID`, `R3_CTRADER_CLIENT_SECRET`, and `R3_CTRADER_ACCESS_TOKEN` in the protected Pepperstone environment. There is **no configured `R3_CTRADER_REFRESH_TOKEN` flow**, no `ProtoOARefreshTokenReq` allowlisting, no permitted repository/environment secret readback and no authenticated secure write-back of rotated pairs through the current connector. No saved secret value can be inspected. This is a verified architectural limitation, **not a proof that OWNER has no private refresh token elsewhere**. Neither the diagnostic nor source code triggers blind rotation.

If the one diagnostic confirms token expiry, provide OWNER only the necessary next secure action via the official cTrader permission page, requesting `scope=accounts` for the original application and account. Credentials must never be pasted into chat. Any new values need the original protected Github environment entry through a secure UI; no alternate OAuth application or trading scope.

## Economic boundary

BCF1 remains `SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS`. One diagnostic is not a recovered BCF1 collector. No original run is overwritten. No new Nov 2–6 source exists, no fresh independent confirmation, no C# ledger finance, no HARD21 qualification, no proof of <=30% equity DD, no Cloud activation or orders. The exposed 52 weeks remain research-only with unchanged closed-trial outcomes.

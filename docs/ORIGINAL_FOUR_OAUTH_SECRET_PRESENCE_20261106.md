# OWNER v2.0 — check original 4 OAuth secrets and safe refresh rotation (6 Nov 2026)

This note does not override `docs/OWNER_SPEC.md` and does not change any frozen economic study, data calendar, capital, C# ledger, SCOPE_VIEW account commitment, orders or Cloud. It concerns only the **original** GitHub Environment `mxm-r3-pepperstone-v1` and original MXM Quant Research cTrader OAuth identity.

## Terminology and actual permissions

1. **GitHub secret metadata exists**: the Environment REST API lists the secret name and timestamps (not its value). The present connected GitHub `fetch` API rejects all `/environments/mxm-r3-pepperstone-v1/secrets` URLs with `HTTPError: 400 GitHub Fetch URL is not an allowed public GitHub repository or search endpoint`. No dedicated environment-secret-list or secret-update tool is exposed by the installed connector. Therefore the Director cannot independently read secret metadata using this connector.
2. **Actually injected**: the predeclared one-shot protected Actions job runs within the original Pepperstone Environment and tests only whether GitHub injected a **nonempty** value for exactly the four OWNER-declared names `R3_CTRADER_CLIENT_ID`, `R3_CTRADER_CLIENT_SECRET`, `R3_CTRADER_ACCESS_TOKEN`, and `R3_CTRADER_REFRESH_TOKEN`. Its public result has only `AVAILABLE_IN_PROTECTED_JOB` / `NOT_AVAILABLE_OR_EMPTY_IN_PROTECTED_JOB` per name. No token lengths, hashes, contents, issuer, account numbers, expiry, or arbitrary environment variables are emitted. **Nonempty injected implies available in that job, not broker validity.** Not injected cannot prove GitHub metadata absence versus empty or denied injection.
3. **Used in code**: frozen source collectors use only client ID, secret and ACCESS token; the refresh secret is not used. The new presence job alone injects the refresh secret for a nonempty check, never sends it outside GitHub and never attempts refresh.
4. **Actually valid**: only official Spotware account/scope authentication or a completed safe refresh can establish token validity; the previously run authentic diagnostics did not prove that the access token was expired. The protected check does not verify validity and submits zero broker requests.

## Spotware OAuth semantics — exact unchanged app and authorization

Official [Spotware cTrader OAuth authentication](https://help.ctrader.com/open-api/account-authentication/) permits `POST https://openapi.ctrader.com/apps/token` with `grant_type=refresh_token`, `refresh_token`, `client_id`, `client_secret` (alternatively the Protobuf `ProtoOARefreshTokenReq`). The new response has **both** a new access and a new refresh token. The old pair is invalidated at successful rotation. The access token expires approximately 30 days after issuance; a refresh token ordinarily does not expire until consumed or the authorization is revoked/replaced. A refresh token's *presence* does not prove its validity or granted scope.

**Safety precondition:** do not call REST refresh, Protobuf refresh or the Playground until durable secure write-back of **both** returned token values is authorized and available, independently of subsequent workflow termination. Do not overwrite one old secret before the other new value can be retained. Never place tokens in job logs, source, public artifact or unencrypted repository file, nor send them in ChatGPT. No changing application identity, broker account, or scope. SCOPE_TRADE must never be substituted for SCOPE_VIEW.

## Durable write-back limitation established offline

The original job uses the GitHub-provided `GITHUB_TOKEN` with `contents: read`; neither the installed GitHub connector nor existing Actions workflows provide an authorized GitHub **Environment secrets write** method. Official [GitHub environment secret API](https://docs.github.com/en/rest/actions/secrets) requires `Environments: write` access, an Environment public encryption key and LibSodium sealed-box encryption. Updating `R3_CTRADER_ACCESS_TOKEN` and `R3_CTRADER_REFRESH_TOKEN` involves two separate secret writes and is not an automatically atomic pair transaction. Do not claim that a general GitHub token with repository contents permission can update Environment secrets or that two separate PUT requests form an atomic swap.

Given current **available** tools and permissions, safe autonomous refresh/rotation and durable installation are **NOT VERIFIED/NOT EXECUTABLE**. This is a limitation in the authorized GitHub write route, *not* proof of a missing refresh secret. No fresh app, repo, external vault, token or unauthorized GitHub PAT is requested or installed.

The latest authentic [auth-only diagnosis #42178238508](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42178238508) reported `AUTH_CAUSE_UNDETERMINED`, `applicationAuthenticationVerified=true`, `explicitSCOPE_VIEWVerified=false`, and two auth requests. Neither BCF1, nor this presence check, may automatically be relaunched as broker research. Existing `research/collect.py` and all frozen evidence SHA are byte-identical.

## Protected one-shot control

The presence test is registered only through the exact single-file change to `ops/original-four-oauth-secret-intent.txt` with commit title `MXM_ORIGINAL_FOUR_OAUTH_SECRET_PRESENCE_ONCE` on `main` by the original owner. The implementation PR, generic pushes, PR branches and `workflow_dispatch` cannot trigger it. The protected step needs only `python` and zero external broker requests, no `GITHUB_TOKEN` write permission; its categorized public artifact can be independently downloaded and SHA-verified. Its result must be preserved in the existing evidence registry without pretending token validity or research-source recovery.

## Economic continuation

Capital prospectiv EUR300 continuous, native C# funding, HARD21 systemwide, max 30% open-equity DD, >=12 months authentic data plus uncontaminated confirmation, BCF1 `SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS`, all closed exact trials untouched. Zero LIVE/DEMO orders, zero Cloud activation. No new BCF1 source, independent holdout or financed EUR NET results are implied by checking secret availability.

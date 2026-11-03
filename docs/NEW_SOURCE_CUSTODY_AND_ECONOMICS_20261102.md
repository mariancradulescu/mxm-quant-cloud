> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# MXM B–E — new-source custody and original Pepperstone account binding (2026-11-02)

## Architectural decision: NEW source is independent of historic R3 ciphertext

The *existing* RSA private key under GitHub Environment `mxm-r3-custody-v1` is the only RSA private key used by the new-source v2 pipeline. This key was already configured by OWNER; the pipeline **does not generate a keypair, OAuth identity, or external credential**. A protected `custody_recipient` job parses the installed RSA private key, checks its type/strength, derives its public SPKI, performs an in-memory RSA-OAEP-SHA256 / AES256-GCM round-trip challenge, and publishes **only** the public recipient PEM and its SHA-256 fingerprint in a workflow-run-bound artifact. If this fails, all subsequent source collection is skipped.

The authorized Pepperstone `collect` job downloads that same-run public artifact and verifies its fingerprint and workflow run ID, then authenticates via the existing cTrader Open API application and SCOPE_VIEW token; requires a **single exact token-listed LIVE account** matching the historic pinned account identity; independently validates the trader's Pepperstone broker name; and collects bounded read-only source. It encrypts the source and C# receipt using `MXM_NEW_PEPPERSTONE_READ_ONLY_SOURCE` **version 2** AES-256-GCM / RSA-OAEP-SHA256 with an independently generated *one-time symmetric session key and nonce per envelope* (not a new RSA identity); domain-specific authenticated AAD binds the immutable `GITHUB_RUN_ID`. The uploaded source artifact is ciphertext plus a public digest receipt. A protected `custody` job then decrypts with **the same existing private key**, validates recipient, run binding and integrity and independently reconciles the native C# source readback.

The pinned historic recipient `research/custody_public.pem` is **not modified** and remains exclusively relevant to decrypting archives sealed for the earlier private key `MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM`. Its mismatch with the installed new-repository private key cannot block the **new-source** pipeline. No legacy ciphertext is converted, decrypted, invalidated or destroyed by the v2 pipeline.

This structural decoupling does not imply that the configured new RSA private key is valid, available or matched until its protected job actually returns SUCCESS. CI's ephemeral synthetic key tests are strictly non-evidence.

## Authentic original Pepperstone account identity without the malformed secret

The account association uses a **double-SHA256 commitment** to the original, public one-way `ACCOUNT_FINGERPRINT_SHA256` in `mxm-quant-greenfield`, `research_core_v4/shallow_m5_support_v2_production.py`, immutable historical commit `6a4e56758d985f00020cd13ef264e8dc84fc6a9b`, line 49. The original fingerprint formula is SHA-256 of ASCII `ctrader-account:<ctidTraderAccountId>`. In `research/collect.py`, the collector hashes that candidate fingerprint a second time and compares it against the fixed commitment in the NEW code. It does not use the malformed environment value `R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256` to define identity, does not guess account IDs, and never authenticates an unbound account.

This is a cryptographic commitment to the **same exact historical fingerprint**, not permission to use some other token-listed account. Application OAuth and explicit SCOPE_VIEW remain mandatory. The previous logs confirmed both steps independently. No claim of account reauthentication is made until a new protected run passes binding and Pepperstone trader authentication.

The historical repository is left unchanged. The account identity check requires no fetch from the old repo at runtime; its fixed original double hash is already part of the new repository.

## Scientific and capital discipline

Neither this change nor success of CI represents EUR 200 funded P&L, twelve-month coverage, full roundtrip broker costs, equity extrema or system HARD21. The existing new C# `PortfolioEconomics` deliberately refuses economic qualification based only on declared flags; it remains an analysis engine until bound to authenticated source/fills/costs and a pre-registered independent chronological confirmation. The pre-existing H1 integration collector still covers a bounded seven-day sample, not the unrestricted final research universe, and its H1 predictor remains unqualified. New hypothesis design and prospective testing must not reuse rejected models or cherry-pick historic PRIMARY145 outcomes.

All order requests remain prohibited. The sole `.algo` artifact is an observation-only native cBot that stops on startup. It must not be deployed as trading-ready or activated in cTrader Cloud.

## GitHub operational conditions

Only the specific owner/main marker-only source-admission event or the protected explicit dispatch request can run the three protected jobs (`custody_recipient`, `collect`, `custody`). Generic pushes and pull requests run secret-free tests only. The original source marker identity gate, explicit environment protections, read-only protobuf request allowlist, public/private separation and non-trading code remain.

`main` formal branch protection remains administratively unavailable with the current GitHub connector. Code changes are isolated, CI-tested and merged through PR with an expected-head lease.

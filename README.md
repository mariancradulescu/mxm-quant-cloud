# MXM Quant Cloud

Public greenfield implementation under OWNER specification v1.0 and the 2026-11-02 public-repository decision. Initial capital EUR 200, no additional deposits; maximum drawdown control objective 30%; HARD21 means at least 21 fully closed round trips per objectively eligible week, never forced trades.

**Status: native foundation only. No qualified strategy, no profitability claim, no trading authority. Do not activate the artifact in Cloud, LIVE or DEMO.** The current cBot reads native account collections then stops; it contains no order submission, cancellation or position modification functions.

The repository contains a shared C# core, an observation-only cBot and focused accounting/recovery checks. One Linux workflow builds the `.algo` artifact without secrets. GitHub is development infrastructure, not the future trading decision engine. The final product will be one native cBot controlled from Android.

See [architecture and recovery](docs/ARCHITECTURE.md), [migration provenance](docs/MIGRATION.md), [implemented migration](docs/MIGRATION_IMPLEMENTED.md), [existing credential setup](docs/CREDENTIAL_SETUP.md) and [acceptance gates](docs/ACCEPTANCE.md). Passing compilation or synthetic checks does not establish economic advantage or operational Cloud acceptance.

Machine-side read-only collection and separate encrypted custody readback are implemented in the same workflow. They require existing configured environment secrets and may run only after explicit owner/main dispatch or an exact owner/main push request (not ordinary pushes or PRs). See [Chat-normal execution boundary](docs/CHAT_NORMAL_EXECUTION_20261102.md). Automatic push/PR checks have no credentials. The seven-day H1 sample is source integration only; no predictive strategy or twelve-month economic validation is claimed.

## Current economic research implementation

The native C# core now includes a strictly evidenced EUR 200 portfolio NET/HARD21/certified-extrema evaluator and a separate causal adaptive H1 observational forecaster. GitHub CI verifies the original 100 encrypted archive asset identities without secrets or broker requests; it does not decrypt archives or claim their four-week coverage satisfies the required twelve months. See [economic core and source provenance](docs/ECONOMIC_CORE_20261102.md) and [two-existing-secret recovery](docs/OWNER_SECRET_RECOVERY_20261102.md). The final cBot is still observation-only; no strategy has economic qualification or trading authority.

## New-source custody separation (2026-11-02)

The existing installed custody PRIVATE key is now used to derive a **new-source v2 PUBLIC recipient**, only within the protected GitHub Actions pipeline. The older historical RSA recipient is preserved for historical archives and is NOT required for collection of new Pepperstone source. The authentic original LIVE account fingerprint is bound by its immutable double-SHA256 commitment in `research/collect.py` and no longer selected by the previously malformed fingerprint environment secret; OAuth app and SCOPE_VIEW remain unchanged. Details: [new-source custody and account binding](docs/NEW_SOURCE_CUSTODY_AND_ECONOMICS_20261102.md). No data collection is claimed until the new protected GitHub run actually succeeds.

## First authenticated new-source predictive result (2026-11-02)

GitHub Actions [#41467047520](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41467047520) fully passed authenticated SCOPE_VIEW and original LIVE Pepperstone identity, new-source RSA-v2 encryption with the already installed private key, original C# source receipt, and protected C# readback. A second **broker-free** encrypted-source cold replay, [#41468900768](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41468900768), scored the already frozen `CausalRangePressureResearch` H1 configuration on 467 authentic source bars and 368 causally scoreable forecasts: mean Brier 0.2506694056 versus neutral 0.2500000000; relative skill **−0.2678%**. The exact H1 configuration is **CLOSED_NONPOSITIVE_PREQUENTIAL_SKILL**, with no inversion or retuning. See [public immutable outcome aggregate](docs/NEW_SOURCE_H1_CAUSAL_COLD_VERDICT_20261102.json). No executable NET edge, HARD21 broker trades, funded capital backtest, 12-month independent confirmation or Cloud activation has been proven. Other distinct candidates and timeframes remain open.

# MXM Quant Cloud

Public greenfield implementation under OWNER specification v1.0 and the 2026-11-02 public-repository decision. Initial capital EUR 200, no additional deposits; maximum drawdown control objective 30%; HARD21 means at least 21 fully closed round trips per objectively eligible week, never forced trades.

**Status: native foundation only. No qualified strategy, no profitability claim, no trading authority. Do not activate the artifact in Cloud, LIVE or DEMO.** The current cBot reads native account collections then stops; it contains no order submission, cancellation or position modification functions.

The repository contains a shared C# core, an observation-only cBot and focused accounting/recovery checks. One Linux workflow builds the `.algo` artifact without secrets. GitHub is development infrastructure, not the future trading decision engine. The final product will be one native cBot controlled from Android.

See [architecture and recovery](docs/ARCHITECTURE.md), [migration provenance](docs/MIGRATION.md), [implemented migration](docs/MIGRATION_IMPLEMENTED.md), [existing credential setup](docs/CREDENTIAL_SETUP.md) and [acceptance gates](docs/ACCEPTANCE.md). Passing compilation or synthetic checks does not establish economic advantage or operational Cloud acceptance.

Machine-side read-only collection and separate encrypted custody readback are implemented in the same workflow. They require existing configured environment secrets and may run only after explicit owner/main dispatch or an exact owner/main push request (not ordinary pushes or PRs). See [Chat-normal execution boundary](docs/CHAT_NORMAL_EXECUTION_20261102.md). Automatic push/PR checks have no credentials. The seven-day H1 sample is source integration only; no predictive strategy or twelve-month economic validation is claimed.

## Current economic research implementation

The native C# core now includes a strictly evidenced EUR 200 portfolio NET/HARD21/certified-extrema evaluator and a separate causal adaptive H1 observational forecaster. GitHub CI verifies the original 100 encrypted archive asset identities without secrets or broker requests; it does not decrypt archives or claim their four-week coverage satisfies the required twelve months. See [economic core and source provenance](docs/ECONOMIC_CORE_20261102.md) and [two-existing-secret recovery](docs/OWNER_SECRET_RECOVERY_20261102.md). The final cBot is still observation-only; no strategy has economic qualification or trading authority.

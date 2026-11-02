# MXM Quant Cloud

Public greenfield implementation under OWNER specification v1.0 and the 2026-11-02 public-repository decision. Initial capital EUR 200, no additional deposits; maximum drawdown control objective 30%; HARD21 means at least 21 fully closed round trips per objectively eligible week, never forced trades.

**Status: native foundation only. No qualified strategy, no profitability claim, no trading authority. Do not activate the artifact in Cloud, LIVE or DEMO.** The current cBot reads native account collections then stops; it contains no order submission, cancellation or position modification functions.

The repository contains a shared C# core, an observation-only cBot and focused accounting/recovery checks. One Linux workflow builds the `.algo` artifact without secrets. GitHub is development infrastructure, not the future trading decision engine. The final product will be one native cBot controlled from Android.

See [architecture and recovery](docs/ARCHITECTURE.md), [migration provenance](docs/MIGRATION.md), [implemented migration](docs/MIGRATION_IMPLEMENTED.md), [existing credential setup](docs/CREDENTIAL_SETUP.md) and [acceptance gates](docs/ACCEPTANCE.md). Passing compilation or synthetic checks does not establish economic advantage or operational Cloud acceptance.

Machine-side read-only collection and separate encrypted custody readback are now implemented in the same workflow, exclusively through explicit protected dispatch on main. They require OWNER configuration of existing secrets. Automatic push/PR checks have no credentials. The seven-day H1 sample is source integration only; no predictive strategy or twelve-month economic validation is claimed.

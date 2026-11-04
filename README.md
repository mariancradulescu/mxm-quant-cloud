# MXM Quant Cloud

Public implementation under the single [active OWNER specification v2.0](docs/OWNER_SPEC.md), updated with the 2026-11-04 integrated OWNER decision. Initial capital EUR 200, no additional deposits; maximum drawdown control objective 30%; HARD21 means at least 21 fully closed round trips per objectively eligible week, never forced trades.

**Status: authentic exploratory research and native portfolio research kernels; No qualified strategy, no profitability claim, no trading authority. Do not activate the artifact in Cloud, LIVE or DEMO.** The current cBot reads native account collections then stops; it contains no order submission, cancellation or position modification functions.

The repository contains a shared C# core, an observation-only cBot and focused accounting/recovery checks. One Linux workflow builds the `.algo` artifact without secrets. GitHub is development infrastructure, not the future trading decision engine. The final product will be one native cBot controlled from Android.

See [architecture and recovery](docs/ARCHITECTURE.md), [migration provenance](docs/MIGRATION.md), [implemented migration](docs/MIGRATION_IMPLEMENTED.md), [existing credential setup](docs/CREDENTIAL_SETUP.md) and [acceptance gates](docs/ACCEPTANCE.md). Passing compilation or synthetic checks does not establish economic advantage or operational Cloud acceptance.

Machine-side read-only collection and separate encrypted custody readback are implemented in the same workflow. They require existing configured environment secrets and may run only after explicit owner/main dispatch or an exact owner/main push request (not ordinary pushes or PRs). See [Chat-normal execution boundary](docs/CHAT_NORMAL_EXECUTION_20261102.md). Automatic push/PR checks have no credentials. The seven-day H1 sample is source integration only; no predictive strategy or twelve-month economic validation is claimed.

## Current economic research implementation

The native C# core now includes a strictly evidenced EUR 200 portfolio NET/HARD21/certified-extrema evaluator and a separate causal adaptive H1 observational forecaster. GitHub CI verifies the original 100 encrypted archive asset identities without secrets or broker requests; it does not decrypt archives or claim their four-week coverage satisfies the required twelve months. See [economic core and source provenance](docs/ECONOMIC_CORE_20261102.md) and [two-existing-secret recovery](docs/OWNER_SECRET_RECOVERY_20261102.md). The final cBot is still observation-only; no strategy has economic qualification or trading authority.

## New-source custody separation (2026-11-02)

The existing installed custody PRIVATE key is now used to derive a **new-source v2 PUBLIC recipient**, only within the protected GitHub Actions pipeline. The older historical RSA recipient is preserved for historical archives and is NOT required for collection of new Pepperstone source. The authentic original LIVE account fingerprint is bound by its immutable double-SHA256 commitment in `research/collect.py` and no longer selected by the previously malformed fingerprint environment secret; OAuth app and SCOPE_VIEW remain unchanged. Details: [new-source custody and account binding](docs/NEW_SOURCE_CUSTODY_AND_ECONOMICS_20261102.md). This paragraph records the original pre-execution boundary; the authenticated runs documented below supersede that historical status.

## First authenticated new-source predictive result (2026-11-02)

GitHub Actions [#41467047520](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41467047520) fully passed authenticated SCOPE_VIEW and original LIVE Pepperstone identity, new-source RSA-v2 encryption with the already installed private key, original C# source receipt, and protected C# readback. A second **broker-free** encrypted-source cold replay, [#41468900768](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41468900768), scored the already frozen `CausalRangePressureResearch` H1 configuration on 467 authentic source bars and 368 causally scoreable forecasts: mean Brier 0.2506694056 versus neutral 0.2500000000; relative skill **−0.2678%**. The exact H1 configuration is **CLOSED_NONPOSITIVE_PREQUENTIAL_SKILL**, with no inversion or retuning. See [public immutable outcome aggregate](docs/NEW_SOURCE_H1_CAUSAL_COLD_VERDICT_20261102.json). No executable NET edge, HARD21 broker trades, funded capital backtest, 12-month independent confirmation or Cloud activation has been proven. Other distinct candidates and timeframes remain open.

## Authentic multi-resolution economic measurement (2026-11-02)

The original pinned Pepperstone Europe LIVE account and installed private-key-derived v2 custody successfully collected and independently replayed the **new** fixed universe of EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD and XAUUSD on H4 and M15 in [Actions #41476636915](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41476636915): **15,113 genuine bars**, H4 observations in **13 calendar months per symbol** and one-minute authentic broker BID/ASK source samples. A completely distinct, predefined native C# 12-bar breakout with fourth-bar price-only exit was evaluated *without recollection* under protection in [Actions #41478328221](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41478328221): **386 H4** and **433 M15** gross OHLC proxy episodes across **all six symbols**, with **five positive and seven negative** mean gross-pip groups. No cross-instrument pip sum or positive-only selection is allowed. This is solely exploratory on previously research-exposed historical dates: historical spread samples are **not** entry/exit fills, broker margin/cost completeness and 200 EUR funded executable NET are **unproven**, and no independent confirmation, HARD21 or 30% global DD certificate follows. See [exact cold economic evidence](docs/AUTHENTIC_ECONOMIC_BREAKOUT_VERDICT_20261102.json). **No new orders or Cloud activation.**

## Integrated system research (OWNER v2.0)

The shared native `OpportunityOrchestrator` consumes causal economic opportunities
and aligned joint scenarios, uses `AdaptivePortfolioRisk`, reserves common margin
and risk, then reranks remaining opportunities. A thin Python adapter connects
its decisions to the existing chronological `FundedReplay`. Both are research
components; no authentic portfolio incremental edge or qualified adaptation has
been demonstrated. `research/evidence_registry.json` conservatively tracks global
data exposure; no existing historical partition is automatically independent.

The frozen JOP1 multi-asset development probe measures causal opportunity coverage
and conflicts on existing authenticated source. Missing executable historical
quotes/costs must prevent funded entries. See the active specification for the
evidence levels, current implementation policy and remaining qualification work.

Authentic [JOP1 result](docs/JOINED_OPPORTUNITY_AUTHENTIC_RESULT.json), protected
[run 41627571731](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41627571731):
11,696 opportunities, 978 multi-asset clocks, 66 gross relationships, zero matching
entry/exit quote-window coverage, and all 11,696 native allocations correctly
declined. No funded replay was started and no incremental NET edge is claimed.
JQE1 extends evidence access on a fixed tiny all-six-asset clock grid; it cannot
qualify historical costs or portfolio performance.

Authentic [JQE1 evidence and complete current margin frontier](docs/JOINT_QUOTE_EVIDENCE_AUTHENTIC_RESULT.json),
[run 41628896432](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41628896432):
39 evidence requests, all 12 fixed historical quote events recovered, all six
H4 interval geometries matched, encrypted independent raw readback passed.
Current minimum margins total EUR164.18 for five FX instruments, EUR174.66 for
XAUUSD alone, and EUR338.84 for all six. With additive current margins, XAUUSD
plus the cheapest FX minimum needs EUR204.48 before costs/stress. All64 subsets
are disclosed; these are current margin-only upper capacity observations, not
historical margin evidence, risk admission, allocation weights or strategy NET.
Complete event/holding coverage, cost/FX/financing history, causal joint EUR-risk
estimation and independent portfolio validation remain necessary.

EPA1 connects a bounded predefined economic source grid to native C# FX/commission
valuation, the common selector and the existing funded account ledger. Its
[prospective protocol](research/portfolio_economic_protocol.json) compares central
and uncertainty-screened conditional policies and all candidate ablations. It
uses an explicit research-estimate endpoint; sampled risk references never become
certificates or verified product admission. Authentic protected source collection, independent raw readback and economic
replay succeeded in the separately authorized execution below.

## First integrated conditional portfolio economics — EPA1

[Authenticated run #41634941443](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41634941443)
succeeded: 1,101 read-only evidence requests,87/90 complete synchronized snapshots,
native C# EUR valuation and decisions, common EUR200 funded ledger and all 24
predeclared candidate ablations. Preserve the [full original result](docs/EPA1_AUTHENTIC_PORTFOLIO_RESULT.json).

| Predeclared policy | Slippage each side / observed entry spread | Closed modeled trips | Conditional NET EUR | Sampled incomplete DD |
|---|---:|---:|---:|---:|
| Primary 2-SE uncertainty screen |0|3|+4.570039|1.7168%|
| Primary 2-SE uncertainty screen |0.5|3|+4.408195|1.7500%|
| Primary 2-SE uncertainty screen |1|3|+4.246351|1.7831%|
| Central sensitivity only |0|4|+8.551930|11.7757%|
| Central sensitivity only |0.5|4|+8.269750|11.8370%|
| Central sensitivity only |1|4|+7.987570|11.8984%|

At 0.5x, primary capital is modeled 200→204.408195 EUR. All three positions
are USDJPY reversal, 6000 units each; eliminating that candidate leaves zero
trades and zero NET. The last trade contributes +5.128523 EUR,116.34% of total
NET; the first two sum to−0.720328 EUR. This is concentrated preliminary
conditional performance, not independently confirmed portfolio advantage.

The central sensitivity books XAUUSD drift and USDJPY reversal. After modeled
retained gains lifted cash to 232.080052 EUR, the June12 decision reserved 204.79
EUR of scenario margin for simultaneous XAUUSD 1-unit and USDJPY 1000-unit
positions. This demonstrates shared capital, reinvestment, competing opportunity
selection and financing/risk interactions. It does not qualify that policy.
Removing USDJPY reversal changes central NET by 1.834825 EUR although its booked
contribution is 0.854754 EUR: the ablation also reallocates opportunities. These
are descriptive interactions on exposed data, not marginal-alpha proof.

Missing snapshots: June9 12:30 UTC (open-position mark), June11 08:59:40 UTC
(predecision, all entries suspended that day), June11 09:30 UTC. No substitution,
imputation or hindsight day removal occurred. Both ledgers end flat and their
closed cash arithmetic reconciles; the unchanged ledger correctly retains
`INCOMPLETE_EXPOSURE_OR_EVIDENCE`, incomplete marks and unverified financing.
The full five-day calendar includes Monday warmup abstention and Thursday's
source-driven abstention. It is not an independently confirmed eligible week.

Historical tariffs/financing, actual slippage, available executable volume/depth
and continuous drawdown remain unproven. Simulated selected volume at observed
BID/ASK is a conditional fill model, not observed liquidity. Sampled peak and
loss paths are research references only. No LIVE/DEMO orders, Cloud activation,
HARD21 qualification, policy selection or candidate promotion follows. Original
protocol/results are frozen without retuning or retrospective gap repair.

Diagnostic interpretation: the 13 no-proposal slots include frozen warmup, absent
causal features or a zero descriptor; they are not 13 additional quote outages.
Native rejection reasons describe the final marginal state after selected capital
is reserved and are not exclusive standalone failure explanations. The primary
0.5x case evaluates 35 actual proposals: 3 admitted and 32 declined. Twelve candidate
slots on Monday have no frozen proposal; another zero/absent proposal occurs later.
Thursday is separately recorded as a source-driven suspension before selection.

EPA2 is prospectively frozen in [the holding protocol](research/portfolio_holding_protocol.json).
It separately audits EPA1's fixed positions and cash without rescoring, then tests
three calendar strata, two holding horizons and active in-position protection
through the same native allocator and funded ledger. Current leverage/margin
profiles are observed, while historical used margin and account stopout threshold
remain unverified. The protected economic execution has completed; its frozen verdict follows immediately below.

EPA2 authenticated run [41648280262](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41648280262)
completed 12 fixed January/April/July development days and both 2/4-hour horizons.
All eight cases admitted zero trades at the evidence gate: modeled capital stays
EUR200, with no evidence of portfolio edge or in-position adaptation from EPA2.
[The frozen receipt](docs/EPA2_AUTHENTIC_HOLDING_RESULT.json) preserves all cases.
3725 bounded read-only requests yielded 612 partial-or-full as-of states (257 with
all six assets). Missing evidence is not economic unprofitability; a broker-free
custody diagnosis must identify the exact route/calibration/margin blocker without
relaxing the frozen criteria. EPA1 original fixed trades reconcile unchanged;
sampled equity/margin minima at 0.5x slippage are 109.9214% (primary 2-SE) and
101.6992% (central sensitivity). No observed 50% reference crossings; one missing
holding mark and between-mark execution uncertainty preclude a liquidation or DD
certificate. No orders, activation, policy selection or promotion.

Broker-free [diagnosis 41654064703](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41654064703)
identified the precise EPA2 blocker: zero of 72 candidate/symbol/horizon/cohort groups
had all six complete fixed-asof calibrations (observed range 0–3). Funding schedules
passed; predecision margin routes existed for 57/72 symbol-days. Availability-only
first causal quote windows covered 596–609/612 routes per asset and all required
calibration windows for 68/72 groups. These are **not replacement fills or repaired
EPA2 results**. Any future event-time evaluation needs its own prospective protocol;
EPA2 is closed and the old entrypoint refuses recollection/replay after freezing.

[The separate fixed-book sensitivity](docs/EPA2_EXECUTION_DIAGNOSIS.json) also shows
why margin units matter: decoding raw tier 2000/3000 as 20/30 produces, for EPA1's
central 0.5x case at June12 13:00 UTC, EUR211.0470 margin versus EUR208.2697 sampled
liquidation equity (98.6840%). It requests a model protective exit, without applying
one to or rewriting EPA1. No sampled 50% reference crossing is observed; broker
threshold and execution remain unknown. Native holding risk now requires explicit
tier-unit encoding and rejects ambiguous input; raw research callers use the
conservative hundredths scenario. Original raw-scale EPA2 audit remains frozen.
All three ciphertexts were re-archived encrypted through 2027-02-01. Incremental
edge, live holding adaptation, HARD21, continuous DD and 12-month independent
validation remain unproved; no policy or candidate is promoted.


## Systemic economic decision after PR50

[System economic feasibility](docs/SYSTEM_ECONOMIC_FEASIBILITY.md) quantifies all12
existing cost contexts, EUR200 concentration and HARD21 occupation-time identities.
It makes no source/model calls, admits no unsupported new study and claims neither
independent edge nor system impossibility. OWNER_SPEC.md remains the authority;
closed studies, native core and observation-only trading prohibition are preserved.


[Authentic displayed-depth discovery pilot](docs/DCP1_CHANNEL_RESULT.md): DCP1
retained5,871 original spot/depth events on all six instruments with independent
protected raw readback. The fixed source gate failed (2 of required3 supported
symbols); no returns/model/NET were evaluated and no expansion is admitted. This
removes an event-capture obstacle, not the unresolved economic-evidence requirement.


[Multiscale conditional economics](docs/MSP1_CONDITIONAL_ECONOMIC_RESULT.md): MSP1
evaluated new persistent/transitory/zero-drift structural forecasts on836087
conserved bars across12 assets, four timeframes and three statistical-cost cases.
166 genuine development quote contexts support explicitly uncertain cost estimates.
No selection-adverse followup is supported; exact profile is closed. Native
ledger/orchestrator/session remain unchanged; no funded NET or HARD21 is claimed.

# CMA1 — prospective broker fee and funding provenance (2026-11-08)

Authority: `docs/OWNER_SPEC.md` OWNER v2.0 and explicit 2026-11-08 decision.
Scope: **cost/contract recovery, not a predictive backtest or XUA1 re-score**.

## Exact existing-source audit

Reuse **only** the frozen encrypted `CCP1` source run `41774823771`, original ciphertext SHA256
`d0d080c94fa1208a2973bd230b9727a14b3596ccbdb81b373ae2df4361e3ce52`,
frozen `research/carry_cycle_preflight_protocol.json`, and the existing custody private
key available solely in the protected GitHub custody environment. Verify original
authenticated Pepperstone EUR account with the unmodified original account-binding
auditor, exact request/reply pairs, symbol IDs, current margin grids and SHA values
before extracting any tariff/rollover field.

CMA1 reports the original account's **as-observed** precise commission rate and
`commissionType` (USD per million USD notional / USD per lot / percentage of
notional / quote currency per lot), minimum commission and currency, P&L
conversion fee, swap direction/type/period/time, 3-day rollover, weekend charges,
swap-free administration if applicable, and symbol trading schedule presence.
Absent optional fields stay **unknown**, never zero or inferred protobuf defaults.
Rates retain official wire scales; they are not silently misinterpreted as bps.

The authenticated contract **does not establish historical tariff continuity**,
historical fills, next-session rates or current executable depth. Historical BID/ASK
must be paired and fresh at each later decision/exit clock. Spread is charged exactly
once: if simulated fill prices already use bid/ask sides, no extra additive spread.
The brokerage fee is distinct from modeled slippage, which remains a transparent
central/adverse/stress uncertainty rather than a universal 6/12/24 bps tariff.
Conversions require the actual asset route and causal bid/ask price. Intraday
or interday holding eligibility is controlled by **observed symbol swap schedule**,
not a universal UTC-midnight prohibition. If scheduling or price data are incomplete,
financing is unknown, never zero.

## Real universe expansion: new targeted preflight, not a 12→18 ceiling

The original CCP1 authenticated contract source already covers `EURJPY`,
`AUDJPY`, `NZDJPY`, `NZDUSD`. These four lie outside the fixed original
12-symbol development roster and six XUA1 markets; they are not claimed as new
2026-11-08 broker reads. Outcome-blind candidate priority:

1. **EURJPY, AUDJPY, NZDJPY (JPY-session repricing):** investigate M15 completed
   post-session price adjustments with causally completed H4 risk regime; alternative
   H1 with H4 for region-shock persistence only if distinct premise is predeclared.
   Matched same-clock unchanged-price-momentum and cash-flat policies required.
2. **NZDUSD (regional-session volatility propagation):** investigate M15 trade
   session-to-session returns conditioned on H4 completed volatility; hypothesis
   distinct from closed USD-major transmission and existing H1 models.

No new economic scoring is approved by this audit alone. For each of these markets,
first require current trading mode, minimum lot and volume step, EUR side-specific
commission at fresh FX conversion, valid paired BID/ASK clocks, opening hours,
swap rate type/time and minimum margin grid. A minimum margin below EUR300 is only
an initial *single-leg feasibility condition*. Then collect selectively genuine
consecutive M15/H4 bars on original LIVE read-only Open API, without reusing the
XUA1/CPF1 outcome-selected examples. Freeze new feature/hold and chronology
**before** evaluating returns. Historical overlap in all 52 previously exposed
weeks is development-only; genuinely new chronological data are required for
independent confirmation.

## Hard economic and operating gates

Only candidates with positive matched-benchmark **adverse** incremental economics
on prospectively selected periods may enter the existing `OpportunityOrchestrator`
and `NativeFundedLedger`. The funded evaluation starts with one EUR300 common
synthetic portfolio, preserves actual observed minimum and step volumes,
conversion, capacity under simultaneous positions, all costs and floating
30% drawdown, and counts HARD21 only for fully closed financed system round
trips per ex-ante eligible week. If any cost or financing component is unavailable,
admission fails closed. No candidate-level HARD21 mandate.

No old protocol, receipt, HOLDOUT or price series is changed. No LIVE/DEMO orders,
no Cloud activation, no token refresh or second trading account. This script and
GitHub Actions are **research-time only**, not a Cloud runtime dependency.

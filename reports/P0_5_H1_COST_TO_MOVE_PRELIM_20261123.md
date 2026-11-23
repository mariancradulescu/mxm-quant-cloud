# P0.5 — H1 cost-to-move first-pass, NOT A COMPLETED GATE (2026-11-23)
**Status: PRELIMINARY / P0.5 NOT PASSED / NO NEW TRADING OR ECONOMIC BACKTEST.**
This is a bounded arithmetic screen of existing original-source development preflight, NOT independent profitability evidence. This report was added solely to answer whether costs already threaten the proposed EUR300/HARD21 goal before elaborate infrastructure.

## Reproducible inputs and formula
- Source path: `docs/EUR_ECONOMIC_PREFLIGHT_RESULT.json` at main commit `dde596ed34ec5c1df7b45093c5da312d0aa2a543`; Git blob SHA `abc08a918daa334236054045a54d14c5f4cd1930`.
- `eur_economic_preflight.horizon_minutes=60`, `capital_reference_eur=300`, source quote dates 3–6, 12 source markets. Prior source is H1 / DEVELOPMENT ONLY.
- `median_move_EUR = median_absolute_move_eur_at_reference_notional`. `partial_2x_cost_EUR = twice_original_base_cost_stress_eur`. `ratio_percent = 100 * partial_2x_cost_EUR / median_move_EUR`. Values rounded to 2 decimals for display, nonrounded source used in division.
- **IMPORTANT:** 2x cost is two times an *original BASE cost proxy*, **not twice an authenticated all-in broker cost**. Source explicitly excludes diffusion proxy, maximum commission for adverse, conversion wedge and funding. Live broker terms or source-time matched economic fills are NOT verified by this calculation.
- Static min margin is an as-of historical source observation per minimum reference volume, not a guarantee of actual funding, risk safety or current conditions. No new broker request, no accounts accessed, no secrets used.

## Economic diagnostic (EUR, source H1 only)
| Symbol | Source min margin EUR | Median absolute H1 move EUR | 2× original base-cost proxy EUR | Proxy / median move | Distinct quote dates |
| --- | ---: | ---: | ---: | ---: | ---: |
| NAS100 | 126.50 | 2.32 | 0.87 | 37.40% | 5 |
| XAUUSD | 175.58 | 7.56 | 2.98 | 39.39% | 6 |
| GER40 | 129.17 | 2.59 | 1.24 | 48.10% | 3 |
| JPN225 | 177.95 | 4.88 | 2.56 | 52.37% | 5 |
| EURUSD | 33.33 | 0.38 | 0.21 | 55.04% | 6 |
| US500 | 33.89 | 0.46 | 0.26 | 56.39% | 5 |
| AUDUSD | 31.13 | 0.37 | 0.22 | 60.53% | 6 |
| USDJPY | 29.79 | 0.42 | 0.27 | 65.39% | 6 |
| GBPUSD | 39.96 | 0.51 | 0.36 | 69.32% | 6 |
| UK100 | 63.50 | 1.02 | 0.91 | 88.73% | 3 |
| USDCAD | 29.79 | 0.27 | 0.26 | 96.85% | 6 |
| AUS200 | 27.50 | 0.50 | 0.69 | 137.82% | 5 |

- From the published 12-market snapshot, cost-to-median ratio ranges from 37.40% to 137.82%; 1/12 instruments have the 2× original base proxy at least as large as the median absolute H1 move. These are **diagnostics, not mathematical impossibility proofs**: a profitable selective strategy could exploit unusually large moves, but only verified causal signals and net/funded outcomes would establish that.
- **M15, M30, H4 and D1**: unavailable in this original-source table. No fabricated interpolation from H1, no claim of horizon exclusion.
- **HARD21/positive weekly opportunities on the EUR300 continuous portfolio**: NOT MEASURED by this source. A trading-opportunity count cannot be inferred from the number of market observations. NO mathematical HARD21 feasibility claim.
- **NET, percentage return, weekly completed trips, marked-equity DD, x1/x1.5/x2 ALL-IN, CASH/trivial/random comparison and independent confirmation**: NOT AVAILABLE in this source. No 0s substituted.
- Prior original *separate* development study Action #45032546544 reported in PR #423: VALUE_CONTEXT NET -1.963785 EUR (approx. -0.65% of EUR300), 0/11 HARD21 weeks, sampled DD 0.654595%; VALUE_FIRST NET -88.020427 EUR (-29.34%), 6/11 HARD21 weeks, sampled DD 29.973028%. These outcomes were **not rerun or independently rehashed in this operation**, do not constitute independent confirmation and are not merged into the preflight sample.

## Required before P0.5 can pass
1. Authenticate input history, contracts, executable minimum volume, real BID/ASK observations or bounded pessimistic modeled spread by symbol/session/volatility, commission, slippage, swap, FX and margin; only read-only broker access allowed; do not inspect or recreate secrets.
2. For M15/M30/H1/H4/D1, calculate typical tradable move and contemporaneous all-in round-trip cost, including x1/x1.5/x2 and adequate session coverage. Do not exclude any horizon using incomplete data.
3. Quantify, on the frozen discovery period only, the *financeable complete positive-NET opportunities per eligible ISO week* with one continuous EUR300 ledger, no lookahead; derive a HARD21/DD frontier. If genuinely below 21, report clear incompatibility before building more.
4. Do not touch chronological confirmation B (starts 2026-11-30 UTC) or final C (starts 2027-05-31 UTC), do not modify original studies or start any Cloud/LIVE/DEMO execution.
5. At P0 gate, the ongoing #45111043597 and eight old queued Actions require resolution. The connected GitHub interface lacks a cancel-run capability; none was canceled by this work. P0 is not certified without scope/account/CLI backtest evidence.

**Verdict: INCONCLUSIVE / P0.5 OPEN.** Concrete source-based screening was completed for H1 only; no qualified trading advantage and no HARD21 coexistence is proven. The next technical work is filling genuine economic inputs, not creating a new strategy/selector.

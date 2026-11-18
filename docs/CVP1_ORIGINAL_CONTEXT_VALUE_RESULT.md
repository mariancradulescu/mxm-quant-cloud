# CVP1 original complete-policy economic result

Recorded 2026-11-18. Verdict: **CVP1_CLOSED_EXACT_NO_ROBUST_INCREMENTAL_NET**. No promotion, retuning, inversion, original rerun or favorable ablation selection. LPM1 remains closed.

## Original evidence

- Frozen protocol commit: `dc958c847533fc49fbe55520dfd2948a6e7c946b`.
- Implementation: `718c02d1d2993d3c0e9ece0ff1bdcde82203dad8`, PR [369](https://github.com/mariancradulescu/mxm-quant-cloud/pull/369), merged as `2df2a8c13f2cc8b1f5da012864fd5cfe17147b2c`.
- Original [Actions 44162043538](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44162043538): SUCCESS, run attempt 1, source/execution commit `e69ed11a84460889bf701d91c4c85d324dc2a7dd`.
- Public artifact `14365407940`, exact ZIP conserved as [CVP1_ORIGINAL_PUBLIC_44162043538.zip](CVP1_ORIGINAL_PUBLIC_44162043538.zip). Downloaded SHA-256 verified: `a5125582a1cf4690871ad4d7640090c376ea8e85196228bf235d4a25ee7bc569`.
- Encrypted original source artifact `14366230834`, 278338511 bytes. GitHub-reported ZIP digest (not locally decrypted/recomputed): `1baf468b21fd33e9cf008f4d99fe08950f0f38d449faf3d171dbe61828b7fdd9`.
- Native source SHA-256: `ccd0cd7b4c659a24045023475c51680b2c8800d6879f6f74430ed429dcc2fee9`; protocol SHA-256: `c41b3615411c197cce393d580af5dc26517d56dee917f2cc1f3fec497b481759`.
- [Arithmetic audit](CVP1_PUBLIC_ARITHMETIC_AUDIT.json) recomputes all 16 books from immutable trade rows; this is Director arithmetic verification, not the independent auditor or independent market confirmation.

Reproduce without broker access or policy execution:

```sh
python research/audit_cvp1_public.py docs/CVP1_ORIGINAL_PUBLIC_44162043538.zip /tmp/cvp1-audit.json
```

## What was actually investigated

A distinct fitted continuation-value hypothesis combined with separately learned complete-cycle entry NET. FLOW follows aligned impulse/trend; RETURN moves toward H1 equilibrium in a low-efficiency state. Structural stop, ATR protection, observed target, learned HOLD/CLOSE, costs and native common-capital allocation act together. Actual-fill compatibility is checked causally. No universal R:R and no fixed take-profit for FLOW.

New original Pepperstone read-only collection: **3540 requests, 350538 authentic bars and 5039797 side ticks**, across 60 weekdays per instrument. All seven timeframes contribute to the feature state. Shared USD context and tick-volume activity have predeclared ablations. Current contract/margin/funding observations are historical cost scenarios, not historical tariff certification.

| Instrument | M1 | M5 | M15 | M30 | H1 | H4 | D1 | BID ticks | ASK ticks |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | 87490 | 17841 | 6048 | 3126 | 1632 | 696 | 130 | 676095 | 672738 |
| GBPUSD | 87335 | 17805 | 6044 | 3126 | 1632 | 696 | 130 | 993696 | 984191 |
| AUDUSD | 87343 | 17832 | 6048 | 3126 | 1632 | 696 | 130 | 856556 | 856521 |

Population [2026-05-04, 2026-07-27): weeks 1–4 continuation fitting, 5–6 entry fitting, 7–9 residual calibration, 10–12 evaluation (ISO W28–W30). All dates are globally exposed development. Three evaluation weeks cannot establish the required >=12 independent relevant months.

All three continuation models used 21468 oriented transitions and reached the frozen limit of 32 iterations **without coefficient convergence**. This is an additional model limitation, not an instruction to raise the iteration limit retrospectively. Both entry families had the required training/calibration counts; exact coefficients, residual quantiles and counts are in the original.

## Common EUR300 counterfactual books

Each row is a separate alternative; returns are never added. Central/adverse costs reprice the complete adaptive lifecycle, so different exit times can make a particular adverse result slightly higher than central.

| Book | Trades central/adverse | NET central EUR | NET adverse EUR | Adverse weekly trips W28/W29/W30 | HARD21 |
|---|---:|---:|---:|---|---|
| FULL | 11/11 | -0.944422417 | -0.935740571 | 3 / 7 / 1 | no |
| NO_PEER | 4/4 | 1.407599905 | 1.390097192 | 2 / 1 / 1 | no |
| NO_ACTIVITY | 6/6 | -0.697637344 | -0.697637344 | 0 / 6 / 0 | no |
| PROTECT_ONLY | 11/11 | -1.522739128 | -1.531592141 | 3 / 7 / 1 | no |
| SIMPLE | 171/170 | -19.308779760 | -19.759613513 | 64 / 46 / 60 | yes |
| FLOW_ONLY | 0/0 | 0.000000000 | 0.000000000 | 0 / 0 / 0 | no |
| RETURN_ONLY | 11/11 | -0.944422417 | -0.935740571 | 3 / 7 / 1 | no |
| CASH | 0/0 | 0.000000000 | 0.000000000 | 0 / 0 / 0 | no |

FULL ends at **299.064259429 EUR**. Its incremental adverse NET is -0.935740571 versus CASH, +18.823872942 versus SIMPLE, +0.595851570 versus PROTECT_ONLY, -2.325837763 versus NO_PEER and -0.238103227 versus NO_ACTIVITY. Avoiding part of a losing comparator is not positive profit. FULL equals RETURN_ONLY; FLOW contributes no funded trade.

Evaluation contains 663 structurally compatible candidates (260 FLOW, 403 RETURN). FULL has 650 current opportunities after held-symbol exclusion: 92 fail the learned HOLD compatibility condition, 547 fail positive uncertainty-adjusted incremental utility, and 11 become complete funded trades. There are no funded cancellations, unknown lifecycles or uncertain held paths in FULL. Diagnostic candidate paths separately record one causal fill cancellation and nine uncertain evaluation paths; they are not erased from the source census.

## Empirical trade distributions and risk

The native scorecard deliberately leaves inferential trade metrics N/A below 20 completions. The following arithmetic descriptions retain small samples explicitly; they are not qualification. All zero-trade metrics remain N/A. Full distributions, per-family/per-symbol decomposition, MFE/MAE, target R:R, exit counts and weekly values are in the audit JSON and original ZIP.

| Adverse book | n | NET/trade EUR | Win rate | PF | Payoff | Mean R | Worst EUR | ES5% EUR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| FULL | 11 | -0.085067 | 0.454545 | 0.402551 | 0.483061 | -0.462980 | -0.552444 | -0.552444 |
| NO_PEER | 4 | 0.347524 | 0.500000 | 2.651333 | 2.651333 | -0.027891 | -0.552444 | -0.552444 |
| NO_ACTIVITY | 6 | -0.116273 | 0.333333 | 0.121009 | 0.242018 | -0.618038 | -0.252878 | -0.252878 |
| PROTECT_ONLY | 11 | -0.139236 | 0.363636 | 0.137907 | 0.241338 | -0.513407 | -0.552444 | -0.552444 |
| SIMPLE | 170 | -0.116233 | 0.376471 | 0.480290 | 0.795481 | -0.255518 | -1.761722 | -1.178356 |
| FLOW_ONLY | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |
| RETURN_ONLY | 11 | -0.085067 | 0.454545 | 0.402551 | 0.483061 | -0.462980 | -0.552444 | -0.552444 |
| CASH | 0 | N/A | N/A | N/A | N/A | N/A | N/A | N/A |

FULL adverse R quantiles (0/5/25/50/75/95/100%): -1.041912, -1.041912, -1.010400, -0.891125, 0.030322, 0.216308, 0.466240. Its initial target R:R spans 0.390374–5.171534, rather than a universal ratio. R uses the recorded ex-ante risk estimate; latency/gaps can exceed -1R.

FULL: observed floating DD **0.581760%**, peak margin **63.91 EUR**, minimum free margin **234.344720 EUR**, maximum **2 simultaneous positions**. No unknown holding marks; continuous intratick/gap DD is still not certified. Adverse weekly NET is -0.026721 / -0.619661 / -0.289359 EUR; descriptive weekly mean minus 2 SE is -0.654990 EUR. No funded FULL trade closed below 60 seconds; duration range 103.274–4619.677 seconds. This resolves the tested entry-compatibility problem without demonstrating profitability.

FULL exit proportions: protection 7/11, learned nonpositive continuation 2/11, equilibrium target 2/11. These are observed cause frequencies, not independent or uncensored probabilities of eventually hitting every competing SL/TP barrier. Structural/profit protection is combined in the original reason code; no finer decomposition is invented. Average MFE/MAE are 0.000200/0.000275455 quote units; per-symbol values are provided to avoid treating these units as universal pips.

SIMPLE adverse has 13 unknown holding marks and 3 uncertain trade paths: its reported modeled terminal NET is arithmetically settled, but those paths are not execution-certified. Known-mark DD is 6.953208%, peak margin 103.93 EUR and concurrency 3; the full-path native DD/margin scorecard remains N/A. HARD21 is achieved by this losing comparator only, not by a qualifying profitable portfolio.

## Economic diagnosis and distinct next hypotheses

1. **The selected gross opportunity does not cover costs.** FULL adverse gross is -0.100805648 EUR before 0.056800163 spread, 0.201106786 slippage, 0.577021338 commissions and 0.000006637 conversion. Net is already negative without claiming costs are the only cause. SIMPLE gross is -5.719790791 EUR and costs deepen the loss. A distinct future hypothesis is executable cross-sectional displacement relative to its estimated correction range and total round-trip costs, with event-defined opportunity creation rather than another cutoff for CVP1.

2. **Additional context did not demonstrate incremental profit.** FULL is below both NO_PEER and NO_ACTIVITY. NO_PEER's +1.390097192 EUR comes from four trades: one FLOW trade contributes +2.065362561 EUR, while its three RETURN trades sum to -0.675265369 EUR. Mean R is -0.027891, only one of three weeks is profitable, and weekly mean minus 2 SE is -1.139601 EUR. Retaining only that trade/family/ablation would be retrospective selection. A distinct next hypothesis could model multi-instrument relative-price innovations jointly with their unwind and common risk, instead of adding peer trend indicators.

3. **Management helps relatively but the learned value is not reliable evidence of an edge.** FULL improves +0.595851570 EUR over protection-only, yet remains negative in every evaluation week; all continuation fits hit their iteration cap. A distinct next study could learn state-transition/competing-exit distributions with explicit convergence and probability calibration checks before scoring; it would require a new ex-ante hypothesis and independent data plan, not a repaired CVP1 threshold or extra iteration search.

Evaluation Brier/MAE: FULL FLOW 0.260378 / 0.419511 EUR; FULL RETURN 0.242001 / 0.297822 EUR. These diagnostics concern compatible candidate lifecycles, including unfunded overlapping opportunities, and cannot be summed as portfolio profit. Training/calibration Brier are in-sample diagnostics because residual calibration uses those observations; only the chronological evaluation figures are out-of-fit development diagnostics, still not independent confirmation. The original does not preserve per-candidate win outcomes for a reconstructed fitted constant-probability baseline, so no stronger calibrated-prediction superiority is claimed.

## Boundaries and verification

Original ZIP, source-to-economic hash binding, all cash/trade/cost/R identities, weekly counts and eligible native scorecard metrics pass the arithmetic audit. Implementation previously passed the synthetic common-capital lifecycle test, 760 existing native checks and all PR369 checks, including the cTrader read-only build. None of those tests constitutes economic success.

All fills remain explicit observed-quote research models with >=100ms latency; no broker fills or historical tariff continuity are certified. Price break-even protection covers estimated remaining exit costs; sunk entry commission can still leave a small NET loss. Legal-minimum positions cannot be partially reduced below the minimum. Three correlated USD FX instruments are not proof of multi-asset-class diversification. The systemic DD guarantee, robust positive NET, HARD21 and >=12-month independent confirmation are unfulfilled.

**No LIVE/DEMO orders, Cloud activation or permanent external service.** All eight alternatives are conserved, none promoted. Independent auditor verification remains separate.

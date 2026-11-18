# SHD1 genuine H1 + M15 original — source and native C# public receipt readback
**Factual postclosure aggregate readback, 2026-11-18.** Does NOT rerun, retune, invert, amend protocol, read original private market tape, or select a model. AUTHORITY: docs/OWNER_SPEC.md and frozen SHD1 protocol dcddc950cfd7f0211b5ac736d68d511216648504. This is independent aggregation of public original C# score fields, NOT a second predictive model.

## Originals and integrity
- New distinct study PR #380: https://github.com/mariancradulescu/mxm-quant-cloud/pull/380, merged f2baa749bc2a3198e8f4fafa8f99e4d35661df61. AHR1 PR #377-379 remains CLOSED unchanged.
- Exact single-commit OWNER main original intent 92601717a07ceab33526605b677abfe6ccdee5f7.
- Authentic ORIGINAL SHD1 workflow https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44279753820: verify SUCCESS, original-protected-custody-native SUCCESS; broker orders zero; Cloud NOT activated.
- Original GitHub artifact ID **14416088492**, name shd1-authentic-session-multiscale-native-original-public.
- Exact original C# public JSON shd1-original-authentic-native-aggregate.json SHA-256 **96e2264cd02318cc884ddaa756ee209c78860845583d6e24246b4d75ec49ad08**.
- Exact public original source readback shd1-original-source-custody.public.json SHA-256 **c1d88cbd7a45d4789170c1472b10c2427c075cacc6190cbcf5a4032253f01a0c**. Its original C# digest matches the independently computed SHA-256 of the exact zip member. Public original receipt proves unchanged original HXC1 ciphertext hash; no decrypted bars or account ID in the artifact.
- Reused verified original Pepperstone HXC1 read-only source Actions #43817213663; original ciphertext SHA-256 **445195a645f5427a04bb62b8a2b755715226a3893dda27c26ec7c80786c1077d**, HXC1 source protocol SHA-256 **b741165d32f02fa01f0bbeb690acfc52d494c90dd4622c9544cf2fb57317be74**. No new broker request in SHD1, no HXC1 rerun.

## Real source, causal sample geometry, and observed trees
All 12 prespecified source symbols admitted independently in each of TWO resolutions, versus only 5 FX models with real TRAIN support in closed AHR1. The original HXC1 corpus has **70,270 H1** and **70,867 M15** actual completed bars: 141,137 total. No price interpolation across daily/weekend closures. Eligibility requires complete true 3-next-bar price path within split, 12 prior observed bar warmup, and exclusion of within-bar dual barrier ambiguity. No broker fill inferred from high/low.

| Resolution | Symbol-resolution groups with TRAIN/CAL/EVAL support | TRAIN | CAL | Historically exposed EVAL | Real trees with root split |
| --- | ---: | ---: | ---: | ---: | ---: |
| H1 | 12 / 12 | 30,404 | 10,375 | 20,991 | 12 / 12 |
| M15 | 12 / 12 | 30,793 | 15,603 | 20,927 | 12 / 12 |

All 24 TRAIN-fitted trees have actual nonnegative root split with 3-4 leaves; **not** AHR1's uniform root=-1. Example EURUSD H1 root feature 5 UTC session-clock phase threshold 0.75 (18:00 UTC). UK100 H1 root UTC session clock phase at 0.16667 (04:00 UTC). The M15 roots frequently split relative tick-volume activity. This is evidence the nonlinear estimator learned TRAIN class partitions; neither the split nor Brier gain proves profitable LONG/SHORT. Session clock may primarily improve touch-vs-no-touch prediction.

## Matched descriptive multiclass Brier score
Lower is better. All methods scored on the SAME population in each split and resolution; figures are row-weighted postclosure aggregation of per-symbol original public C# fields, not a new separate scorer.

| Resolution/split | PRIOR | Bayes session | Observed state transition | Actual depth-2 tree |
| --- | ---: | ---: | ---: | ---: |
| H1 CAL | 0.645099 | 0.630132 | 0.630046 | 0.624481 |
| H1 EVAL | 0.642687 | 0.623886 | 0.625286 | 0.615733 |
| M15 CAL | 0.635130 | 0.622889 | 0.625668 | 0.620046 |
| M15 EVAL | 0.636169 | 0.628015 | 0.626244 | 0.626676 |

H1 EVAL row-weighted Brier gain versus PRIOR: Bayes **+0.0188005**, state-transition **+0.0174005**, tree **+0.0269537**. M15 EVAL: Bayes **+0.0081539**, state-transition **+0.0099245**, tree **+0.0094927**. These are positive descriptive Brier differences, **not** evidence that trading profitable after execution. Some symbols deteriorate, e.g. H1 AUS200 tree EVAL difference **-0.016393**, and H1 NAS100 Bayes **-0.010538**. EVAL was historically globally exposed; model development and later review make it unsuitable for fresh 12-month independent confirmation. Same-week labels and instruments are dependent; 12 x 2 x 3 model comparisons are multiple tests. Per-symbol 95% normal-reference weekly intervals are not simultaneous, block-robust or multiplicity-adjusted. No statistical discovery certificate.

**Distinct mathematical-family caveat:** Bayes-context and observed-state both use regularized categorical-count estimation with different causal conditioning variables; they are not three wholly independent estimator families. The depth-two TRAIN-quantile tree is genuinely nonlinear and learned structural splits. SHD1 must not be advertised as three unrelated mathematical algorithms or as a hidden Markov model.

## Diagnostic directional policy and HARD21
At the frozen prospective nonfunded rule (direction probability >=0.55 and exceeds opposite probability >=0.10), identical publicly reported EVAL rows generated:
- H1: Bayes-context **39** proposals across all 12 symbols (at most 4 per UTC week), state-transition **11** (at most 1/week), tree **zero**.
- M15: Bayes-context **28** proposals across all 12 symbols (at most 10/week), state-transition **25** (at most 9/week), tree **zero**.

Proposals are NOT legal funded entries, independent unique exposures, verified exits or completed portfolio trips. Each H1/M15 model individually falls short of 21 diagnostic proposals per relevant week, even before accounting for overlapping clocks, margin, risk and cost. Do not sum model proposals as a portfolio or claim HARD21 is mathematically impossible in general. The substantial score improvements plausibly reflect predictability of conditional event/no-touch occurrence and market-session geometry, **not demonstrated directional economic value**.

## Exact bounded verdict and next distinct hypothesis
**SHD1_CLOSED_EXACT_AUTHENTIC_INFORMATION_DIAGNOSTIC_NO_FINANCIAL_QUALIFICATION**. The new session approach resolved the prior artificial coverage exclusion and 24/24 trained nonlinear trees learned. Conditional three-bar barrier-outcome predictability shows descriptive improvement across both original resolutions and most source groups, which warrants sharper CAUSAL directional-vs-NONE uncertainty and independent-window examination. It does NOT identify verified profitable trading decisions at minimum legal broker size.

Not demonstrated: true historical next-executable BID/ASK fills, commission/slippage/swap/FX, common capital EUR300 ledger, NET central/adverse, complete floating DD30, systemic funded HARD21 or genuinely new >=12-month independent confirmation. No broker orders, no LIVE/DEMO, no Cloud activation. All genuine funded metrics are UNKNOWN/N/A, NOT zero. No money may be computed from bar extremes alone.

A **new separate prospectively frozen** economic test, if pursued, should first examine incremental *directional* information versus merely event/hazard prediction and matched funded simple comparators, use genuinely non-exposed chronology where possible, add authentic official M1/quote or lower-level path and original-account legal cost/FX evidence, and validate on the single Core EUR300 ledger. Do not retune SHD1, shift selection thresholds ex post, or promote the exposed UK100/EURUSD tree as a winner.

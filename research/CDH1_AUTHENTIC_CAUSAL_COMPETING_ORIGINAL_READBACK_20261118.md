# CDH1 — authentic original ex-ante competing-directional readback and bounded closure (2026-11-18)

**Evidence class:** factual postclosure public-artifact readback ONLY; original frozen C# study neither rerun, rescored, retuned, inverted nor substituted. Authority: docs/OWNER_SPEC.md OWNER v2.0 and amendments; frozen preimplementation CDH1 protocol commit `b1196ab736f1f95f4476af20dcf8fd1a9944b7fd`. Earlier AHR1 and SHD1 exact studies remain closed, intact.

## Original GitHub evidence / hashes
- Implemented PR [#382](https://github.com/mariancradulescu/mxm-quant-cloud/pull/382), merged at `d4c7235ac7e825f06c4df173510990d8d28c92ef`; all twelve CI runs for final PR HEAD SUCCESS including native Core/Replay/Cloud compile and synthetic ex-ante/censor/ambiguous/softmax self-test. This is SOFTWARE verification only.
- Separate OWNER original main-branch intent `32a658f9b82f933dfb0b3a3c3fad73917d7b49e4`.
- Original protected GitHub [Actions #44287157193](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44287157193), both verify and original-protected-custody-native SUCCESS; artifact **#14419273447**, `cdh1-authentic-competing-directional-native-original-public`. No broker orders, no Cloud activation.
- Exact ORIGINAL C# output `cdh1-original-competing-hazard-csharp-aggregate.json` SHA256 **`bc649527dc73227347a15c2cb56dd0138f411fde4c8111b337ee762355dca3e6`**, independently recomputed from ZIP raw member and equal to custody JSON nativeOriginalCSharpJsonSha256.
- Original public custody file `cdh1-original-source-custody.public.json` SHA256 **`8c37cd90023a91b7dc1e4319358c158e70646b17cd157f7ee18293a860d930c1`**.
- Reused ORIGINAL verified HXC1 read-only bound Pepperstone source [#43817213663](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43817213663), authentic ciphertext SHA256 **`445195a645f5427a04bb62b8a2b755715226a3893dda27c26ec7c80786c1077d`** and original broker-source protocol SHA256 **`b741165d32f02fa01f0bbeb690acfc52d494c90dd4622c9544cf2fb57317be74`**. Original account raw protobuf readback verified, no original plaintext bars publicly released, no new broker request in CDH1.
- **141,137 original completed OHLC/tick-volume bars**, 70,270 H1 and 70,867 M15, across all 12 predeclared sources and both resolutions. Tick volume is not exchange-traded volume.

## Causal population and censor/ambiguity transparency

The original decision population is admitted ONLY at each real bar close using current and past 12 observed bars, never future 3-bar availability/outcome. The following is *original* C# readback, not an after-the-fact new scoring run:

| Resolution | Cohort | EX-ANTE clocks | Observable risk steps | Censored clocks | Dual-touch ambiguous clocks | First UP | First DOWN | 3-bar NO_TOUCH |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| H1 | TRAIN | 34,554 | 61,827 | 2,380 | 1,096 | 12,224 | 12,140 | 6,714 |
| H1 | CAL | 11,723 | 20,938 | 841 | 309 | 4,120 | 4,244 | 2,209 |
| H1 | EVAL | 23,837 | 42,383 | 1,764 | 770 | 8,268 | 8,690 | 4,345 |
| M15 | TRAIN | 21,509 | 39,842 | 410 | 548 | 8,068 | 8,355 | 4,128 |
| M15 | CAL | 5,446 | 9,990 | 119 | 125 | 2,098 | 2,105 | 999 |
| M15 | EVAL | 43,756 | 80,784 | 815 | 883 | 16,717 | 17,409 | 7,932 |

All **24/24** symbol-resolution cohorts passed pre-score EX-ANTE TRAIN/CAL/EVAL support; EVAL spans exactly eight weeks M15 and 18 ISO weeks H1. Genuine future censoring is not discarded; dual-touch is NOT assigned a fabricated intrabar UP or DOWN order. Training fits use only the observable risk sets and a strict split boundary. This corrects the exact source-selection failure revealed in SHD1, but does not prove independent non-informative censoring or profitability.

## Predictive results, score interpretation

All numbers below are row-weighted descriptive aggregations of authentic native C# **observed partial** negative log-likelihood per EX-ANTE decision, scored on exactly the same clocks and observed event-risk steps. Lower is better. They are NOT original full outcome Brier and do not identify missing future price paths.

| Period EVAL | PRIOR | Grouped Bayesian context hazard | L2 multinomial softmax cause hazard |
|---|---:|---:|---:|
| H1 (23,837 clocks) | 1.703038 | 1.639060 | **1.600732** |
| M15 (43,756 clocks) | 1.804812 | 1.764650 | **1.743921** |

Observed partial log-likelihood improvement vs train-only PRIOR: H1 Bayesian +0.063978 and Softmax +0.102306; M15 Bayesian +0.040162 and Softmax +0.060890. This improvement survives including censor/ambiguous clocks in the **decision denominator**, but observed likelihood has no contribution for genuinely unobserved future risk steps; it does NOT certify full 3-bar price outcome accuracy. Both models learned causal conditioning structure; two distinct fitted forms (count posterior vs regularized softmax), not arbitrarily renamed HMM. Model EVAL periods and HXC1 original history are already globally exposed; 12*2*2 tests, overlapping decision horizons and cross-market calendar dependence invalidate naive winning-model significance and prevent 12-month independent confirmation.

## Original nonfunded directional decisions

Four original predefined **descriptive-only** candidate-gate pass flags occurred, ALL on M15, eight EVAL weeks, with at least 21 *unfunded proposals* in each week. Exact values below include only FIRST-TOUCH directional status, not money:

| M15 model | EX-ANTE diagnostic proposals | Direction wins | Opposite FIRST touch | No-touch | Ambiguous | Censored | Matched momentum wins | Matched contrarian wins |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| AUDUSD softmax | 446 | 214 | 179 | 32 | 20 | 1 | 175 | 212 |
| EURUSD Bayesian | 1,033 | 377 | 346 | 296 | 8 | 6 | 311 | 366 |
| GBPUSD softmax | 985 | 446 | 401 | 114 | 21 | 3 | 398 | 437 |
| JPN225 softmax | 239 | 87 | **97** | 20 | 24 | 11 | 79 | 72 |

These four pass flags are **NOT financially valid edges**, broker-financed trades, independent wins, or model promotions. JPN225 is a decisive warning: its descriptive gate passes versus simple matched comparator *counts*, yet opposite first-touch outcomes **exceed** correct outcomes (97 vs 87); economic desirability is not established. Even AUDUSD/GBPUSD signed outcome advantages are small and cannot pay demonstrated bid/ask, fees, slippage or margin because those are unverified; NO_TOUCH outcomes require unknown exit economics. EURUSD Bayesian has many no-touch events, and lower-bound success only 377/1033. Predictions are vulnerable to overlap and multiplicity, with M15 CAL only ONE week. Do NOT add model signal counts across markets or treat proposal count as systemic funded HARD21.

Other original EVAL diagnostics, all-symbol sums:
- H1 Bayesian 754 unfunded proposals / 258 wins / 210 opposite; H1 softmax 1,143 / 517 / 453.
- M15 Bayesian 1,468 / 565 / 507; M15 softmax 3,111 / 1,352 / 1,294.
- Most instruments/model cases do not pass the frozen **joint** descriptive gate; no all-week funded common book is demonstrated.

## Exact verdict and economic next admission

**CDH1_CLOSED_EXACT_AUTHENTIC_EXANTE_COMPETING_DIRECTION_DIAGNOSTIC_NO_FUNDED_EDGE_QUALIFICATION**

CDH1 solved the specific future-observability admission design error (population includes censored, ambiguous and terminal clocks) and demonstrated real historical improvements in a *partial observed-data event likelihood*, with a small set of matched nonfunded directional candidate gate passes. It did NOT demonstrate robust causal signed economic alpha, simultaneous legal capital feasibility, adversity NET in EUR, executed HARD21 or independently confirmed performance. Historical OHLC extrema do not identify authentic future bid/ask fills or the 300-EUR account ledger.

Before any financial admission, the DIRECTOR must distinguish true direction vs event occurrence/no-touch, address informative censoring and calendar overlap, demonstrate sensitivity/multiplicity and genuinely NEW chronological confirmation, and obtain original-account authentic legal unit/margin, historical BID/ASK/tick, slippage/fees/FX/rollover and continuous full-position path; then use the **single authoritative Mxm.Core EUR300 funded ledger** with funded simple controls and conservative adverse NET/DD/HARD21. No need to wait for prior advantage before a justified fresh read-only collection. No LIVE/DEMO, orders, Cloud activation or permanent external service.

Report and code immutable; independent AUDITOR reviews originals. OWNER decides. The four exposed candidate flags must not be optimized or promoted retrospectively.

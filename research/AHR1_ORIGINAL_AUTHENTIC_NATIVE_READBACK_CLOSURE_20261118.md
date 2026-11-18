# AHR1 original broker H1 native C# readback — factual closure (2026-11-18)

**Evidence class:** after-the-fact readback of NEW original, prospectively frozen AHR1; not a second scoring run, rerun, retuning, reversal, or economic promotion. OWNER_SPEC v2.0 and 2026-11-18 corrections remain authoritative.

## Immutable links, hashes, and custody

- Frozen protocol **841dab0e62d58f2f988cec7c8f2307fa413d54c8** predates C# implementation and scoring; research [PR #378](https://github.com/mariancradulescu/mxm-quant-cloud/pull/378) merged at **8ea83966b9b5e96c67786aefd9047c444c5093e1**.
- Original AHR1 one-time protected workflow [Actions #44275773380](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44275773380) **SUCCESS**, artifact **#14413284901** `ahr1-authentic-pepperstone-h1-native-aggregate-original`, with files `ahr1-original-authentic-h1-native-public.json` and `ahr1-original-source-custody.public.json`.
- Authentic HXC1 bound Pepperstone original run **43817213663**, raw source ciphertext SHA-256 **445195a645f5427a04bb62b8a2b755715226a3893dda27c26ec7c80786c1077d**, original source protocol SHA-256 **b741165d32f02fa01f0bbeb690acfc52d494c90dd4622c9544cf2fb57317be74**. Cryptographic original-account protobuf readback `HXC1_ORIGINAL_ACCOUNT_RAW_BARS_CRYPTOGRAPHICALLY_REBUILT`: TRUE.
- Original AHR1 native public output SHA-256 **16950d830897680c2e24692210d341443a00a4c1e9e2adab6906dbd593287d31**; separately recomputed SHA-256 of exact artifact JSON bytes matches public custody receipt. No original raw market bars or account secrets published.
- `OrdersSubmitted=0`, `CloudActivated=false`, `NetEur=null`, `EconomicQualification=false`. No original broker fills or certified continuous floating risk.

## Authentic source usage

Exactly **70,270 completed H1 bars** from all 12 predeclared symbols; 22,223 event rows were labeled by code, but **88 AUS200 EVAL rows had zero TRAIN rows** and are **not a learned-model test**. No claim of valid 12-class comparison.

| Symbol | Original H1 bars | TRAIN | CAL | EVAL | Missing contiguous-24h warmup |
|---|---:|---:|---:|---:|---:|
| AUDUSD | 6,190 | 2,188 | 740 | 1,520 | 1,274 |
| AUS200 | 5,598 | 0 | 0 | 88 | 5,478 |
| EURUSD | 6,190 | 2,166 | 733 | 1,512 | 1,274 |
| GBPUSD | 6,190 | 2,181 | 739 | 1,518 | 1,274 |
| GER40 | 5,146 | 0 | 0 | 0 | 5,122 |
| JPN225 | 5,882 | 0 | 0 | 0 | 5,858 |
| NAS100 | 5,883 | 0 | 0 | 0 | 5,859 |
| UK100 | 5,040 | 0 | 0 | 0 | 5,016 |
| US500 | 5,884 | 0 | 0 | 0 | 5,860 |
| USDCAD | 6,190 | 2,178 | 749 | 1,520 | 1,274 |
| USDJPY | 6,190 | 2,142 | 734 | 1,515 | 1,274 |
| XAUUSD | 5,887 | 0 | 0 | 0 | 5,863 |

The 24 *consecutive clock-hour* requirement made symbols with regular session closures ineligible, most critically all indices and XAUUSD. **This is an AHR1 SOURCE-WARMUP DESIGN ERROR relative to the OWNER multi-class research objective; it is not proof that those underlying markets lack signals**. No after-the-fact change to AHR1 is authorized or made.

## Predictive outcomes — five predeclared FX symbols WITH training support

All numbers below are from the original native output, independently aggregated across the same valid five symbols. Identical chronological test rows for all four models: **TRAIN 10,855; CAL 3,695; EVAL 7,585**. Brier score is multiclass (UP_FIRST, DOWN_FIRST, NO_TOUCH), lower is better.

| Model | TRAIN Brier | CAL Brier | EVAL Brier | EVAL minus prior |
|---|---:|---:|---:|---:|
| Train-only PRIOR | 0.54874986 | 0.54958358 | 0.53989137 | 0 |
| Bayesian context | 0.54745368 | 0.55028422 | 0.53943255 | -0.00045882 |
| Observed volatility-state transition | 0.54589090 | 0.54753364 | 0.53957940 | -0.00031197 |
| Depth-2 nonlinear regularized tree | 0.54874629 | 0.54958491 | 0.53983937 | -0.00005200 |

These are **small descriptive differences on historically exposed, clustered overlapping labels**, with no blockwise error bound or independent future confirmation. Bayesian context is **worse** than PRIOR in CAL; model rankings change. Do not claim statistical significance or selection of a winning method. NO algorithm met the frozen proposed long/short diagnostic thresholds on TRAIN, CAL or EVAL: **zero proposed signals**, hence **zero funded trips are NOT inferred** (no funded simulation was attempted). Opportunity frequency, economic NET/risk and HARD21 remain not demonstrated and/or unknown, not zero modeled PnL.

## Exact conclusion / forward requirement

**AHR1 CLOSED_EXACT_NO_PREDICTIVE_OR_ECONOMIC_QUALIFICATION.** Original receipts and code remain untouched. The two immediate demonstrated impediments are:
1. **Study geometry:** artificial contiguous-24h warmup excludes noncontinuous classes, despite ample original bars. A *new distinct, ex-ante protocol* must represent actual official market sessions and elapsed-time gaps without forward filling, not retroactively rescore AHR1.
2. **Weak/restricted predictive evidence:** three mathematically distinct methods show only tiny, unstable improvement against the same PRIOR on trained FX; no predeclared actionable proposals.
3. **Execution evidence missing from H1 price bars:** genuine historical broker BID/ASK, minimum funded contracts/fees/FX, execution path, shared EUR300 capital, margin, concurrent positions and floating drawdown remain unproven. Do not manufacture NET EUR, HARD21 or DD30.

Do not relaunch HXC1 or AHR1, invert signals or retune exposed outcomes. A future source-and-session-aware original study is permitted when prospectively frozen as a **distinct economic mechanism**; official read-only collection can occur whenever required. Owner objective remains one C# cBot, capital EUR300, robust adverse NET > 0, systemic HARD21, floating DD <=30%, and >=12 months truly independent confirmation. AUDITOR independently verifies GitHub LIVE and all original receipts; OWNER decides.

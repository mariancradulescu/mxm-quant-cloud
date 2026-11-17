# SDP2 F1 — systematic action-value discovery: original result

**Director verdict:** `SDP2_F1_EXPOSED_ACTION_VALUE_NO_VALUE_VS_KNOWN_COST_BASELINE_NO_PROMOTION`.

The new chronological, pooled nonlinear model was actually trained and evaluated. It improved NET prediction error relative to the simpler fitted own-price model, but **failed to beat the prespecified zero-price-move plus scenario-cost reference at either horizon**. The apparent improvement over weaker comparators is not evidence of a usable price-prediction advantage. The exact SDP2 configuration is closed without promotion or retrospective tuning. This does not close the systematic programme or prove that all information in these sources is unpredictable.

## Protocol, original runs and correction

- Protocol frozen separately at `c7891655084de2f87dbf9af41f841cf6f1d0a41a`, before implementation/source scoring: `research/SDP2_SYSTEMATIC_ACTION_VALUE_PROTOCOL_20261117.md`, SHA256 `cefbda37bfa7936675ad18ce8396d3e96a8a2f393071000894769f8e08156945`.
- [PR #352](https://github.com/mariancradulescu/mxm-quant-cloud/pull/352) implemented the programme. Pre-source A1 registered the cost-only comparator and preserved the original conversion wedge. All model families, hyperparameters and acceptance thresholds remained frozen.
- First [Actions #44037808869](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44037808869) completed, but its EUR evidence is **INVALID_SOURCE_PRICE_UNITS**. Code inspection while its source job was waiting identified that the existing decoder retains Spotware OHLC integers at 100000 units per price. Direct use in cross-currency EUR arithmetic was wrong. This was identified and corrected before inspecting SDP2 scores, not after selecting a favorable result.
- [PR #353](https://github.com/mariancradulescu/mxm-quant-cloud/pull/353), code `4d6aca56c4f63b4885f1fe268df2e73012ca5db0`, converts OHLC to physical prices only after authentic raw-source reconstruction. Raw source, predictor design, universe, clocks, model complexity, thresholds and original attempt remain unchanged. Six local/CI tests include all currency routes and Python-label/native-EUR settlement parity; existing 751 native checks passed.
- Corrected original [Actions #44038569445](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44038569445), attempt 1, executable HEAD `4080cf13a18b79589c70b2f8765b5529de9feb2f`: **SUCCESS**.
- Corrected public artifact [#14308483122](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44038569445/artifacts/14308483122), original ZIP SHA256 `309e0feb37dd048c2c934eb643726fbe8daf63f025b67d4a939230d2a239bfa5`; original `sdp2-original-public.json` SHA256 `f48a81fc6be4052d8273b2fc336d5512bcd1636c791a14ef45e8341c2700d931`. Downloaded bytes match the actual upload/job logs.
- Corrected encrypted native inputs artifact `14308812106`, ZIP digest reported by original uploader `579e17a7299cf669f52b6a7d97d8d9778c731d42fc40fb38b17bc4323eaf5b5f`. These are derived private replay inputs, NOT a new broker collection. No protected raw data were published.
- Invalid first public artifact `14308411761`, original ZIP SHA256 `a87b3709478d6288bb11b4a43ca70d58ad0bfd9bec32cbfc1c6d4222e170ec57`; original JSON SHA256 `4a044f31b0643cb3400f44332628c04b447300f535f3bc0922a871cd7cc63386`. Its encrypted derived-input artifact `14309145098` is separately retained. Neither first-attempt economic output nor a favorable subset is reused as evidence.

## Source, causal observations and models

The original BDP1/AIP1 account/protobuf/ciphertext readbacks reconstructed **836,087 authentic M5 bars**, 12 instruments and 166 original cost contexts. Original source runs: `41724643418` and `41735441128`; ciphertext SHA256 respectively `e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370` and `fa684ca1de58c6d1e8bdee410834855d05389af0c0ae4523b095367dce0e5331`.

All available symbols in this annual panel were included: AUDUSD, AUS200, EURUSD, GBPUSD, GER40, JPN225, NAS100, UK100, US500, USDCAD, USDJPY, XAUUSD. This is source coverage, not a universal 12-symbol cap. Other archives and official information channels have **not** yet been assimilated by this execution.

Completed UTC M15/H1/H4 aggregates supplied 42 causal features: candle geometry, normalized returns, efficiency, volatility/range, native tick activity, gaps, native clock and all available synchronized peer context. Every weekday hour was scheduled, with 60m/240m horizons. Missing history and future outcomes were counted separately. No news or other externally unavailable cBot input was used.

| Chronology | Scheduled symbol×hour×horizon slots | Feature known | Feature unknown | Label known | Future outcome unknown after known feature |
|---|---:|---:|---:|---:|---:|
| First 26 weeks | 74,880 | 57,570 | 17,310 | 50,553 | 7,017 |
| Following 26 weeks | 74,880 | 59,588 | 15,292 | 51,570 | 8,018 |
| Total | 149,760 | 117,158 | 32,602 | 102,123 | 15,035 |

Four fixed information sets were refitted weekly: FULL, NO_PEERS, NO_ACTIVITY and OWN_PRICE, plus training-only PRIOR and exact CASH. The learner used 16 depth-2 boosted trees, fixed 0.1 step, train-only quartile splits, 128-row minimum leaves and 32-weight shrinkage. The four targets are central/adverse LONG/SHORT minimum-volume NET, normalized by causal notional/volatility. CASH is zero by definition. Every training/calibration label had matured with a four-hour embargo; the latest four past weeks were reserved for residual calibration and purged from fitting.

**104 weekly fitted models** and **260 week×horizon×variant diagnostic panels** are preserved, not merely pass/fail totals. C# arithmetic reproduced all 104 sampled model evaluations with **maximum absolute difference 0**. All 52 source weeks were globally exposed development material. The later 26 weeks are chronological out-of-fit evaluation for this learner, **not independent project confirmation**.

## What was learned, and what was not

The following are label-count-weighted errors, averaging the two **adverse NET action targets**. Lower MSE is better. The reference predicts zero price movement and deducts the already declared conditional cost scenario; it does not predict a future price direction.

| Horizon | Fully known evaluation labels | FULL MSE | OWN_PRICE MSE | PRIOR MSE | Zero movement + scenario costs MSE |
|---|---:|---:|---:|---:|---:|
| 60m | 27,608 | 2.130180 | 2.162990 | 2.180126 | **2.086487** |
| 240m | 23,962 | 2.636375 | 2.646097 | 2.649286 | **2.622372** |

- FULL improved over OWN_PRICE in 26/26 weeks at 60m and 25/26 at 240m. The prespecified descriptive Bonferroni lower weekly MSE benefits were `+0.027231` and `+0.006746`; these remain exposed, serially dependent diagnostics, not independent qualification.
- Against the stronger zero-movement/cost reference, FULL improved in **0/26 weeks at 60m** and **1/26 at 240m**. Mean weekly benefits were **−0.043643** and **−0.014018**. Both first/last 13-week means were negative at both horizons. Reporting only the own-price comparison would overstate the result.
- Removing peer information changed neither the executable fitted tree functions nor the recorded predictions/errors at any weekly fit. **No peer feature was selected in any FULL tree.** This is a finding about this frozen shallow learner and these three peer summaries, not proof that all intermarket information is worthless.
- FULL used H1 log-volatility in 451 of 1,248 splits and horizon in 393; together these are 67.63% of splits. Some geometry/trend features were also used. Feature counts alone do not establish economic causation. The cost-reference comparison prevents attributing predictable cost/normalization effects to price alpha.
- FULL action-positive Brier scores were `0.224799` (60m) and `0.243059` (240m), versus PRIOR `0.226080` and `0.243461`. These concern **NET-positive action outcomes**, not a balanced up/down-price contest; comparison to 0.25 alone would be misleading. The receipt preserves five probability calibration bins per action, week and horizon.
- Positive realized conditional opportunities existed: among complete labels, LONG/SHORT adverse NET were positive in **34.94% / 33.86%** at 60m and **42.43% / 40.57%** at 240m. Those are overlapping counterfactual observations, not funded trades. The learner did not identify a positive expected-NET subset prospectively.

A post-result, read-only check of exported coefficients gives a stronger diagnostic than rejection counts: for each fitted FULL model, initial output plus the sum of every tree's maximum leaf contribution bounds every possible input's output from above. Across all 26 fits, even the largest such adverse bounds were **−0.056514 LONG** and **−0.118802 SHORT** in normalized units. Therefore **these fitted functions cannot emit positive adverse expected NET**, even before any risk/uncertainty gate. This is a mathematical property of the actual fitted coefficients, not a universal restriction on the model class or market information. No leaf, threshold, learning rate or penalty is changed after this finding.

## Conditional common-capital result and its limits

Each named counterfactual starts once at EUR300; books are never summed. `NativeFundedSession.DecideResearch`, the existing selector and common ledger were called. Evidence flags remain exploratory/unqualified. Actual source forecasts supplied no positive-adverse candidate: the native cycle was invoked 2,941 times per non-CASH policy **with no admissible positive forecast offered**. This does not demonstrate active financing or allocation skill.

| Policy | Central conditional NET EUR | Adverse conditional NET EUR | Complete funded modeled roundtrips | Final cash EUR |
|---|---:|---:|---:|---:|
| FULL | 0 | 0 | 0 | 300 |
| NO_PEERS | 0 | 0 | 0 | 300 |
| NO_ACTIVITY | 0 | 0 | 0 | 300 |
| OWN_PRICE | 0 | 0 | 0 | 300 |
| PRIOR | 0 | 0 | 0 | 300 |
| CASH | 0 | 0 | 0 | 300 |

All 26 predeclared evaluation weeks, ISO 2026-W19 through W44, have zero completions. **HARD21 was not achieved.** There are no open/pending positions, top-ups or resets. Sampled drawdown is zero because exposure is zero; this is **not** a demonstration of an active portfolio respecting maximum 30% continuous floating drawdown.

Historical bid/ask at every decision, historical tariff continuity and actual fills are not available. Price, spread/slippage, commission and FX conversion inputs are explicitly conditional scenarios sourced from bars/current original terms. Central/adverse books are scenario-specific counterfactual policies, not an assumed adverse revaluation of identical active trades. No broker execution profit is certified. Here all books are CASH, so the zero arithmetic is exact but has no positive economic value versus CASH.

## Reproducible receipt reconciliation and decision boundary

`research/sdp2_receipt_audit.py` reads the unchanged original corrected ZIP. It verifies source/code/protocol hashes, matched denominators, original native cash/closed-fragment identities, weekly completions, the no-peer executable-tree identity and the negative fitted upper bounds. It calls no source collector, model trainer or portfolio replay. Derived output: `docs/SDP2_F1_ORIGINAL_RECEIPT_RECONCILIATION_20261117.json`. This is the Director's reconciliation, **not the separate independent AUDITOR's acceptance**.

Preserve both attempts and the exact corrected original. Do not retune SDP2 or select a favorable week, asset or family. No positive price-information value beyond the declared cost reference, independently confirmed NET EUR, active funded diversification, HARD21 or continuous-DD qualification has been established. The result rejects this exact fitted research configuration; it does not justify terminating systematic discovery or requiring a predictor to be profitable before researching it.

No new broker request, LIVE/DEMO order, Cloud activation, cBot or permanent external service was introduced.

# LPM1 original lifecycle research — exact negative result

Verdict: **LPM1_CLOSED_EXACT_NO_POSITIVE_INCREMENTAL_NET**. No promotion, inversion, retuning or research rerun.

The contextual and pooled native selectors both remained in cash: zero financed entries, zero incremental EUR NET, EUR300 final cash. Six prespecified active counterfactual portfolios were also executed, all negative after costs. They are mutually exclusive uses of the SAME EUR300; their trades, cash or returns must never be added.

## Original execution and custody

- Original run: [44090751371](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44090751371), SUCCESS.
- Original executable commit: `835b56cce3794d9eec276d773b0f5de7e9a3a9f2`.
- Protocol commit `64c2f7a90cbe82521a73d333a643eb20aec29285` predates implementation `8385db699766e1006c3e91c437d4eafa9f06712c`; PR #367 integrated at `8d729c2fd4a814a2c7a560415855b2c7cf2022fc`.
- Public artifact: `14332790979`, ZIP SHA256 `cfb7398418351a797657d373ad5d27c416fa4fb63ef56a5d5cee2af9798cdd04`. The exact original ZIP bytes are conserved as [LPM1_ORIGINAL_PUBLIC_44090751371.zip](LPM1_ORIGINAL_PUBLIC_44090751371.zip).
- Original encrypted source artifact: `14332631701`, 115730693 bytes, ZIP digest reported by GitHub and upload log `5ce6ee3c3f77ac9cff5108df89dc724678c064816e01816b3286a76a33196a55`. Its private plaintext was not exported to the OWNER or this workspace.
- Native input SHA256: `c91f5162b44bb1c565f41689ced6d4516042463a0789d328d8c0b940c680dbe3`; C# independently hashes the same native input. Native input ciphertext SHA256: `fed4da4a6cba379a13a0c8c93ef72d38b2d3f3cf93fd8cb7f557e58bc0320560`.
- Original economic JSON SHA256: `fe6bb4daa21a0fb89f3635c022c1b24168eb9810f575fbe399e92dd94ce0a033`.
- Original source JSON SHA256: `c651ed1f2164fc1843f0d98fa281d21f25d340bcc8fc4cb2cc1d4c4793cb8598`.
- 1781 post-authentication read-only requests; 87379 M1 bars; 17537 M5 bars; 1126172 BID ticks + 1125641 ASK ticks = 2251813 side ticks over60 weekdays. M1 is retained source evidence; features use completed M5/M15/H1 views and exits use authentic tick paths.
- Original account authentication and read-only request guard succeeded. Zero submitted orders; no Cloud activation.

## Frozen comparison and economic results

Source calendar: 2026-08-17 through2026-11-09 exclusive. Six training weeks, three calibration weeks, three evaluation weeks (W43/W44/W45). Every week has60 scheduled candidates. There are720 candidates and4320 action labels:4297 complete/unambiguous,23 unknown or uncertain. All1080 evaluation action labels are complete/unambiguous. No selected fixed-control trade is marked uncertain or unsettled. All calendars are globally exposed development, not independent confirmation.

Each active control uses one current legal minimum position on EURUSD, the existing native ledger and current margin/cost terms. Primary contextual/pooled selection uses the existing native risk/orchestrator/session. Controls are diagnostics, not claims of economic-selector admission. No fixed5/30/60/120-minute target horizon is used.

| Policy | Trades | NET central EUR | NET adverse EUR | Adverse final capital EUR | W43 / W44 / W45 completed |
|---|---:|---:|---:|---:|---|
| CONTEXT | 0 | 0.000000 | 0.000000 | 300.000000 | 0 / 0 / 0 |
| POOLED | 0 | 0.000000 | 0.000000 | 300.000000 | 0 / 0 / 0 |
| CASH | 0 | 0.000000 | 0.000000 | 300.000000 | 0 / 0 / 0 |
| VOL_LONG | 63 | -8.496946 | -8.496946 | 291.503054 | 23 / 21 / 19 |
| VOL_SHORT | 62 | -0.142324 | -0.151255 | 299.848745 | 23 / 19 / 20 |
| STRUCT_LONG | 145 | -10.598619 | -10.660921 | 289.339079 | 50 / 46 / 49 |
| STRUCT_SHORT | 144 | -8.571647 | -8.660702 | 291.339298 | 45 / 53 / 46 |
| ADAPT_LONG | 148 | -13.435212 | -13.488583 | 286.511417 | 50 / 47 / 51 |
| ADAPT_SHORT | 141 | -7.605351 | -7.694445 | 292.305555 | 45 / 51 / 45 |

## Trade distributions and risk

Full per-trade NET/R values and seven quantiles are in each original `Books.*.NetDistribution` / `RDistribution`. Initial stop-risk and reward/risk observations are retained in admissions. R is NET divided by the risk estimated BEFORE fill; positive mean R cannot override negative common-capital EUR NET. Cash-policy trade metrics are undefined, not a0% win rate.

| Active policy (adverse) | Expectancy EUR | Win rate | Profit factor | Mean R | Worst trade EUR | Sampled floating DD |
|---|---:|---:|---:|---:|---:|---:|
| VOL_LONG | -0.134872 | 34.92% | 0.657197 | -0.222918 | -0.915566 | 3.8423% |
| VOL_SHORT | -0.002440 | 48.39% | 0.992797 | 0.005870 | -0.941024 | 1.9831% |
| STRUCT_LONG | -0.073524 | 11.72% | 0.438728 | -0.184894 | -0.740624 | 4.1216% |
| STRUCT_SHORT | -0.060144 | 18.06% | 0.566110 | -0.128557 | -1.258600 | 2.9268% |
| ADAPT_LONG | -0.091139 | 13.51% | 0.331955 | -0.147275 | -0.733527 | 5.1376% |
| ADAPT_SHORT | -0.054571 | 17.73% | 0.604426 | -0.085287 | -0.848333 | 2.6544% |

All active controls have peak current-modeled margin EUR33.33. Detailed minimum free margin, five-percent expected shortfall, loss streaks, capital return, distributions, weekly NET and descriptive weekly mean minus2 SE are conserved in the original scorecards and [public arithmetic audit](LPM1_PUBLIC_ARITHMETIC_AUDIT.json). Every active policy has a negative weekly mean-minus2-SE. STRUCT/ADAPT controls exceed21 completed trips in each evaluated week but lose money; VOL controls fail at least one week. The selected strategy has zero trips. Thus no profitable systemic HARD21 demonstration exists.

Floating-DD figures are sampled conditional liquidation-equity statistics, not continuous risk certification. The existing ledger marks floating slippage using the entry slippage allowance; actual modeled close fills use current exit slippage. This is an additional limitation of these floating-DD statistics, not a guarantee of the30% bound. No terminal NET is affected by this reporting limitation. No policy approached30% sampled DD, but no continuous or independent risk certificate is claimed.

## Predictive information versus executable value

Evaluation Brier averages over the six equal-size action populations: context0.17045423698130116 versus pooled0.18240048283636767. Context improves Brier in four of six actions. Mean absolute EUR error is slightly worse overall: context0.33983778603470766 versus pooled0.3394655285712311 (only two of six actions improve). These descriptive classification improvements do not establish positive trade expectancy. Both selectors reject all1080 action offers for `CONDITIONAL_ESTIMATE_NO_POSITIVE_UNCERTAINTY_ADJUSTED_INCREMENTAL_UTILITY`; there is no margin-based explanation for the primary zero-entry result.

## Three observed failure causes and prospective implications

1. **Entry/invalidation incompatibility in active controls.** Fixed long/short controls can enter when the already-closed M15 direction opposes the position. STRUCT/ADAPT then requests an immediate close; this is the frozen rule, not a software exception. The counts and durations below expose it. A genuinely distinct future design must establish entry/invalidation coherence ex ante. Do not remove these losing trades, reclassify the rule as a software bug, or rescore a repaired LPM1 as fresh evidence.

| Adverse policy | Regime-invalidation exits | Trades closed under60 seconds | Median holding seconds |
|---|---:|---:|---:|
| STRUCT_LONG | 122 | 93 | 1.5630 |
| STRUCT_SHORT | 121 | 87 | 1.6915 |
| ADAPT_LONG | 119 | 90 | 1.5840 |
| ADAPT_SHORT | 114 | 84 | 1.6530 |

2. **Costs consume the small positive gross outcomes.** VOL_SHORT adverse has gross EUR4.483034943559 but commission EUR3.321563418362, slippage EUR1.116158774460 and spread EUR0.196506455904, plus conversion effects, leaving NET EUR-0.151255079641. STRUCT_SHORT and ADAPT_SHORT also have positive aggregate gross and negative NET. Future hypotheses need prospective evidence of economically sufficient movement relative to turnover/cost; no tariff relaxation or favorable inversion follows.

3. **Context predicts losing/winning classifications better without producing useful positive action value.** The Brier gain does not translate to EUR MAE or uncertainty-adjusted admissions. Future distinct research should test information that changes the complete lifecycle value distribution, not treat indicator implementation or classification accuracy as economic success.

These are diagnostics of this exact study, not rejection of all ATR/SL/TP/trailing, EURUSD, price data or adaptive policies. No new hypothesis is silently promoted or launched by this closure.

## Reproducibility and boundaries

`python -m research.lpm1_receipt_audit economic.json audit.json` reads only the conserved original public JSON. It recomputes cash/trade NET, weekly closures, initial-risk R, expectancy, win rate, profit factor and incremental contextual-minus-pooled/cash. It does not invoke source collection, forecasts or replay. The audit passed; source-price/fill causality still requires the independent auditor to inspect the encrypted original source in its protected environment.

Validation before original execution: Release build, native end-to-end18-book synthetic test including135 contextual funded synthetic trades,760 native checks, OWNER verification and successful PR CI. These synthetic values are not original economic evidence. Original run and artifacts above are distinct.

Official capability references checked2026-11-17: [historical ticks and hasMore](https://help.ctrader.com/open-api/symbol-data/), [message timestamp/pagination contract](https://help.ctrader.com/open-api/messages/), [native SL/TP/trailing capabilities](https://help.ctrader.com/ctrader-algo/references/General/Robot/ModifyPosition/). No trading API was invoked.

Current tariffs/margin are conditional historical scenarios, quotes are not broker fills, same-millisecond ordering and missing paths are disclosed, and three evaluation weeks are not twelve months or independent confirmation. Final cBot qualification, robust positive NET, continuous30% DD and systemic HARD21 remain undemonstrated.

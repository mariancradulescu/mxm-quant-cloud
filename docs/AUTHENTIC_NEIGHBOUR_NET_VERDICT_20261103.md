# Authentic H1 conditional-neighbour selection — frozen verdict (2026-11-03)

## Evidence and provenance
The already-authorised [GitHub Actions run #41592777895](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41592777895) completed **SUCCESS** on main `5d3f17e44008312d2f9159b6db4d930ba28c9d75`. The protected `collect` job obtained original Pepperstone Europe SCOPE_VIEW H1 data and bid/ask event quotes; independent `custody` job **125774103667** decrypted and recomputed the native C# result, confirming exact parity. Sealed ciphertext SHA256: `52a455f8845d90c76f5de67ea3c61331750851bc4ce1cd6e69578ca0e4f4f685`. Original encrypted data remains in the protected Actions artifact, not this repository.

Frozen protocol: [PR #20](https://github.com/mariancradulescu/mxm-quant-cloud/pull/20) and [H1 conditional-neighbour specification](FROZEN_CALIBRATED_NEIGHBOUR_FX_20261103.md). Each of EURUSD, USDJPY and USDCAD contains **6,283 authentic H1 bars** over **370 observed calendar days**. This is distinct from the ~14-day M15/H1 coverage in the earlier 432-cell study. Full elapsed history is not proof of 12 months of qualifying funded performance or untouched independent confirmation.

## Chronological selection result

| Diagnostic / selection | USDJPY | USDCAD | Combined |
| --- | ---: | ---: | ---: |
| Causally eligible entry proposals after forecast/cost screen | 13 | 18 | **31** |
| Rejects by conservative TRAIN-only adaptive utility | 13 | 18 | **31** |
| Simulated funded complete round trips, all three frozen slippage scales | **0** | **0** | **0** |
| Modeled gross / modeled cost / modeled NET (EUR) | 0 / 0 / 0 | 0 / 0 / 0 | **0 / 0 / 0** |
| Complete selection weeks with >=21 round trips | 0/10 | 0/10 | not a combined funded portfolio |
| Survives selection gates | no | no | **none** |

Before the 31 proposals there were **648** feature-decision windows, **617** rejected by forecast versus anticipated broker cost, **0** missing-data rejects and **0** zero-forecast rejects. Event quotes were requested for the 31 planned entry/exit paths (121 instrument-plus-EURUSD event windows). An evaluated proposal is not necessarily a trade.

**Critical interpretation:** the printed `NET = 0 EUR` is the accounting result of **zero admitted trades**, not evidence of a flat-return strategy, a profitable strategy, or measured net outcomes of the 31 rejected proposals. The three slippage-sensitivity cohorts (0.5x, 1x, 2x calibrated quote-motion proxy per side) each admit zero trades. No historic real fills, complete historical tariffs, observed broker stopout term, absolute DD guarantee, qualified HARD21 or funded portfolio NET are demonstrated. TRAIN-dependent uncertainty adjustment and finite stress states may prevent admission; this negative admissibility outcome **does not** prove the conditional predictor's forecast law or the entire nonparametric family economically impossible.

The exact frozen `H1_CONDITIONAL_NEIGHBOUR_RETURN_K64_V1` configuration on these selection dates is **CLOSED_NO_ADMITTED_FINANCED_EPISODES**, with no coefficient tuning, scaling tweak, reversed direction, re-priced holdout, or selection of favourable slippage assumptions. Final20 confirmation was **not evaluated**; it is not called a failure or success. USDJPY and USDCAD are *alternative* experiments each using the same initial EUR200, not a synthetic EUR400 joint account. Original risk authority is adaptive, not fixed 1%/2% per entry; mandatory initial EUR200, DD maximum30%, and system HARD21 remain.

## Highest-value next work
Do not rerun this exact frozen candidate. In subsequent **genuinely distinct** causal research, preflight the calendar coverage needed for selection, estimate gross and quote-dependent cost separately, and admit only hypotheses that can support a funded EUR200 event replay with mark-to-market floating drawdown and concurrent positions. Count every objectively eligible week including zero-trade weeks; do not infer independence from old development-exposed calendar history. Preserve broker quote/cost/margin provenance and distinguish unavailable data from economic rejection. Promote native cBot logic only after independent NET evidence; all current cBot code remains observation-only. Zero LIVE/DEMO orders and no Cloud activation.

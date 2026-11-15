# MVE1 — original authenticated multivariate OHLCV event research, 2026-11-15

**OWNER decision-ready economic research receipt.** No trading permission.
Authority `docs/OWNER_SPEC.md` OWNER v2.0 and OWNER post-SPDE1
multivariate OHLCV discovery order.

## 1. Unaltered original study and custody

- Initial prospective MVE1 protocol separately frozen at
  `f5f4339a69ce16d1eb1850b7023e58af4bebe078` **before** any
  original outcome. Technical pre-source current-term rollover A1
  was recorded separately at `8c406fd64b7c7c8308ac5a37e249a77f7a8c4f6b`.
  Original feature population, model, costs and split have not been
  retuned or rerun after observing authentic outcomes.
- Research code integrated through PR
  [#311](https://github.com/mariancradulescu/mxm-quant-cloud/pull/311),
  original executable HEAD `8ad35decc6ac24a9a61478aaaf4e85f50e08b31e`.
- ORIGINAL encrypted BDP1 source readback
  `#41724643418`, source SHA256
  `e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370`;
  ORIGINAL AIP1 source readback `#41735441128`,
  source SHA256
  `fa684ca1de58c6d1e8bdee410834855d05389af0c0ae4523b095367dce0e5331`.
  Both complete protobuf/account source reconstructions independently
  confirmed by the existing authenticated source-and-native C#
  original COST path; original BDP1/AIP1 predictive policies
  were NOT reexecuted.
- True original action
  [#43763069241](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43763069241)
  **SUCCESS**. Original standalone public JSON evidence is artifact
  **#14181073514**, ZIP SHA256
  `30cacebf45134659846c8764a272ff6eca1ed155031d88a9cfd50be3195e1288`;
  extracted public JSON SHA256
  `87fbeef2516710bf1bcae75ec1a05a5bc77633818a015845a37f849f69e87e6d`.
  Exact frozen protocol SHA256:
  `1414f8db233566dca194ba6987f66289e4fe24ba25b080d5fe6d8b9272f73567`.
- **0 new Pepperstone requests, 0 broker orders, 0 LIVE/DEMO actions,
  no Cloud activation, no new permanent services**.

## 2. Source coverage and the feature/event study

**836,087 genuine M5 Pepperstone bars over 12 instruments** with
original source-unique instrument counts. 836,077 historical completed
bars fell within the exact fixed research calendar. 118,367 had
no valid contiguous 49-bar causal warmup; 87,932 passed the
source warmup but did not meet any of the predeclared observable
event definitions. Exactly **629,778 multitag causal event intents**
were generated before looking at any future label or price.

All completed M5 clocks, NOT three cherry-picked hours per day.
Six independent objective event tags (overlap permitted):
BREAKOUT_12 112,400; WICK_REJECTION 306,661;
VOLATILITY_TRANSITION 322,823; PULLBACK_REJOIN 88,792;
COMPRESSION_BREAK 58,882; IMPULSE_CONTINUATION 298,391.
Counts are overlapping tags, **not additive independent events**.

Common vector: **32 continuous variables** comprising prior-bar body
and wicks, scaled multi-horizon impulse (3/12/24/48 M5 bars),
efficiency, six/24/48-bar realized volatility, compression/previous
range, breakout distance, RSI/EMA and broker tick activity,
synchronous original peer context, clock phase, six nonlinear
feature interactions and six event-tag covariates.
All features are sourced from exactly 49 genuinely closed M5 bars
and clock-synchronized *closed* peer returns.

Joint regularized four-target model estimates normalized future
signed return, high excursion, low excursion, and future
volatility expansion. Two predeclared horizons: 12 and 48 M5
bars (60 and 240 minutes). Training data and scaling confined to
the original first 26 weeks, selection on following 13,
last 13 already globally exposed and **NOT independent confirmation**.

| Period | Original events | Fully matured 60m | Unknown 60m | Fully matured 240m | Unknown 240m |
|---|---:|---:|---:|---:|---:|
| Train26 | 313,152 | 299,842 | 13,310 | 265,083 | 48,069 |
| Selection13 | 158,080 | 150,875 | 7,205 | 132,055 | 26,025 |
| Exposed13 | 158,546 | 151,369 | 7,177 | 132,500 | 26,046 |

Unknown next-path prices were retained as future-unknown. They did
not alter event scheduling or predecision forecasts.

## 3. Predictive information: signed return is WEAK, path/risk is useful descriptively

All MSE below are normalized target errors on exactly matched
observations. Zero and naive momentum are distinct baselines.
Comparison against the simple own-price model is crucial:
a large improvement over a poor momentum formula alone does not
establish incremental information from complex interactions.

| Phase / horizon | MSE FULL | MSE own-price | MSE zero | MSE fixed momentum | Direction Brier FULL | Direction accuracy |
|---|---:|---:|---:|---:|---:|---:|
| Selection 60m | 1.475046 | 1.476034 | 1.476475 | 1.540981 | 0.249819 | 50.67% |
| Exposed 60m | 1.422864 | 1.423644 | 1.422935 | 1.485369 | 0.249894 | 50.22% |
| Selection 240m | 1.877957 | 1.877529 | 1.877532 | 1.891726 | 0.249955 | 50.98% |
| Exposed 240m | 1.785175 | 1.785027 | 1.781860 | 1.792108 | 0.250149 | 49.80% |

Paired 13-week same-event instrument-balanced differences
(full minus a comparator error benefit) with Bonferroni bounds:

- 60m selection FULL vs fixed own momentum:
  mean improvement `+0.06338129`, lower `+0.04002689`;
  versus own-price trained model: mean `+0.00068539`,
  **lower `−0.00081171`**; versus zero:
  lower `−0.00062494`.
- 60m exposed evaluation FULL vs momentum lower
  `+0.04373492`; vs own-price lower `−0.00148916`;
  vs zero lower `−0.00268573`.
- 240m selection FULL vs momentum lower
  `−0.00185445`; vs own-price `−0.00313715`;
  vs zero `−0.00507401`.
- 240m exposed FULL vs momentum lower
  `−0.00438241`; vs own-price `−0.00286624`;
  vs zero `−0.01014643`.

**Interaction/multimarket incremental attribution (60m):**
selection FULL vs removing interactions weekly adjusted lower
`−0.00050956`; FULL vs removing peer lower
`−0.00095484`. On exposed portion, corresponding adjusted
lower bounds `−0.00066684` and `−0.00053484`.
Thus the combined 32-feature model does not prove robust
incremental directional alpha due to nonlinear interactions
or peer information, even if some average differences are positive.

**Separate conditional distribution/risk finding, NOT trade alpha:**
future volatility expansion Brier (FULL vs original TRAIN-only
unconditional regime prior):

| Horizon | Selection FULL / prior | Exposed FULL / prior |
|---|---|---|
| 60m | 0.215945 / 0.246173 | 0.212409 / 0.246264 |
| 240m | 0.197478 / 0.249784 | 0.190267 / 0.248731 |

For future favorable (high) and adverse (low) normalized excursion
prediction, FULL improves descriptive absolute-error results
over the train-only unconditional mean in **both chronologies**;
e.g. 60m selection high MAE 0.573980 vs 0.589074,
low MAE 0.616638 vs 0.630381; exposed high 0.568853 vs
0.585008, low 0.604393 vs 0.620185.
At 240m, selection high 0.636945 vs 0.664770 and low
0.701583 vs 0.719235; exposed high 0.623036 vs 0.654448,
low 0.692615 vs 0.717934.

These are genuine *descriptive predictive differences on already
globally exposed history*, not a certified independent
risk-distribution model, and OHLC high/low does not resolve
intra-bar ordering or true protective stop fills. No evidence
warrants selecting a favorable event regime after viewing these
breakdowns.

## 4. Selection, abstention and actual original EUR evidence limits

The fixed model first evaluated direction and uncertainty, then
authentic training-phase current-contract costs and EUR min-notional.
Exactly **166 original C# synchronized quote/fee/current-margin
contexts** from BDP1/AIP1 were train-dated. All twelve symbols were
included; no favorable instrument was substituted after results.

The following EUR figures are **CONDITIONAL current-tariff EUR at
authentic original M5 price proxies, for a single minimum-unit
position per selected event with potential overlapping exposures**;
NOT authenticated historical broker fills, NOT a C# cash-funded
ledger, NOT a realizable consolidated return on EUR300.
Original observed event bid/ask on every scheduled entry/exit
is **not available**; model friction includes observed original
training snapshot spread, original as-observed current terms,
commission/slippage scenarios and threefold directional swap
debit if an interval crosses the current-contract rollover.

| Phase / horizon | Predecision one-per-clock event intentions | Fully priced modeled outcomes | Unknown selected forward outcomes | Central modeled EUR | Adverse modeled EUR |
|---|---:|---:|---:|---:|---:|
| Selection 60m | 40 | 39 | 1 | +23.648952 | **+14.542847** |
| Exposed 60m | 17 | 16 | 1 | +1.852838 | **−0.221842** |
| Selection 240m | 1,014 | 893 | 121 | −1,524.282510 | **−2,005.732066** |
| Exposed 240m | 611 | 549 | 62 | −774.527140 | **−1,031.242097** |

The 60m selection cohort had **16 profitable and 23 losing**
individually modeled positions; the exposed cohort had 9 positive
and 7 negative. Selection reversal vs continuation intentions
were 33 vs 7, exposed 15 vs 2, suggesting a different conditional
decision mix from the 240m model, but not an independently verified
reversal mechanism. One selected 60m outcome remains missing in
each of the two phase panels.

Matched chosen-clock fixed 12-M5 momentum adverse NET:
**−30.007187 EUR** vs +14.542847 (selection 60m),
**−15.674251 EUR** vs −0.221842 (exposed 60m).
This is a useful counterfactual, **not** proof of a
transaction-funded or 30%-DD-bounded incremental advantage.

The 240m model's selected-intent economics failed badly,
including on the exposed chronology. Do not mask those figures
by reporting only 60m or an ex post favorable symbol,
event tag, side or forecast uncertainty threshold.

No chronological 13-week selection model passed the
predeclared multiplicity-adjusted predictive hurdle against BOTH
the fixed momentum and simpler own-price model; result field:
`NO_MULTIVARIATE_PREDICTIVE_MODEL_PASSED_STRICT_SELECTION`.

**Resulting exact MVE1 admission: NONE.** The conditional
positive 60m selection EUR is not a promoted policy: its next
globally exposed 13-week adverse EUR is slightly negative and
there is no shared EUR300 C# ledger financing, continuous
floating drawdown proof, systemic HARD21, actual broker-order
fills or independent 12-month confirmation.

## 5. Rational continuation, without retrospective rescue

This study meaningfully evaluated observable events, feature
interactions, classification/abstention, conditional expected
movement, intrahorizon favorable/adverse excursion and
volatility regime switching on original source — not just
infrastructure. New evidence suggests relative learnability
of *volatility and path risk* was greater than incremental
signed-return direction in the tested fixed original model.
This statement is descriptive and requires a distinct
**prospectively designed, truly unexposed** risk/uncertainty
evaluation, not a retune or revival of this closed MVE1
configuration.

Retain original 52-week source and original artifact/receipt.
Do not invert signals, change ridge penalty, adjust event or
confidence gates, choose 60m from hindsight as qualified or
relax negative adverse EUR. New native C# implementation of
MVE1 coefficients and ledger proof is not justified as a
trading promotion at this stage; existing native C#
provenance/cost, orchestration, risk and cash ledger remain
intact and available for later independently supported
candidates.

**Final:** original MVE1 preserved and exact rule
`NOT_QUALIFIED_NO_ROBUST_INCREMENTAL_DIRECTIONAL_OR_EXECUTABLE_EUR`.
This does NOT establish that all continuous multivariate OHLCV
or regime-transition representations lack predictive information.

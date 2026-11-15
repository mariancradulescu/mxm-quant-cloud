# SPDE1 — authentic systematic OHLCV predictive and conditional EUR report (2026-11-15)

OWNER continuation after GCR1 / PR #306–307. Authority docs/OWNER_SPEC.md
OWNER v2.0; accepted systematic methodology
docs/OWNER_SYSTEMATIC_OHLCV_PREDICTIVE_DISCOVERY_20261115.md.

**Result: systematic predictive discovery was ACTUALLY RUN, not merely
prepared.** The exact original SPDE1 frozen mechanism did **not**
demonstrate sufficient predictive uncertainty/cost-adjusted advantage
to admit an opportunity in selection. Therefore no SPDE1 asset,
family, timeframe, regime or direction is economically promoted.
The trading decision for this exact study is ABSTAIN.

## 1. Genuine execution and original-source custody

- Frozen original source-agnostic economic protocol:
  `research/spde1_protocol.json`, first separate commit
  `78126e3b3f1829ea81fc026e5e345a6ce9085685`,
  SHA-256 `2accb53f26ec40034d8405fdf82f1b2abb61543cf7f1ea081584a4cdb3eb4e08`.
  It predates all original SPDE1 outcome scoring.
- PR #308 integrated systematic causal seven-family Python research,
  original fixed protocol, tests and an actual protected GitHub
  readback job; no permanent Python runtime in target cBot.
- Original first attempt #43737304206 FAILED **before** source
  checkout/retrieval due solely to an invalid pinned setup-dotnet
  action. PR #309 source-blind F1 corrected ONLY the runner action
  hash, prior to the first source opening.
- Real original SPDE1 research:
  [Actions #43737644678](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43737644678)
  **SUCCESS**. Original research-only artifact
  **#14171066144**, artifact ZIP SHA-256
  `21a997271c432d3d845d53590a362c3054995359f7be3a714470f80d6c936f65`,
  extracted original JSON SHA-256
  `f19392b28ad183fa0e55e1ad764f1764a531cbb6a3ba9db493292a77c0f0c338`.
- Reused original independent source archives:
  **BDP1** original #41724643418, ciphertext
  `e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370`;
  **AIP1** original #41735441128, ciphertext
  `fa684ca1de58c6d1e8bdee410834855d05389af0c0ae4523b095367dce0e5331`.
  All original source/protobuf account/contract/bar reconstructions
  in `multiscale_conditional_research.recover` passed for each archive;
  no closed BDP1/AIP1 models, WIDE_REGIME or IPF1 were invoked.
- Original M5 OHLCV: **836,087 bars** over **12 instruments**:
  EURUSD 74,195; GBPUSD 74,126; USDJPY 74,031; AUDUSD 74,177;
  USDCAD 74,161; XAUUSD 70,550; US500 70,490; NAS100 70,495;
  GER40 60,903; UK100 60,186; AUS200 62,310; JPN225 70,463.
- Original current-contract BID/ASK, commission, margin and FX cost
  contexts: **166**. All 166 had original observation timestamps in
  TRAINING interval, never future audit quotations used for
  selection cost thresholds.
- **0** new Pepperstone requests, **0** broker orders,
  **0** Cloud activations, no OAuth reauthorization.

## 2. Actual causal prediction construction

Seven distinct **native-replicable completed-M5 OHLCV** categorical
feature families were scored on the same pre-fixed whole-universe
08:00 / 12:00 / 16:00 UTC weekday clock grid, 2025-11-03 to
2026-10-30, two fixed forecast horizons 60m and 240m:

| Feature family | What genuinely entered the ex-ante prediction |
|---|---|
| CANDLE_GEOMETRY | Completed candle real body, upper/lower wick, close-to-range location |
| IMPULSE_PERSISTENCE | Signed 30m and 120m completed-return persistence |
| VOLATILITY_TRANSITION | Completed last-8 versus last-32 M5 realized volatility, expanding/contracting states |
| CONSOLIDATION_BREAKOUT | Completed close beyond the PREVIOUS 24 M5 high/low, otherwise range state |
| PULLBACK_CONTINUATION | Previous 4h signed trend opposed by latest completed 1h pullback |
| CLOSED_BAR_INDICATOR | RSI14 and EMA12/EMA26 concordance on completed closes |
| SYNCHRONIZED_PEER_CONTEXT | Earlier completed 4h directional returns from available same-clock peers, no future alignment |

Each source/timeframe slot required exactly 49 contiguous M5 bars
ending at the decision. Missing predecision feature is
`FEATURE_UNKNOWN`, not `ABSTAIN`. Entry/exit labels use original
M5 CLOSE price proxies at t+5m / t+65m or t+245m and never affect
same-time causal intents. Missing future target remains unknown,
not zero. Price proxies are **not** broker executable BID/ASK fills.

A new categorical per-symbol/feature-state/horizon empirical-Bayes
conditional mean and directional-probability model was fitted;
**454** genuine conditional training states. This is neither
the frozen WIDE_REGIME ridge model grid nor IPF1 SGD. No test-period
label fed into training and no postselection family coefficients
were retuned.

**Chronology:** weeks 1–26 training, weeks 27–39 genuine separate
selection *on the already globally exposed historical dataset*,
weeks 40–52 held-out from the new fitting and selection but
**not independent of the project's previously exposed history**.
No 13-week performance was used to choose the retrospectively
best cell in the later period.

| Stage | Fixed horizon×symbol slots | Causal feature known | Realized label complete | Feature unknown | Future label unknown |
|---|---:|---:|---:|---:|---:|
| Training 26 weeks | 9,360 | 8,836 | 8,675 | 524 | 161 |
| Selection 13 weeks | 4,680 | 4,538 | 4,382 | 142 | 156 |
| Exposed descriptive 13 weeks | 4,680 | 4,544 | 4,394 | 136 | 150 |
| **Total** | **18,720** | **17,918** | **17,451** | **802** | **467** |

## 3. What was and was NOT predictive

For each of the fourteen fixed feature×horizon policies, the output
contains precommitted selection and descriptive-evaluation
directional accuracy, mean Brier probability score, and matched
simple training-prior Brier benchmark. **Lower Brier is better.**

### Mean Brier versus original train-only prior (selection / exposed)

| Feature | Selection 60m model vs prior | Exposed 60m | Selection 240m | Exposed 240m |
|---|---:|---:|---:|---:|
| Candle geometry | .252199 / .251413 | .253863 / .252116 | .249827 / .249409 | .250669 / .249895 |
| Impulse persistence | .253060 / .251402 | .254036 / .252114 | .250172 / .249294 | .250991 / .249848 |
| Volatility transition | .251294 / .251402 | .252435 / .252114 | .249713 / .249294 | .250323 / .249848 |
| Consolidation / breakout | .252252 / .251402 | .253898 / .252114 | .250793 / .249294 | .249500 / .249848 |
| Pullback continuation | .254853 / .251402 | .254702 / .252114 | .249397 / .249294 | .251032 / .249848 |
| RSI/EMA indicator | .251816 / .251402 | .254243 / .252114 | .250403 / .249294 | .252141 / .249848 |
| Synchronized peers | .251697 / .251402 | .253159 / .252114 | .249631 / .249294 | .250105 / .249848 |

Results: only **volatility transition 60m** had a small
selection Brier improvement (0.251294 versus 0.251402); in the
later period it became worse than its benchmark (0.252435 versus
0.252114). **Consolidation/breakout 240m** improved slightly only
in the later descriptive period (0.249500 versus 0.249848)
AFTER failing the original selection comparator (0.250793 versus
0.249294). These isolated, tiny and nonpersistent reversals
do not satisfy a prospective predictor selection and must not be
cherry-picked into a renamed strategy. The other comparisons did
not show robust predictive value either.

No feature or volatility regime was qualified by the predeclared
familywise statistical/economic conditions. Source bars, fields
and transformations remain available for genuinely NEW hypotheses,
not later retuning of this exact classifier.

## 4. Opportunities, uncertainty, cost and EUR result

The predictor did NOT transform every indicator into an entry.
At each pre-fixed selection clock it classified all supported
symbol/family/horizon forecasts into predictive abstention, cost
adverse abstention or economically rankable opportunity.
To count an actual selected intent a directional prediction had
to exceed its **95% model uncertainty interval AND independently
authenticated modeled adverse cost**, with current original
minimum margin below EUR300. Select the maximum
conservative expected NET EUR of all 12 instruments for each
family/horizon only where that lower bound is strictly positive;
the same rule is applied prospectively to the 13-week selection
population. No trade frequency minimum is forced.

Across the 14 selection policies (2,340 clocks each; counters are
OVERLAPPING POLICY DIAGNOSTICS, not separate trades):

- 30,704 predictive-confidence `ABSTAIN` classifications;
- 1,052 additional cost-adverse `ABSTAIN` classifications;
- 994 source-unknown classifications;
- 10 unknown training-support classifications;
- **0 economically rankable model opportunities** and
  **0 selected funded or modeled entries**.

All 14 family×horizon selection panels and all 14 exposed
descriptive panels have **0 EUR** conditional modeled NET
central and adverse, because the fixed policy **never enters a
position**. These are *cash/abstention results*, not evidence of
a positive alpha or 14 independent successful portfolios.
A forced-direction profitability score is deliberately not
promoted to trading economics.

The valid minimum-volume model context had original observed
EUR margins ranging from **EUR27.50 to EUR177.95** across 12
markets, but same-time shared cash, opening/closing and floating
drawdown were never funded in the C# ledger because **no
positive-adverse expected NET candidate passed admission**.
`nativeFundedContinuousEur300BookProven=false`, and
`brokerRealizedNetEur=null` are the correct original outcomes.
It would be wrong to report trading profit from these values.

## 5. Original verdict, risk and future direction

**Original immutable result status:**
`NO_FAMILY_PASSED_STRICT_SELECTION`;
`selectionQualifiedCount=0`;
`frozenSelectionFamilyHorizon=null`.
**OWNER verdict:** exact SPDE1 seven-family categorical
classifier and associated economic admission rule CLOSED, no
trade promotion. No retuning of the 95% bound, invented filters,
after-the-fact instrument/timeframe winner or reproduction of this
exact study under a new name.

Minimum 12 months of original source are present, but all weeks
are globally research-exposed, **NOT new independent confirmation**.
There are no historical broker-complete fills, funded common-C#
NET, continuous floating DD<=30% or system HARD21 proof.
No LIVE/DEMO or Cloud orders are authorized.

**Next discovery must remain systemic and predictive**, not return
to one-off macro calendar hypotheses or mere quote collection:
advance-register genuinely distinct continuous/multivariate
OHLCV predictive structures, train/selection/test discipline,
full 12+ instrument universe when authentic sources permit,
source coverage/causal checks, multi-family ablations and
opportunity ranking; request new untouched forward source where
true independent confirmation is required. The existing
C# OpportunityOrchestrator and NativeFundedLedger are the
only authorized common cash/risk integration once a defensible
positive-incremental-EUR candidate survives the causal screen.
Do not revive the exact closed WIDE_REGIME, IPF1, BDP1, GCR1 or SPDE1 policies.

**Source of truth:** untouched original
`spde1-systematic-ohlcv-authentic-eur.json` inside
[original artifact #14171066144](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43737644678/artifacts/14171066144).
The report paraphrases source data without rewriting or rescoring it.

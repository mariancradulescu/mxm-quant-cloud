# OWNER 2026-11-15 — SPDE1: systematic native-predictive OHLCV discovery, post-GCR1 mandate

**Authority:** `docs/OWNER_SPEC.md`, OWNER v2.0 and all amendments.
This is a **new prospective research-process specification**, not an
instruction to retune GCR1, resurrect WIDE_REGIME / IPF1 / BDP1 / PVE1
or select a previously favorable exposed cell. Neither this
specification nor the GCR1 final report constitutes a new scored
OHLCV economic experiment. The previously closed configurations and
their immutable receipts remain closed.

## Why this method changes (economics, not just implementation)

An economic explanation, a sign relationship and a positive gross-bps
mean cannot substitute for predictive information and executed EUR
wealth gain. Serial one-off signal studies, selected assets, ad hoc
microstructure/cost gates and repeated isolated macro hypotheses
have not produced a robust capital-funded strategy. The mandatory
primary research loop becomes **systematic feature -> causal forecast ->
multi-opportunity scoring/ranking -> native funded portfolio ->
independent verification**. Bid/ask, FX, fees and margin are required
downstream for execution proof and final admissibility; they are NOT
the source of new prediction candidates.

The final product remains **one C# native cBot**, Android-operated in
cTrader Cloud, not a Python/permanent external-service trading system,
under prospectively initial EUR300, no resets or deposits, systemic
HARD21, DD<=30% including full floating equity and costs, at least
12 relevant months and genuine independent confirmation. Until
all gates pass: **no LIVE/DEMO orders and no Cloud activation**.

## 1. Reuse already implemented, authenticated infrastructure FIRST

The following are software/source primitives, not candidates resurrected:
- `research/portfolio_discovery_source.py` and historical BDP1/AIP1
  custody/provenance receipt: 836,087 original M5 bars / 12 assets
  with globally exposed 52-week history; source-only readback is
  permissible, frozen BDP1 predictor and its result are not rerun.
- `src/Mxm.Core/RegimeDiscovery.cs` already includes completed OHLCV
  candle geometry, volatility/path efficiency, multi-resolution
  aggregation, a train-only ridge scaler and purged expanding folds.
  **Do not rerun its closed 432-trial original model grid**:
  WIDE_REGIME 2026-11-03 had 0 multiplicity-supported cells even at
  nominal zero cost. It is a reference implementation/primitive
  inventory, not evidence of new alpha or permission to tune that grid.
- IPF1 original fusion/ablation and native scenario engine are
  **closed**: its FULL book lost NET and later exposed audit failed;
  reuse underlying generic source/financial/parity modules, not
  scored predictors or exposed candidate winners.
- `src/Mxm.Core/CausalObservationClock.cs`,
  `CausalForecastScoreLedger.cs`,
  `OpportunityOrchestrator.cs`,
  `AdaptivePortfolioRisk.cs`,
  `NativeFundedDecisionCycle.cs`,
  `NativeFundedLedger.cs` and `research/evidence_registry.json`
  remain the common single-capital scientific and accounting
  infrastructure. Do not create a separate decision allocator,
  account, cBot, runtime service or an incompatible ledger.
- The 100 older encrypted archives are separately catalogued,
  verified by original hashes and exact symbol/date/resolution;
  they are NOT assumed to contain another 12 independent months,
  full native BID/ASK, or features not actually present. New
  Pepperstone read-only collection is freely permitted when needed.

## 2. Feature census on completed, usable native C# OHLCV alone

Define a **single reusable, multi-instrument/timeframe feature catalog**,
not a sequence of independent bespoke strategies. Every feature
record stores symbol, resolution, completed source-bar end, first
available decision clock, exact original source digest, required
lookback, sample/holiday/gap states and symbolic C# replication.

Prospective families to implement/census, without later selecting only
the ones whose original outcomes appear attractive:

1. **Candlestick structure:** real body/range, upper/lower wick,
   close position, true range, preceding open-to-close gap,
   multi-bar inside/outside patterns, rejection/engulfing geometry;
   zero-range/missing bars explicitly UNKNOWN.
2. **Directional impulse/trend:** normalized returns at several
   completed scales, regression slope or directional efficiency,
   trend persistence/exhaustion, pullback depth and acceleration.
3. **Volatility and compression:** ATR, robust realized range,
   volatility ratio, contraction/expansion, time spent in
   consolidation, breakout distance versus PRIOR observed limits.
4. **Regime and market context:** completed volatility/trend/range
   states, session/calendar, tick-volume intensity or signed
   activity *only if broker-authentic and natively replicable*,
   peer direction where synchronized completed input exists.
5. **Reference indicators:** rolling SMA/EMA, RSI, ATR, ADX/DI,
   channel/Donchian/Bollinger position or similar native cBot
   computable transforms; indicator presence does NOT by itself
   qualify predictive edge.

Do not preselect a symbol, session, sign or regime because a closed
study happened to show a favorable exposed result. Missing OHLCV
fields, lack of native tick volume, contract closures and incomplete
contiguous bars are first-class SOURCE/FEATURE_UNKNOWN states.

## 3. Systematic model: forecast distribution and rank opportunities

- For each causal completed-bar event, produce a **directional
  distribution and conditional potential EUR payoff**, with
  calibration/uncertainty, not automatic entry on every indicator.
- Define an explicit *economic opportunity* of instrument × mechanism
  family × causal market regime × horizon × native entry/exit rules ×
  minimum legal volume and cost route. Log every evaluated combination,
  including abstention and missing outcomes.
- Begin with fixed regularized, interpretable pooled multi-asset
  classification/regression and incremental feature-family ablations;
  admit further complexity only by new pre-source registered plan
  with out-of-sample benefit. No hyperparameter search on a
  validation fold that is later called independent.
- **Native causal information sets**: no future quote, realized label,
  future label coverage, revised indicators, unclosed candle or
  GCR1-style source availability affecting the current forecast.
  A label may update an online model only AFTER its entire
  horizon matures. Purge/embargo overlapping train and test targets.
- Evaluate directional calibration, uncertainty, upside/downside
  distributions, gross contribution vs neutral/own-momentum,
  and incremental value of every feature family on calendar-
  comparable events, before connecting full execution/margin costs.
- Then rank BUY/SELL/ABSTAIN candidates by conservative
  incremental expected **NET EUR**, not maximum raw signal count.
  Account for existing open/pending exposure, redundant risks,
  individual minimum volume, correlated states and cost/adverse
  uncertainty. A rejected or unfunded opportunity does not become
  a complete transaction.

## 4. Learning discipline, source exposure, honest validation

1. Publish immutable source/calendar, universe, available resolutions,
   feature formulas, target clocks/horizons, training procedure,
   multiple-testing budget, benchmark definitions and ledger
   acceptance rules before new outcome scoring.
2. Train only on eligible historical observations with outcomes
   that had *fully matured* by the corresponding fit clock.
   Walk forward through chronological expanding or rolling
   periods with purging and horizon embargo; compare on fixed
   matched clocks. Separate training, model selection,
   final evaluation and future truly unexposed confirmation.
3. All available 52-week BDP1/AIP1 material and prior archive
   date ranges have already been globally research-exposed.
   Walk-forward analysis on them remains **developmental evidence**,
   no matter how many folds are used. A clean prospective source
   segment not exposed to earlier research is required to claim
   new independent confirmation.
4. Use a fully specified family-wide discovery ledger and
   multiple-testing controls; never promote one favorable
   instrument/timeframe/regime combination after viewing audit
   or after multiple unreported tests. Preserve every failure.
5. Record missing future outcome separately from a predecision
   UNKNOWN and from explicit ABSTAIN. Do not condition the
   predecision signal on successful future BID/ASK, EUR conversion
   or complete forward path. Report the unconditional scheduled
   denominator, complete matched denominator and censoring by state.

## 5. Economic confirmation: only after genuine incremental prediction

- Evaluate exact native legal entry/exit times and volume, historical
  two-sided entry/exit quotations when available, round-trip spread,
  commission, financing, adverse slippage, conversion EUR and
  missingness. No nonsensical cross-asset aggregation in bps/pips
  substitutes for EUR500/EUR300 book funding. Cost screening
  is downstream of forecast discovery, NEVER a profitability source.
- Run ONE continuous initial EUR300 model book with the existing
  C# selector, allocator and ledger; at equal clock time process
  held marks / confirmed CLOSE settlement / release of actual
  margin BEFORE new entries. Preserve unresolved exposure, free
  margin, peak including sampled and when available continuous
  liquidation equity. No automatic capital top-up, redeployment
  reset or floating drawdown forgiveness.
- Compare prospective FULL policy to cash, constant-side,
  own-history price-only signals, deterministic simple rules
  and advance-frozen one-family ablations, each on **matched
  calendars and realistic comparable portfolios**; ablation
  books are counterfactuals, not simultaneous capital.
- HARD21 counts only fully financed, fully closed roundtrips
  per objectively predeclared eligible week across the
  **entire cBot**, not per candidate and not signal density.
  More indicators cannot be used to force 21 trades.
- Absolute and incremental *adverse* NET EUR must remain
  positive and economically stable in enough genuinely
  informative independent time periods, after conservative
  exposure/control of 30% floating DD. No broker order/Cloud
  authorization is implied by research success.

## 6. First bounded next implementation — NOT YET A SCORED STUDY

Implement an **inventory-and-causal-feature-parity stage** using
already authenticated source, current `RegimeDiscovery` primitive
patterns, C# source-replay inputs and invariant tests:
source/feature coverage by timeframe and symbol; native
time-stamp parity; strict split/label embargo; missingness
accounting; candidate registry; indicator parity between C#
and research-only Python. This stage produces *no trading
forecast result, margin reclassification, selected high-return
markets or independent confirmation*.

After that stage passes and the specific first new model protocol
is prospectively frozen, start genuinely new systematic
forecast evaluation; do NOT rerun original WIDE_REGIME, IPF1,
PVE1/2, GCR1 or other closed model grids under new names.

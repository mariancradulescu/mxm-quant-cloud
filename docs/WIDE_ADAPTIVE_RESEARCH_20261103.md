# OWNER mandate correction and broad adaptive development — 2026-11-03

The latest explicit OWNER directive withdraws EUR2/80/120 and universal 1%/2%
constraints. PR18 was closed without integration, branch preserved. Initial
capital remains EUR200 without deposits; system HARD21 and maximum DD30% remain.
No LIVE/DEMO orders, activation, new credentials, or broker correspondence.

## Exact research protocol frozen before authentic execution

Reuse source run 41476636915 with ciphertext hash and native receipt parity.
Previously exposed development dates; never call these untouched confirmation.
All available six-symbol H4/M15 groups, plus complete UTC H1 from four M15 and
D1 from six H4 bars. Record all missing/short groups; no symbol cherry-picking.
H1/M15 have short history: this does not establish 12-month frequency.
Horizon grid 1/4/16 bars. Eight model families: intercept, trend ridge, candle
response ridge, volatility interaction ridge, intermarket ridge, pooled ridge,
causal regime specialist ridge, and fixed equal pooled/specialist ensemble.
No closed breakout, hourly shock reversal, session drift, cross-currency
GBP-minus-AUD or PRIMARY145 configuration is called or retuned.

Features: completed returns at 1/4/16 lags, candle body/location, 8-vs32 RMS
volatility, 16-bar path efficiency, observed past gap fraction, volatility interaction, contemporaneously
completed same-timeframe peer returns, and cyclic hour. Peer availability is
checked as-of; absence is represented by count, not fabricated observations.
Regime descriptors: efficiency >.35 and short RMS > long RMS (four cells).
These are frozen exploratory descriptors, not a final taxonomy. Fewer than
80 specialist examples falls back to pooled ridge. No HMM/boosting is installed
merely for sophistication; first measure whether specialist linear inference
improves on the pooled/baseline alternatives. Native C# implements scaling,
ridge fit (penalty .1*n, intercept unpenalised), prediction and aggregation.

Expanding folds: first50% fit, test50–60, refit0–60/test60–70,
refit0–70/test70–80. Purge all training labels ending at/after test start;
exclude test labels reaching next fold boundary. Last20% has no performance
calculation. This does NOT recover independence from prior historical exposure.
Per-model entries do not overlap; prediction at completed close, proxy entry
next contiguous bar open, exit horizon close. Past observed returns across weekend/gaps remain available with a gap feature.
No missing bars are filled. Discontinuous execution target windows are excluded,
explicitly making execution proxies conditional on target continuity.
Weekend/gap opportunities remain untested, not assumed absent in deployment.
No optimized stops or entry confidence thresholds. Report every attempted cell.

Gross basis points and hypothetical round-trip costs 0/1/3/10 bps are sensitivity
curves, NOT broker-cost NET, EUR profit, funded fills or executable positions.
Weekly exit-block approximate HAC variance (lags1–2, not below iid variance),
with conservative Gaussian union-bound multiplier sqrt(2 log(2*N/.05)) for all
instrument/timeframe/horizon/family trials. This is an approximate exploratory
screen under non-Gaussian/dependent markets, not certified statistical FWER.
Regime breakdowns and cost stresses are descriptive, not independent tests.
At least30 episodes, 8 observed exit weeks and positive adjusted weekly bound
at3bps flag further investigation; three positive folds distinguish stability.
No candidate is automatically promoted to holdout or trading. All trials stay
in the ledger, including missing support and negative evidence. Broader past
research multiplicity remains unknown, so new confirmation must be prospective.

## Adaptive portfolio research, not a validated trading policy

HistoricalPr16Risk preserves exact old 2%/20% arithmetic only inside closed
PR16 CausalFlowResearch and regression tests; public verdicts stay byte-for-byte.
It has no current risk-policy authority. New AdaptivePortfolioRisk compares zero
exposure with every broker-valid volume on a bounded computational grid using
lower expected incremental log-wealth utility. Confidence multiplier and
effective independent blocks are explicit experimental inputs, not risk caps.
All joint states include open/pending/bounded ambiguous exposure, costs, FX,
liquidity, intrahorizon loss, favorable peak and margin. No diversification
discount from a guessed correlation. Unweighted stress states constrain exposure
without contaminating the estimated mean. Require <30% adverse scenario DD,
nonnegative funded margin after stress, observed broker stopout terms, real min/
step/max and available margin. No positive lower utility => suspend new risk.
Monitoring/selective recovery remain independent.

Finite scenarios cannot prove absolute DD/ruin control. Sample ruin fraction
only describes admitted scenario states; it is not an estimated live ruin rate.
No calibrated economic distribution, transition/gap tail coverage, long-horizon
capital-path simulation, real funded return or validated adaptive risk policy is
claimed. This is a native evaluation component to compare future policies on
honest chronological/prospective evidence. Parameter trials require their own
selection ledger. Broker netting/portfolio margin benefits are not invented.

## Validation references

Chronological causality and multiple-testing discipline are motivated by:
- Bailey & López de Prado, Deflated Sharpe Ratio (2014),
  https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
- Bergmeir, Hyndman & Koo, time-series CV validity (2018),
  https://robjhyndman.com/papers/cv-wp.pdf
The present implementation uses expanding purged folds and an explicitly
approximate union-bound screen, not an implementation of DSR or HMM.

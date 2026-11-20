# FCP1 prospective protocol — financed FIRST versus economic rankers (19 Nov 2026)

Authority: docs/OWNER_SPEC.md, Issue #393, OWNER decision after SCP1-A1. This document is frozen on a new branch BEFORE any FCP1 code or outcome. SCP1-A1 original #44525563693, artifact #14530975929 and original scorer/results remain immutable and are NOT re-run or altered.

## Estimand and decisive counterfactual
Does a predecision probability or economic score improve **completed funded EUR NET** over the FIRST opportunity that is **actually financeable**, under equivalent quotes, clock, legal volume, capital, risk, exit machinery and opportunities? An all-CASH comparison is noninformative. FIRST must traverse the ENTIRE chronologically ordered same-clock candidate set until it finds a genuinely financeable candidate; it cannot truncate before funding nor require predicted positive utility.

## Source scope and chronology
One native Core C# complete-policy evaluator and native Replay / observation-only Cloud adapter. Use only original authenticated CXL1 genuine BTCUSD/ETHUSD M5, HXC1 M1-derived exact M5 and actual M15, OEI1 as-of BID/ASK for ETHUSD, EURUSD and US500 when pairing real executable-price evidence; no invented quotes or execution fills. Other historical HXC1 M15/H1 symbols remain price-only until their compatible quote/contract paths are proven. Reuse original SCP1-A1 *frozen fitted snapshot* as a negative-control forecast input; NEVER retrain that closed estimator, rerun the closed study or label it successful. All Oct19–Nov09 2026 outcomes are globally exposed, strictly retrospective-exploratory, not prospective blind validation. Further genuinely independent history is needed for promotion; collection of new read-only sources is permitted.

## Fixed comparators, no ex-post method choice
- FCP1_FIRST: alphabetical symbol, family, side at an as-of closed-bar decision; test **every** candidate for funding; submit first fundable model intent (no forecasting veto).
- FCP1_SCORE: descending Bayesian contextual probability; model known to have failed independent calibration, included only as falsifiable score negative control, NO post-result model promotion.
- FCP1_RIDGE: separate fixed descending Ridge probability negative control (not choose a winner retrospectively).
- FCP1_MARGINAL: descending modeled *lower net EUR at minimum volume* after same-source spreads/slippage/fees; **not** an empirically validated EUR profit predictor. Require strictly positive lower value for admission, independently from FIRST.
- FCP1_ABSTAIN: choose none when adverse lower marginal EUR <=0; explicitly permitted.
- FCP1_LONG / FCP1_SHORT: mechanically directed first-financeable opportunity controls; no forecast utility veto.
- FCP1_CASH: zero trades.

All policies start one separate counterfactual EUR300 COMMON portfolio ledger (not separate asset budgets). Every policy processes identical complete causal quote clocks and opportunity timestamp set, though prior trades and financing change its later portfolio eligibility. No hard-coded position count; limit per-symbol overlap plus **global** free margin, pending reservations, aggregate prospective loss-to-stop versus remaining sampled 30% drawdown headroom, and actual broker legal min/step/max and fees. Dynamic volume cannot exceed these constraints. Stops are estimated risk reservations only, NOT executable intrabar claims; actual normal exits stay in NativeSimulatedCloseLifecycle via signal / structure / regime / risk, time only emergency. A modeled REQUEST_OPEN is NEVER a broker order or actual fill; only a later genuine quote permits the conditional modeled OPEN_FILL. Unknown data block, not zero-impute.

## Outcome / falsification gates
Pre-score every offered candidate; separately record (a) finance refusals (b) score refusals (c) selected model intents (d) subsequent fills (e) completed positions and censoring. Per policy: initial/final cash and sampled liquidation equity EUR, closed NET EUR with tariff-continuity UNKNOWN, win rate, PF, expectancy, payoff, R and MFE/MAE, max sampled DD, margin, concurrency, weekly complete funded trips and system HARD21. Score vs FIRST incremental EUR must compare common period, matched offered sets and capital semantics; record score-order to next outcome price-only rank diagnostics separately from funded performance, not condition on traded winners.

Failures: FIRST=0 despite actual clearly financeable opportunities is an implementation gate failure, not a model result. Score=0 with FIRST>0 is informative abstention but NOT uplift. Positive sample result is exploration only; >=12 months truly unexposed chronological independent verification and full realistic broker tariffs/intrabar/risk still missing. No LIVE/DEMO orders, Cloud activation, Android, new repositories, or closed-study reruns. Architect-Coordinator independently audits; OWNER decides promotion or merge.

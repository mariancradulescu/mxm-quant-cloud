# IPC2 · Integrated intraday FX and industrial-metal portfolio

This prospective development protocol tests complementary hypotheses in one
continuous native EUR300 ledger. The data window, feature rules, prices,
comparison, benchmark and eligibility are frozen before collection.
CAL1, WIR1, WFG1 and all other exact closed configurations remain untouched.

**FX relative leadership.** During a common-direction completed one-hour
move in AUDUSD and NZDUSD, distinct commodity-currency demand may persist
in their relative ranking. Buy the better-performing currency and sell the
weaker one versus USD, including when both are down. Use the same four
contiguous completed M15 observations for both symbols. No asynchronous
substitution, forced paired fill or assumed netting credit. Forecast the
post-entry directional advantage over the reverse leg and cash. Manage
with native ATR Chandelier and a 45-minute safety limit.

**Industrial-metal sparse-update impact.** Copper and Aluminium prices
can temporarily move farther on sparse broker price updates than on
ordinary activity. In seven contiguous M5 bars, the final bar must have
positive tick activity below the mean of the previous six and absolute
body above their mean absolute body. Fade that bar. Forecast partial
reversal versus continuation and cash. Tick count measures broker quote
activity. Use equilibrium reversion with native volatility invalidation
and 60-minute safety limit. No order book, exchange volume or inferred flow.

Observe weekdays at 08:00, 08:30, 14:00 and 14:30 UTC with exact
source observation timestamps, completed aligned bars and no future
updates. Use the following eligible quote at least one second later, with
a ten-minute freshness ceiling for entry. Collect USD conversion and the
relevant source marks in 08–10 and 14–16 UTC. Raw maximum is 80 slots
per week across four targets. Missing/closed markets, missing features
and missing contracts are measured explicitly. No manufactured marks.
EURUSD is used for conversion and is excluded from opportunities.

Use six complete ISO weeks from 6 July 2026 through 16 August for
development, then six complete weeks through 27 September for evaluation.
Historical chronology has already been exposed at the project level.
Collect from the original Pepperstone account via the existing read-only
workflow and custody. Current tariff and margin are conditional historical
scenarios. Aluminium is optional only for prespecified contract failures
or an absent symbol, with the reason retained and no substitution.
Validate eligible contract economics before requesting historical prices.
No new OAuth, live/demo orders or Cloud activation.

Estimate the probability of positive stressed NET and standalone and
incremental stressed NET after entry. Use equal ISO-week means with
at least four distinct training weeks per family. Require positive
standalone and reverse-rule incremental stressed NET after three times
the larger weekly standard error and an upward current-friction
adjustment. This is a descriptive dispersion allowance, not a coverage
claim. Report neutral Brier, gross, central/adverse NET and paired
reverse-rule stressed NET. Run joint, FX-only, metal-only, fixed long,
fixed short and cash with one separate uninterrupted EUR300 ledger each.
Do not substitute directional comparison tokens for predictive evidence.
Attribute economic contribution by the NET difference from each ablation.
Report weekly quote/feature/prediction/NET availability, reservations and
actual closures, margin and sampled floating-equity drawdown. Missing
adverse marks make continuous risk and adverse comparability uncertain.
Repeated deterministic scenario states do not count as independent evidence.

Freeze only sufficient statistics at the chronological cutoff. Replay the
same evaluation data with a fresh research predictor reconstructed from
the digest-checked envelope and require identical signal trace and
funded results. The cBot can read this compact explicit research parameter
at restart without durable storage, Python or network model loading. The
parameter integrity digest is not an approval signature. Account
reconciliation remains separate from the fresh isolated model epoch.
The cBot uses a canonical five-minute clock plus 1.5 seconds, native paired
ticks as of that clock, and EURUSD BID/ASK conversion. Pair freshness is
verified from the native paired timestamp; historical side freshness is
verified separately. The real Cloud feed, per-side age and live margin/fee
observations and restart of
a previously exposed monetary book require additional evidence. No
independent confirmation or model promotion is possible from this study.

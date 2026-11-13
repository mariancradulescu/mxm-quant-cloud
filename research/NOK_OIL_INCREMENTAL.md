# NOKJPY and oil transmission — exposed development protocol

Question. Do completed WTOIL-PERP moves add information about the following
hour's NOKJPY return, above NOKJPY's own prior movement and SEKJPY as a common
JPY/regional risk control? The Norwegian terms-of-trade channel motivates a
positive oil effect, while common risk can move all three. A 60-minute lag
tests delayed adjustment. A [Norges Bank staff memo](https://www.norges-bank.no/en/news-events/publications/Staff-Memo/2016/Staff-Memo-182016/)
motivates the exposure, without establishing its intraday persistence.

Use only the existing selected M5 development bundle from the bound Pepperstone
Europe account, captured for 2025-09-16 through 2026-09-16. Verify the account
commitment, archive manifest and per-series SHA-256, and matching bars by clock.
All periods are exposed development. No exact model from closed studies is called.
The period is a year of bars and confers no economic or independent qualification.

Freeze before scoring. Use the Monday–Friday 08:00–15:00 UTC hourly clock
for concurrent Europe and oil trading. Require every observed M5 close in the
prior hour for each input and through the forward label for NOKJPY. Measure
log returns in bps. A bar opens at its CSV timestamp and completes five minutes
later. Observe entry one M5 close after decision and exit 60 minutes after
entry. Count missing slots. No forward filling. The first 20 full Monday
weeks after capture start are initialization (starting 2025-09-22), followed
by expanding training frozen before each subsequent full week. Keep labels
matured strictly before that week. Drop partial edge weeks from evaluation.

Train two fixed ridge regressions. Standardize using training only, leave
intercept unpenalized, penalize slopes by 0.01 times training count. Compare
NOKJPY/SEKJPY prior-hour returns to the same features plus the prior-hour
WTOIL-PERP return. No feature, sign or horizon selection after results.
Compare paired out-of-week MSE, directional policies and cash, constant long
and constant short on the same clocks. Report incremental MSE and gross bps
with a four-week moving-block bootstrap (5,000 replicates, fixed seed), model
coefficient signs, raw loss quantiles and counts. Bootstrap bounds are
descriptive within exposed development. No claims of causal identification.

Falsification for expenditure on this route: require positive paired MSE
improvement and positive directional gross increment over both the same model
without oil and the stronger constant side. A positive but uncertain result
can support cost work only if the gross break-even all-in cost is plausibly
material on original contract and quote evidence. Cash is the zero reference.
Report available margin as a historical probe estimate, with no funded
admission. Existing bundle lacks paired quotes/fees and as-of volume/margin
evidence at decision; no cost is filled with a synthetic zero. This pilot
reports the gross break-even ceiling for costs, not a EUR NET or DD claim.
Selectively price synchronized quotes and conversion only if the incremental
result warrants it. Preserve the native common ledger and NXE1 gate.

No broker calls, orders, Cloud activation or publication of raw market/account
data. Evaluate a future untouched chronology only after development warrants a
frozen prospective test with contemporaneous as-of contracts and execution costs.

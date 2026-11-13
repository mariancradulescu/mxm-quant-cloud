# US share CFDs — conditional payoff at recurring intraday clocks

Frozen before scoring. The tested mechanism is recurrent timing of execution
flows. If stock-specific buying pressure recurs at a given half-hour on
subsequent sessions, a stock's prior same-clock relative return may predict
which name offers the largest gross opportunity there. Published US stock
research finds recurrence at daily multiples of intraday intervals
(https://doi.org/10.1111/j.1540-6261.2010.01573.x). This pilot tests Pepperstone
CFD bar observations and makes no claim to identify order flow.

## Economic choice

The US500/US30 result eliminated bad outcomes but its average captured move
was only half of central friction. Extending that horizon would revisit the
closed configuration. Short-lived spread recovery can improve execution for
an admitted intent and cannot supply standalone positive gross expectation.
The NOKJPY oil pilot and ETP1 tested recent changes in other markets or names.
Here the signal is repeated clock-specific cross-sectional relative
performance across previous days. Single-name equity moves offer potentially
larger magnitude; the existing archive supplies a year of bars and historical
minimum-margin probes. Single-name tariffs and bid/ask are a material unknown.
The rule uses one long only at any clock to avoid a second spread and margin
leg. Long-only is specific to this test. No exact closed strategy is run.

## Fixed evaluation

Use the 17 US-24 share symbols from the selected development archive identity
manifest, all retained, with the original account commitment and per-series
checksums verified. Use full weeks 2025-09-22 to 2026-09-14 exclusive, all dates
exposed, and all Monday–Friday New York clocks 10:00 to 15:30 at half-hour
intervals. Observe the next M5 close at +5 min, then exit at +30 min.
Require all six closes for a path. This uses observable BID-bar proxies at
both endpoints and no look-ahead to availability when making a choice.
The consecutive policies have non-overlapping modeled holding intervals.

Warm up 12 full weeks. At each later week's start, freeze a score using the
last 40 scheduled weekdays of fully matured same-clock observations.
For each stock and clock, subtract the simultaneous mean return of the
available cohort (minimum eight, including that stock); require at least
20 prior observations for each ranked name. Use the highest mean residual
for the proposed long. On the same decision set compare a policy ranked by
the same stock's mean residual across *all* clocks in the same training
window, and a uniform one-position reference (expected outcome if one name
were chosen uniformly at each clock). No eligibility from future path:
an unavailable chosen name remains unknown, no replacement. Compute the
paired contrast on clocks where the selected model and benchmark paths
and all candidate paths needed by the uniform control are complete.
Report available-case model evidence separately, and count all omitted
clocks. A name is eligible at decision only if its completed decision bar
exists and both training scores exist. Use alphabetic tie breaking.

Report absolute and incremental BRUT bps, both fixed evaluation segments
(first 19 and last 20 weeks), four-week moving-block descriptive intervals,
weekly frequency, percentiles of final signed gross, and favorable/adverse
excursion from sampled M5 closes. Report break-even all-in bps from the
mean gross; costs and NET stay unknown pending own-symbol bid/ask, tariffs
and conversion. Margin estimates are historical probes. Continue to targeted
cost investigation only if both segments have positive absolute gross and
positive increments versus both controls and the combined gross is material
enough to warrant cost verification. Cash is zero. No claim of funded
portfolio performance, drawdown or HARD21. No new broker calls for this
first diagnostic, no raw market data in public outputs, no orders or Cloud.

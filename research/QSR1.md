# QSR1 · Quoted-spread shock recovery

Freeze before reading data. Hypothesis: a one-sided widening of the quoted
spread can temporarily displace the midpoint. After the spread returns to
baseline, the shock direction may still predict a residual reversal.

Use the original Pepperstone LIVE account through the read-only Open API.
Use EURUSD and GBPUSD historical BID/ASK ticks, including EURUSD for causal
EUR conversion. Use twenty consecutive exposed weeks from 2026-06-22 to
2026-11-09 exclusive, ten for selection and ten for exposed audit. Take the
first ten minutes of 08:00 and 14:00 UTC each weekday and sample every 30
seconds. On equal millisecond updates use the last returned side update in
decoded chronological order. Reject stale sides older than two seconds and
incomplete pages. No bars, DOM or invented ticks.

Compare spread and midpoint at -20 seconds, -5 seconds and the decision.
Require spread normalized at decision to no more than its -20s width.
Predict reversal of the -20s to -5s midpoint displacement. The selected
signal requires exactly one side unchanged and shock width at least twice
baseline. Benchmark all eligible same-direction reversals within the same
symbol, week and session, weighted by selected count. Cash is zero.

Price entry at decision +1 second and exit at decision +31 seconds using
fresh original quotes. Central buys at ASK/sells at BID with observed
current-contract fees and causal EUR conversion through native valuation.
Adverse adds one observed half-spread on each side as a sensitivity.
Exclude intervals crossing rollover. Historical fees, slippage and fills
are not certified. Report equal-weight active-week averages in EUR per
minimum-volume hypothetical round trip, separate from portfolio accounting.

In both phases require 30 valued signals, eight active weeks, positive
adverse absolute and incremental means and positive-week sign tests for
both, adjusted by eight across symbols, comparisons and phases. The sign
test assumes independent week signs and is exploratory on exposed data.
Require current minimum margin below EUR300. A survivor merits common
native funded replay, separate independent evidence and full marks.
Do not sum these episodes into portfolio NET, count them as HARD21 or
infer equity drawdown from them.

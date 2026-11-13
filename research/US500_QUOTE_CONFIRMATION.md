# US500 quote confirmation — frozen exposed-development protocol

## Research choice

PR #261 shows why an economic link in levels can have little incremental
short-horizon value. In NXE1 the cheaper US500 contract was a context series.
Its current EUR34.29 minimum margin compares with EUR236.48 for US30.
NXE1's US30 trading rule lost EUR0.5637 adverse per complete hypothetical
label, and the EURUSD rule lost EUR0.2726. MSE1 showed that missing holding
marks and currency conversion can dominate the result. The earlier US500
volatility-persistence study tested directional agreement in completed bars.
The spread-recovery study tested entry delay after a wide spread for an
existing intent. Neither protocol asked whether two-sided *quote movement*
adds information to a bar direction about its future executable markout.
DCP1's displayed-depth pilot did not establish an eligible historical depth
panel. Here US30 contributes a cross-index quote check with no capital leg.
Keep the new-instrument direction open; neither the US30 trade rule nor the
NOKJPY rule is reopened. The archived US30 contract makes a funded US30 test
a lower priority on this evidence.

## Hypothesis and test

Test whether actual movement on both sides of the US500 and US30 quote
over the last 15 minutes confirms that US500's bar direction is market-wide,
with enough delayed adjustment to cover immediate entry and exit friction.
A widened quote or a lone moving side can make a bar signal look stronger
than the bid and ask together. This is an empirical prediction, not an
identification of information or a claim about order flow.

Use the original encrypted NXE1 tape from run 43377275493, artifact
14015883688, and original public receipt 14016671008. Verify both artifact
contents and the plaintext SHA-256 before scoring. No Open API calls.
Use every weekday clock 10:00–13:30 America/New_York every 30 minutes.
Require exact 5-minute original quote clocks at decision and 15 minutes
earlier on both indices, and three completed contiguous M5 US500 bars
over that interval. Use the sign of the change from first bar open to
last close as the baseline direction. A clock is confirmed if *both* bid
and ask strictly move in that direction on both indices. A flat bar has
no direction. Compare the baseline to two filters on this same tape:
US500 bid-and-ask confirmation alone, and both-indices confirmation.
No optimized threshold, same direction, 5-minute delayed entry, 25-minute
holding horizon. An exit lands at the next decision clock, before that
decision's entry. Require every US500 holding quote plus original EUR
conversion. Restrict to the observed zero commission/zero conversion-fee
US500 contract and a known intraday hold that does not span rollover.
Unknown observations remain unpriced for the policies that would trade them.

Score observed BID/ASK, native-tape slippage on each side for central, and
the NXE1-style extra round-trip full spread at entry and exit plus two more
units of modeled slippage for adverse, using signed EUR conversion. These
are conditional EUR markouts at the original observed minimum size,
without fill or historical tariff certification. Compare cash, constant
long and short, all bar signals, US500-only confirmation and two-index
confirmation. Evaluate incremental adverse EUR per common complete clock,
including zero from each filter's abstentions. Keep 17 full calendar
weeks, show results by week and chronology, missingness, loss tail, sampled
worst holding markout, frequency and minimum margin. Four-week moving-block
95% intervals are descriptive on exposed history. This is a fixed nested
comparison with a single primary contrast versus US500-only confirmation.
Continue to financing research only if the two-index policy has positive
absolute adverse value and exceeds US500-only, all bar signals and the
stronger constant-side control on the common calendar, with directionally
positive results in both calendar segments (first 8 and final 9 weeks).
Estimate uncertainty; even a pass is development support only. An economic
result on this archive uses ex-post contract terms and sampled quotes.
The existing C# admission boundary still requires as-of contract/schedule,
monitoring and funded common-book risk, plus independent confirmation.

Protected source-only job with the existing custody secret, no OAuth,
orders, Cloud activation, exact NXE1 replay, or publication of raw prices.

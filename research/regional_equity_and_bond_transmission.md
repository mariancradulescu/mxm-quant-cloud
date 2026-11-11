# Regional equity repricing and euro bond transmission

Exploratory Pepperstone study. Freeze the two configurations, costs, coverage
and decision gates in the research PR before accessing any outcomes.

- **AAXJ.US, regional equity repricing.** At 10:00 New York, compare the
  completed 09:30–10:00 local simple returns in AAXJ.US and ACWI.US. Trade
  the sign of the difference in AAXJ.US from 10:05 to 11:05. If the
  difference is zero, abstain. The first half-hour can reveal incremental
  regional demand following the Asian session. Compare with AAXJ.US own
  continuation, ACWI.US continuation, always long, always short, and zero.
  ACWI.US is informational only. Same clocks, same target and costs.
- **EUBund-F, maturity transmission.** At 10:00 Berlin, observe the
  completed 09:00–10:00 returns of EUBobl-F and EUBund-F. On opposite
  nonzero signs, trade EUBund-F in the direction of EUBobl-F, 10:05–11:05.
  The hypothesis is that repricing in the shorter maturity leads a
  subsequent move in the longer maturity after an initial disagreement.
  Compare with EUBund-F own continuation, always long, always short, and
  zero. EUBobl-F is informational only. Same clocks, target and costs.

From 2026-05-04 through 2026-10-30, split into two fixed 13-week halves.
Use weekdays and contiguous completed M5 bars. The first bar opening at the
start of a source interval supplies its opening reference. Missing bars
and nonpositive prices are absent evidence. No forward fill, session
substitution or indicator tuning. Report authenticated bar count and tick
volume sum per symbol. Report both halves, all benchmarks and sample sizes.
Weight each active week equally. A neutral benchmark direction scores
zero at that clock. Frozen weekday set is an observation calendar,
independent of HARD21 eligibility.

Before scoring, require a currently enabled target, contract metadata,
positive current minimum margin at or below EUR300 on both sides, and
contract session coverage of the modeled execution interval. Use fresh
paired historical BID and ASK no older than 20 seconds at each entry and
exit. Record actual sampled spreads and use executable sides, current
minimum-volume contractual commissions with causal EURUSD conversion as
needed, and conversion charges on absolute converted P&L where applicable.
No execution interval may cross a documented financing clock. Current
terms are conditional and their historical continuity is uncertified.
Central/adverse round trip slippage assumptions are 0.5/2 bps of opening
mid notional. Raw authenticated data and account identifiers are private.

In each half require at least 12 priced events across at least six weeks
and at least 75% priced coverage of bar-complete signals. Require positive
absolute adverse bps and a strict adverse advantage over every benchmark
in each half. Coverage failure means insufficient evidence. Failing the
economic comparison with sufficient coverage rejects the exact rule.
These are exploration admission gates. A pass calls for the existing
common C# EUR300 replay with floating equity, funded allocation and
portfolio ablation. A descriptive cost-conditioned result alone confers
no promotion, certification of financed NET, HARD21 or drawdown.

Source API: https://help.ctrader.com/open-api/symbol-data/

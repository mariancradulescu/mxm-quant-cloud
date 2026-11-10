# CIT1 · Intraday inventory transfer

Frozen before scoring. Owner v2.0. Source artifacts 13273950911 and 13278617985,
recovered and verified inside the existing custody environment. No broker calls.

- GER40 at 14:00 UTC. The 08:00–12:00 move has the opposite sign to the
  13:00–14:00 move. Test continuation in the direction of the late move as
  dealers unwind morning inventory before the US afternoon session. Benchmark
  continuation of the morning move on identical entry and exit clocks.
- XAUUSD at 13:00 UTC. If EURUSD and GBPUSD both moved opposite to gold over the
  preceding hour, test gold catching up to the broad USD move. Benchmark
  continuation of gold's own last hour on identical entry and exit clocks.
  GEP1 used gold as a predictor for JPY and used USD funding to predict indices.

Use exact completed M5 closes with a five-minute delay. Exit at the next M5
close after the first nonpositive signed move at a completed 15-minute check,
with a 60-minute maximum label horizon. Missing required closes exclude the
label. The fixed UTC clocks are analytical sampling times.

Use 26 development, 13 selection and 13 subsequent exposed audit weeks.
Score all phases once with fixed signs, thresholds and groups. Report active
weekly means, with a three-lag HAC normal lower bound and a Bonferroni divisor
of 16 for the two groups, four tests and two scored partitions. Require at least
30 conditional cost labels and ten active weeks in each scored partition.
Positive adjusted bounds are required for gross and gross increment, and
adverse absolute and adverse increment. This is an exploratory screen.

Conditional basis-point sensitivity uses original observed cost contexts,
including a separate P&L conversion wedge. Missing cost or rollover terms
leave the conditional result unknown. Holdings crossing a recorded rollover
are excluded from the sensitivity. Keep predictive labels separately.
Current observed minimum margin is descriptive. Bar closes and sparse cost
samples alone cannot certify matching entry, exit and floating-equity BID/ASK.
No funded replay, portfolio NET in EUR, HARD21 or global drawdown is inferred
from them. A passing candidate needs matching source coverage and the existing
shared C# ledger with one EUR300 starting balance, then independent confirmation.

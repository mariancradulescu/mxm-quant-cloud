# Frozen LDP1 replication · W39–W43

Run the exact original LDP1 signal, sizing, adaptive exit, financial
admission and fill-time cancellation policies from PR #180, with no tuning.
Use only the original authorized read-only Pepperstone account and observed
BID/ASK with EUR conversion. The portfolio and each separate reference start
with one continuous EUR300 capital balance.

Change only the observation dates and source identity. Use five contiguous
complete weeks from 2026-09-21 through 2026-10-26 exclusive, with warmup from
2026-09-18 08:00 UTC. These dates are disjoint from LDP1 W26–W30; other
research has used this period, so this is exposed historical replication.
Current contract observations are applied retrospectively as in the original.

Report absolute central and adverse NET, same-clock descriptive long/short,
funded long/short with their own admission and exposure, marginal contributions,
weekly results, sample drawdown and the fill-time cancellations. A missing
adverse funded result stays unknown. Use the original unmodified cost stress.
Negative adverse NET or weak weekly stability refutes robustness in this window.
A favorable replication cannot itself independently qualify the strategy.

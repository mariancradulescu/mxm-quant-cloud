# BMR1 · Scheduled US macro releases and continuation after 15 minutes

Register before market collection. The BLS CPI and Employment Situation
releases reset public information on inflation and labor. A coherent move
across dollar pairs could persist as market participants reprice. A
negative realized gross move, weak absolute NET or failure versus the
fixed-side comparisons weighs against this continuation premise.

Use the official [BLS 2026 calendar](https://www.bls.gov/schedule/2026/)
for six CPI and six Employment Situation releases from May through October.
The fixed days are in `bmr1.py`. All releases in the sample are scheduled
for 08:30 Eastern (12:30 UTC). Score once per symbol per event at 12:45 UTC
plus 1.5 seconds, using only the completed 12:30–12:45 M15 candle.
No consensus, release values or surprise labels enter the signal.

- EURUSD. Require coherent EURUSD and GBPUSD moves of at least 8 and 6 bps
  respectively. Forecast continuation in the EURUSD direction.
- XAUUSD. Require the same FX agreement and a gold move of at least 15 bps
  in the same direction. Forecast continuation in the gold direction.

Use the magnitude of the target move, existing native economic gates,
prediction invalidation exit and 45-minute ceiling. Collect only event-day
warmup bars and BID/ASK from 12:00 to 15:00 UTC. Use authentic account
terms retrospectively and the existing model slippage and adverse stress.
GBPUSD is context only. EURUSD is a target, context and conversion source.
Run a common continuous EUR300 ledger, one-leg ablations, funded long and
short and matched-clock descriptive comparisons. A common USD exposure
can make both legs redundant. The ablation tests incremental contribution.
This sparse, globally exposed event sample can test a portfolio sleeve.
Its frequency cannot meet HARD21 by itself. Independent confirmation is
required before any promotion.

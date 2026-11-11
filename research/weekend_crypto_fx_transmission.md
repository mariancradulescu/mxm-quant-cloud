# Weekend crypto information and Asia FX price discovery

OWNER v2.0 exploratory screening before admission to the native EUR300
portfolio. Pepperstone offers weekend crypto CFD sessions. When liquid FX
is closed, BTC and ETH can reflect broad risk information. Their agreement
may predict a remaining repricing in AUD and NZD after early FX price
discovery. Either information is already priced or weekend crypto-specific
noise can falsify the hypothesis. MBF1 traded ETHUSD weekend drift; this
protocol uses BTCUSD and ETHUSD strictly as context and trades only FX.
AUDUSD and NZDUSD share USD and regional exposure; treat them as a single
family and a single weekly observation, not independent evidence.

- Calendar: Monday 2025-11-17 through Monday 2026-11-09 inclusive, 52
  observations in two frozen consecutive 26-week halves. UTC throughout.
  These are exposed exploratory calendar windows, not an untouched holdout.
- On Monday use the sign of the return from Saturday 04:00 M5 open to
  Sunday 16:00 M5 close for each of BTCUSD and ETHUSD. Require both signs
  equal and nonzero. Fixed endpoints avoid the FX reopening. Neither
  interpolation nor a minimum return optimized on this source is used.
- At 01:05 Monday model the agreed direction in both AUDUSD and NZDUSD.
  Close at 02:05. Compare with each FX symbol's own completed 00:00–01:00
  direction, cash, long and short on identical observation clocks. Require
  both FX symbols to have contiguous feature and label M5 bars. A flat
  direction in an own-FX benchmark is cash. No weekday, target or
  alternative clock selection. Only executed simulations are modeled.
- Cost every matched observation at minimum size using bid/ask no older
  than 20 seconds at both ends, signed EURUSD conversion, observed current
  commissions and explicit P&L conversion costs, and intraday session and
  financing checks. Round-trip slippage is 0.5/2 bps central/adverse.
  Report the equal-notional mean of the two per-leg conditional bps as
  an exploratory family screen and retain both leg results. This is not
  an allocation policy. Current simultaneous minimum margins must fit
  within EUR300 before collection. Current terms are not historical tariffs.
- Before accessing returns require at least four of the final five fixed
  Mondays with executable paired quotes and costs on both legs. The
  preflight performs valuation checks without publishing or selecting on
  outcome. A failed gate ends the study without retrieving trendbars.
- For admission require at least 12 cost-complete weeks and at least 75%
  coverage of bar-complete signals in each half. The adverse family mean
  must be positive and beat all benchmarks. The one-sided exact positive
  sign statistic versus cash and versus own-FX continuation must be at
  most 0.10 in each half. Treat this as a screening statistic, not a
  calibrated guarantee under serial dependence. No pooling of targets as
  independent samples and no inversion, horizon search or favorable subset.
- An admitted family still needs the native common ledger, synced marks,
  exposure overlap, adverse free margin and family ablation. The weekly
  schedule contributes at most two potential closures before allocation
  and is evaluated only for diversification across session and information
  source, with HARD21 at system level. Raw source is private. Zero orders
  and no Cloud activation.

Broker session context: https://pepperstone.com/en/markets/cryptocurrencies

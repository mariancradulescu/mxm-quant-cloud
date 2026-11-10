# MCT2 · Crypto persistence and gold range release

Freeze before collecting prices. ISO W36–W40 from 2026-08-31 through
2026-10-05 exclusive is globally exposed. Native EUR300 research only.
Use Pepperstone original quotes on the weekday 13:00–19:00 UTC M5 grid.
Use completed M15 decision clocks 13:00–17:00 UTC exclusive plus 1.5 seconds.
Forecasts use uninterrupted closed-bar inputs, current authenticated
contract terms applied retrospectively and the existing execution stress.

- ETHUSD persistence when equity movement is subdued. Require absolute NAS100
  H1 return at most 8 bps, ETHUSD H4 return at least 40 bps and H1 return at
  least 15 bps in the same direction, with the final M15 body agreeing.
  Forecast continuation. Use the H1 move as driver and the existing Chandelier
  exit with a 60-minute ceiling. The hypothesis is crypto-specific sustained
  repricing during a quiet equity interval.
- XAUUSD release from compression with dollar confirmation. Require the
  previous four M15 candles to span at most 60% of the prior four-candle
  range. The latest completed M15 close must break that compressed range
  in the direction of the contemporaneous EURUSD H1 move, at least 4 bps
  in absolute value. Use the latest body magnitude and existing prediction
  invalidation exit with a 60-minute ceiling. The hypothesis is a gold range
  break backed by common dollar repricing.

NAS100 is context only. EURUSD is both context and USD–EUR conversion.
Use the existing selector and native ledger for the combined run, one-leg
ablations, and fixed-side long and short references. The latter retain raw
opportunity clocks and run their own allocation and exits. Report matched
entry/exit clock references separately, plus cash, costs, margin, sampled
equity and weekly completions. Qualification requires further independent
evidence and the system requirements in the owner specification.

## Evidence used to choose the next mechanisms

The original Pepperstone symbol and contract records govern technical and
financial eligibility at each replay. These economic dispositions apply to
the specified instrument, mechanism and regime.

| Target | Mechanism and regime | Status | Context or conversion |
|---|---|---|---|
| XAUUSD | CIT1 FX disagreement, fixed 13:00 UTC, M5 closes | Closed as tested, negative later windows and limited coverage | EURUSD, GBPUSD context |
| XAUUSD | RRP1 defensive rotation, M15 and H1, afternoon | Positive exploratory in joint book, insufficient to qualify | US500 also traded, NAS100 context and EURUSD conversion |
| US500 and NAS100 | RCG1 regional participation, H1 filter | Closed as tested, negative after conditional costs | GER40 and UK100 context |
| US500 | RRP1 NAS leadership transmission, M15 and H1, afternoon | Positive exploratory in joint book, inferior to matched short at portfolio level | NAS100 context, EURUSD conversion |
| GBPUSD | RCG1 implied CADJPY confirmation, H1 filter | Closed as tested, incremental point estimate insufficient to cover costs | USDJPY and USDCAD context |
| GBPUSD and EURUSD | QSR1 tick spread normalization, fixed intraday clocks | Inconclusive coverage, one negative evaluable EURUSD episode | EURUSD also used for conversion |
| GBPUSD | OTC1 GBP relative strength, H1 and M15, afternoon | Closed as tested, adverse loss and below funded long | EURUSD context and conversion |
| SpotCrude | PR #167 US tick activity drift, H1 and M15, US session | Closed as tested, negative economics | ETHUSD separate candidate, EURUSD conversion |
| SpotCrude | OTC1 WTI local basis unwind, H1 and M15, afternoon | Three signals, zero funded admissions | Brent context and EURUSD conversion |
| ETHUSD | PR #167 M5 liquidity wick absorption | No funded admissions | SpotCrude separate candidate, EURUSD conversion |
| EURJPY and USDJPY | JRC1 risk participation and volatility unwind, H1 and M15 | EURJPY closed on losses, USDJPY inconclusive with zero signals | AUDJPY context, USDJPY and EURUSD for conversion |
| XAGUSD and NZDUSD | LDP1 silver repricing and local NZD unwind, H1 and M15 | Initial exploratory positive, exact configuration closed after failed replication | EURUSD and AUDUSD context, EURUSD conversion |
| ETHUSD and XAUUSD | MCT2 H4/H1 persistence and M15 range release | Exact configurations closed, both negative marginal NET central and adverse | NAS100 context, EURUSD context and conversion |
| EURUSD and XAUUSD | BMR1 continuation after scheduled CPI and US employment releases, completed M15 reaction | New preregistered hypotheses | GBPUSD context, EURUSD context and conversion |

Sources: [CIT1](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42773706175/artifacts/13742509291),
[RCG1](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42776222946/artifacts/13743777877),
[QSR1](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42778550820/artifacts/13744922391),
[RRP1](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42781700638/artifacts/13747681714),
[PR #167](https://github.com/mariancradulescu/mxm-quant-cloud/pull/167),
[LDP1 replication](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42803043068/artifacts/13757931330),
[JRC1](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42811179071/artifacts/13764030872),
[OTC1](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42814122228/artifacts/13765215820).

MCT2 recorded 20 modeled closures, −32.2647 EUR central and −33.5675 EUR
adverse. See the [original receipt](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42822802931/artifacts/13769185362)
and [frozen protocol version](https://github.com/mariancradulescu/mxm-quant-cloud/blob/5ac826231f9ee39d2c274eca86cb02ae7d07f313/research/MCT2.md).

# PRR1 · Broad-market pullback resumption and crude range rejection

Registered before accessing the PRR1 market data. Continuation under OWNER v2.0.
Use one continuous EUR300 native historical book from 2026-04-06 through
2026-05-01 UTC, four complete ISO weeks, with pre-window warmup. Treat all
dates as exposed development. Preserve chronological weekly results without
resetting cash or substituting markets, dates or triggers.

## Predictions and management

- **US2000, broad-market pullback resumption.** Smaller US companies can
  participate when broad risk appetite persists after a temporary setback.
  Use synchronized completed M15 bars. The US500 return from the first open
  to the fourth close in the hour immediately before the last two M15 bars
  must exceed in magnitude the US500 mean absolute return across the
  preceding two non-overlapping hours. US2000 must agree over that same
  hour. The penultimate US2000 bar must move against this direction and
  the last must close beyond that bar's extreme in the original direction.
  The projected magnitude is the absolute US2000 impulse return, an
  exploratory forecast input. Manage with the existing M5 ATR Chandelier
  trail, initial volatility invalidation and a 120-minute safety ceiling.
- **SpotCrude, rejection of price outside balance.** A break of a three-hour
  range with elevated quote activity can represent temporary liquidity
  demand. Test return to balance when the next completed M15 candle closes
  inside that range. The breakout candle must close outside the range,
  and its tick volume must exceed the mean of the 12 prior M15 candles.
  Fade the failed direction only while the mean of the last eight M15
  closes lies farther inside in the proposed direction. The distance
  to that mean is the exploratory forecast magnitude. Use the existing
  M15 equilibrium target frozen at fill, initial volatility invalidation
  and a 90-minute protective ceiling. Tick volume measures broker price
  updates. No inventory release, Brent basis or exchange volume proxy.

Evaluate synchronized closed M15 decision bars at 14:30–17:30 UTC inclusive
on weekdays, with 1.5 seconds of observation latency. Process native quotes
and M5 management clocks from 14:00 until 20:00 UTC, allowing the longest
safety exit plus its next executable mark. An absent price remains unknown.
Forecast direction uses only OHLC and tick-volume from completed bars.
Require fully contiguous feature windows and shared clocks with US500 for
US2000. M15 is aggregated from original, contiguous M5 bars. Use exact
price-side broker observations and EURUSD conversion for cost, fills,
volatility exit checks and floating equity. No intrabar stop-fill assumption.

## Execution and decision

Original Pepperstone read-only data and current authenticated min-size
commission, conversion and margin scenarios through the existing C# adapter.
Preserve the exact native input tape in existing run-bound encrypted v2 custody.
Existing common ledger, selector and adverse costs remain in force. Run
joint, both one-family ablations, and direction-fixed long/short ledgers
on the same signal opportunities with the same exit policies and costs.
Cash is zero. Compare aggregate EUR NET and ablation contributions, weekly
fully closed trips, held equity samples, financing and cost rejections.
Meaningful positive evidence requires positive adverse NET above the best
constant-side funded alternative and cash, with comparable financed fills,
complete held marks and positive marginal adverse contribution for any
sleeve proposed for further work. Zero or unresolved closures are insufficient.
Four exposed weeks can falsify or prioritize further research. Qualification
requires independent evaluation. No LIVE/DEMO orders or Cloud activation.

# One fixed native H4/M15 economic challenger — predeclared 2026-11-02

## Chronology and non-selection commitment

The source has already been collected and independently verified on the original Pepperstone Europe LIVE account in protected GitHub Actions **41476636915**. Public source-only statistics (15,113 valid H4/M15 bars, six symbols, authentic 60-second BID/ASK samples, H4 observations across thirteen calendar months) were disclosed before designing this test. **No bar-level returns, signal outcomes, direction labels or economic prices have been exposed in this new repository's public record.**

This is a **new exploratory mechanism**, not the closed adaptive H1 probabilistic model and not a relaunch of the older Ridge or PRIMARY145 policies. It is *not* independent confirmation: historical dates might have been exposed to prior research and the mechanism was specified after source coverage became known. Its purpose is to reject unpromising configurations early and inform a separate future prospective test.

## Immutable single hypothesis and evaluation

For every genuinely enabled symbol, assess H4 and M15 **separately**, with the **same** fixed rules and no parameter search:

1. The bar is completed and causally available. Use only its own complete OHLC and the previous 12 completed contiguous same-timeframe bars.
2. Direction is **long** if the signal close exceeds the highest high of those preceding 12 bars, **short** if it is below the lowest low, and **no proposal** otherwise.
3. The proposed entry is the open of the immediately following bar (price-only OHLC proxy, not a historical ASK/BID execution), and its single proxy exit is the close of the fourth subsequent completed bar. No stop fill, trailing, overnight cost or true margin is inferred.
4. Exclude every signal with a missing bar in the preceding 12 or following 4. No overlap of proxies within each instrument and timeframe. Different instruments/timeframes may coexist but **are not summed into fictitious one-account trades**.
5. Convert signed gross source deltas to *symbol-specific* pips using the Pepperstone source symbol `pipPosition`. Only report pooled **per symbol / per timeframe** gross-pip mean, median, and direction-hit rate if at least 20 complete opportunities exist. No cross-asset pip/P&L aggregation.
6. Describe three chronological slices **60% / 20% / 20%** of source time, with all thresholds fixed, no tuning. These slices remain *development-only* and **must not** be labelled pristine independent out-of-sample confirmation.
7. Count observed weeks containing 21 **price-only proposals**, never claim HARD21 fulfilled by these nonexecuted proxy trades.

The single source is pulled only from an existing encrypted GitHub Actions artifact, with workflow-run-bound v2 decryption using the **already-installed** custody RSA private key. Recompute the **original** native C# source receipt and demand exact byte-data-equivalent JSON parity before evaluating the new `EconomicBreakoutProbe` core in a second distinct mode `--economic-screen`.

No future signal is allowed to affect entry direction. Entering at the next OHLC bar OPEN and exiting at the fourth CLOSE is deliberately an *unfunded price-price approximation*: no broker fill, BID/ASK at each entry/exit, 200 EUR margin, min lot availability, commissions, slippage, swaps, conversions, intrabar liquidation equity or certified drawdown is established. A positive gross-pip proxy is **never** a positive NET EUR edge. Any non-positive time-aligned gross score discourages promotion of this exact configuration; no sign inversion or retuning after viewing results.

This is one bounded, falsifiable economic experiment that does not require recollecting source, infrastructure rebuild, historical key recovery, Sandbox, refresh token, demo/LIVE orders or Cloud activation. No research output will expose private market candles, account identities or per-trade observations.

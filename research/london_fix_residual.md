# LFR1 — London closing-fix relative FX dislocation

Prospective exploratory protocol under [OWNER v2.0](../docs/OWNER_SPEC.md).
The [WMR methodology, January 2026](https://www.lseg.com/content/dam/ftse-russell/en_us/documents/ground-rules/wmr-fx-methodology.pdf)
defines the London 16:00 closing spot reference and a centered five-minute
sampling window. Benchmark-linked demand can temporarily displace one currency
relative to other USD-quoted currencies. Test whether its relative displacement
decays after the window. The benchmark clock is public metadata. Dealer quotes
do not measure benchmark trades, order flow or actual fixing completion.

## Frozen sample and comparisons

- 26 weeks of exposed development, 2026-05-04 through 2026-10-30, Monday–Friday.
  Two consecutive 13-week halves. No alternative periods or subset selection.
- AUDUSD, GBPUSD and NZDUSD provide the cross-section. EURUSD converts P&L and
  commissions where applicable. Use the original Pepperstone EUR account,
  current enabled symbol contracts, minimum volume/grid, both current minimum
  margin directions, short permission, session and rollover. If a basket
  member is currently ineligible, leave the basket unscored. Calendar clocks
  remain in the denominator when data are absent. No substituted pairs.
- Use Europe/London time. At 15:57:29 and 16:02:30 observe the last BID and ASK
  individually at or before the clock, at most 20 seconds old. Reject
  truncated, absent or crossed observations. Compute midpoint simple returns
  in bps. Subtract the median of the three returns from each. Choose the
  unique largest absolute residual when it strictly exceeds twice the larger
  of that market's two observed spreads in bps. Fade that residual. A tie or
  a failed hurdle abstains. There is at most one modeled position per clock.
- Enter at 16:03:00 and exit at 16:18:00, using identical as-of rules for the
  target and EURUSD. Apply executable sides, original current minimum-volume
  commissions and FX conversion fee, plus 0.5/2.0 bps modeled round-trip
  slippage. Current terms and modeled slippage yield conditional bps.
  Compare with long, short and cash on the model's same priced signals.
- Run exactly the same logic centered at 15:15 London, away from hourly and
  half-hourly fixing windows, as a time-of-day control. Use same-date paired
  differences of adverse policy bps, counting causally known abstentions
  as cash and excluding days with unknown pricing in either policy. Disclose
  each clock, pair counts, selection by symbol and both chronological halves.
- In each half, require at least 20 costed fix trades across at least eight
  weeks, at least 75% priced fix signals, at least 20 costed control trades
  across eight weeks, at least 75% priced control signals, and at least 50
  matched days across ten weeks. With coverage, the fix's equal-week-weighted
  adverse NET must exceed each same-clock comparator and its adverse policy
  difference against the time control must be positive. A covered failing
  half rejects this exact rule. Both halves passing permits a separately
  registered native common-capital replay only. Otherwise evidence is
  insufficient. No p-value or independent confirmation claim.

## Source and portability

The evidence registry and original studies provide exposed calendar, route and
friction evidence. SQIC1's public aggregates cannot supply this basket's
simultaneous fixing/control quotes. Prior H1/M5 bars cannot supply two-sided
quotes at these second-level clocks. Reuse the existing transport, decoder,
margin/session and commission routines. Read only narrow historical tick
windows, and read entry/exit/FX only after a signal. The theoretical upper
bound is 5,200 historical requests plus a small roster/contract preflight.
Store wire provenance in the existing encrypted v2 custody format and publish
aggregate results only. No closed studies run.

A native C# cBot can observe the three symbols' BID/ASK ticks and maintain
as-of snapshots for the same UTC-converted London schedule using cTrader Algo
MarketData. Desktop CLI can test a C# implementation offline. Live depth is
outside this hypothesis. Cloud runtime behavior and native parity remain
unverified. The maximum standalone frequency is five closures per week, so
any contribution is conditional on the shared allocator, EUR300 funding,
marginal portfolio benefit and independent validation.

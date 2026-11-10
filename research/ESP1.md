# ESP1 — small-cap repricing and release-clock oil liquidity

Frozen before price access. Two distinct hypotheses, scored separately, no
optimization or substitutions. Exploratory historical evidence only.

- **US2000**: capital rotation into or away from smaller companies can
  persist once the opening hour is past. At noon New York, sign the completed
  11:00–12:00 US2000 minus US500 simple return if magnitude is at least 20 bps.
  Take the relative move's sign in US2000, 12:05–14:05. US500 is context only.
  This tests post-opening continuation of size-specific repricing, distinct
  from the frozen NAS100 opening dispersion fade.
- **SpotCrude**: an initial WPSR-clock price jump can reflect temporary
  liquidity demand that reverses after the first repricing. Use only the
  10:30–10:40 New York M5 path on standard WPSR Wednesdays. Fade moves of
  at least 35 bps, 10:45–11:25. Same rule on Tuesday is the timing control.
  Exclude entire weeks of May 25, September 7 and October 12 per EIA release
  exceptions. No actual inventory surprise or order flow claimed. This
  differs from general H4 impulse persistence and Brent/WTI convergence.

Twenty-six weeks from May 4 through October 30 2026, two 13-week chronological
halves. Closed contiguous M5 paths, no forward fill. Predeclared thresholds
filter negligible impulses relative to prior MEF1 observed spreads; they are
hypothesis parameters rather than estimated optima. Historical BID and ASK as
of modeled entry/exit must each be no older than 20 seconds. Use executable
side for each modeled position and same-clock long/short alternatives. Apply
authenticated current minimum-size commission, any recorded P&L conversion
fee, and 0.5/2 bps assumed central/adverse round-trip slippage. Report
equal-weight active-week bps, normalized on USD opening mid notional, no
claim of historical tariff or EUR net. Intraday clocks avoid daily rollover
of these contracts. Current individual margin is a necessary preflight only.

In each half require 4 active weeks and at least 10 complete priced US2000
or 5 complete priced SpotCrude main observations. Require positive adverse
and a strict advantage over both directional alternatives. SpotCrude must
also beat its timing control in each half with at least five priced controls.
A pass justifies native common replay, not qualification. No actual fills,
orders, Cloud, HARD21 or portfolio drawdown claim. Missing source stays unknown.

Sources: [FTSE Russell methodology context](https://www.lseg.com/en/ftse-russell/indices/russell-us),
[EIA release schedule](https://www.eia.gov/petroleum/supply/weekly/schedule.php),
[cTrader historical bars and ticks](https://help.ctrader.com/open-api/symbol-data/).

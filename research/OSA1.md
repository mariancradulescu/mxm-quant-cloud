# OSA1 — oil news absorption at the US cash open

Fixed exploratory screen before collection. Oil reprices while US producer
shares are closed. At the open, broad equity order flow can temporarily
dominate company exposure to oil. Test whether the opening adjustment is
incomplete, using two integrated producers, Exxon Mobil and Chevron. Prior
WTI and equity experiments did not test this producer basket or cash-open clock.

- Original Pepperstone Open API, same authenticated EUR account. SpotCrude is
  a signal only. US500 is a market comparator only. XOM.US and CVX.US are the
  fixed targets, with no substitution. Verify enabled status and current
  minimum margin in both directions for each equity before scoring.
- One equal-weight target basket, one horizon, one threshold. 26 weeks from
  2026-05-04 through 2026-10-30, New York local time. At 09:45, use the closed
  09:00–09:30 SpotCrude M15 path. Trigger at absolute log return of 40 bps,
  and use its sign. Evaluate the target from 10:00 to 10:30. Every bar close
  in each required path must be present. No interpolated prices or holidays.
- Same-clock always long and always short are descriptive comparators.
  Subtract same-clock US500 return before signing to check market-direction
  dependence. This is a diagnostic with unit beta, not a hedged fill.
  Aggregate by session first and then equally by active ISO week.
- Necessary gate to justify historical BID/ASK collection and a shared native
  C# replay: at least 30 complete sessions across 12 active weeks; mean
  signed gross exceeds both directional means and mean signed market-adjusted
  return is positive in each calendar half (13 weeks each). No tuning, no
  per-stock selection, no inference from the halves as independent confirmation.
- Current tariff and current stand-alone minimum margin are provenance.
  M15 prices cannot establish fills, round-trip NET, capital contention,
  HARD21 or floating-equity risk. No order, activation or new secret.

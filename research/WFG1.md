# WFG1 · Liquidity absorption, compression release, and chronological funding gate

Preregistered on the exact encrypted FCE1 Pepperstone source (run 43036474843,
artifact 13863803890). There are zero new broker calls. Both segments are
globally exposed. February 9–27, 2026 is selection history. March 2–20 is the
chronologically later development evaluation, with a weekend between segments.
Only results fully closed before March 2 may inform the locked evaluation
selection. There is no re-selection within evaluation and no independent
confirmation claim.

- **Local FX liquidity absorption** (AUDUSD, GBPUSD, NZDUSD): on completed
  M5, use the 12 bars preceding the latest two as the local range. The
  penultimate bar sweeps exactly one boundary and closes inside; the last
  bar advances inward and closes inside, with the prior-range mean still
  ahead. Require EURUSD's synchronized penultimate bar to remain inside its
  own preceding range. Forecast a move toward the local equilibrium, with
  gross magnitude equal to the remaining distance to the prior mean over the
  latest close. Use the existing entry-frozen M15 equilibrium and ATR
  protection, with a 45-minute safety ceiling. Scan M5 clocks 15:15–17:45 UTC.
- **Commodity compression release** (XAUUSD, SpotBrent): a compressed hour
  can release price discovery after buyers or sellers accept a price outside
  its range. From 16 consecutive completed M15 bars, use the first eight as
  two one-hour range baselines, the next four as the compression hour, and
  the final four as the release hour. The compression range must be smaller
  than each baseline. The release hour's final two closes must both remain
  outside the compression range on the same side, and release second-half
  tick activity must exceed the first half. Gross magnitude is the
  distance from the compressed range's opposite edge to the latest close,
  normalized by the latest close. Use existing Chandelier and ATR protection
  with a 75-minute safety ceiling. Scan half-hour clocks 15:30–17:30 UTC.
  Tick activity measures broker price updates.

All decisions use the tape's 1.5-second observation delay and future fills
use the existing latency and modeled cost machinery. Use original
minute-mark BID/ASK, conversion and the original current-at-collection
contract terms. Use one continuous EUR300 modeled ledger at broker minimum
volume in each counterfactual, with differentiated causal stresses.

Selection runs each family, long and short counterfactuals under the same
coverage and financing. A family must close at least five model trips in
at least two ISO weeks, finish all positions and intents, have reported
adverse NET with no adverse engine failure, and beat cash and both funded
directions on adverse closed NET. Benchmarks must finish with no unresolved
positions/intents and at least one closed trade each. Five and two are
minimum information guards for this experiment, not a statistical claim.

The gated evaluation starts its one 300 EUR ledger at the segment boundary
and admits only the locked families. It uses the same forecast and costs,
with funded long and short controls over the same eligible families.
Also run the ungated joint book, its funded directional controls, and each
standalone family over the later segment to measure opportunity cost and
marginal effects without reselecting. If no family qualifies, gated cash is
the modeled outcome. Report observed equity, shared margin, weekly trips,
overlaps and source coverage. Missing intraminute prices preclude continuous
drawdown claims. No orders or Cloud activation.

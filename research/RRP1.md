# RRP1 · Joint equity transmission and defensive rotation

Frozen before collection. The prior US indices portfolio showed occasional
benefit from joint allocation and a persistent shortfall in completed
weekly trades. This study uses the already deployed native funding route
for two different transmission hypotheses. No earlier predictor runs.

- US500 leadership transmission. At a fresh completed M15 clock compare
  the last hour's NAS100 and US500 returns. When NAS100 moves at least
  15 bps, US500 agrees or is flat and its absolute move is no more than
  half the NAS100 move, forecast US500 in the leader's direction.
  Driver is the absolute inter-index difference. Use the existing M15
  prediction-invalidation exit with a 90-minute exposure ceiling.
- Gold defensive rotation. When US500 moves at least 15 bps over the
  last hour and XAUUSD moves at least 10 bps in the opposite direction,
  forecast continuation in the gold direction. Driver is its absolute
  move. Use the existing ATR volatility-target exit with a 120-minute
  exposure ceiling.

Use the existing native feature uncertainty and economic selector.
Decisions at the completed M15 clock plus 1.5 seconds, 14:30–18:00 UTC
exclusive. Collect historical BID/ASK and EURUSD conversion marks on
the M5 grid, 14:00–21:00 UTC exclusive on weekdays. Six exposed weeks,
2026-09-21 to 2026-11-02 exclusive; compare first three and last three
descriptively. Start once with EUR300 and carry the ledger throughout.
Use current original account tariffs and margins as retrospective
scenarios and the existing modeled central and adverse slippage.
Only US500 and XAUUSD are candidate trades. NAS100 and EURUSD supply
context. Maintain native order-disabled shadow mode.

Report cash and matched constant-side comparators, two funded ablations,
weekly closures, incomplete marks, final residual exposure and global
sampled central/adverse drawdown. Asynchronous quotes and between-mark
paths are not certified. No approval for production follows from these
exposed observations. A positive aggregate would still require evidence
beyond directional exposure, economically viable weekly frequency and
an independent chronological validation.

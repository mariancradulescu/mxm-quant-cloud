# LDP1 · Silver repricing and local NZD inventory unwind

Registered before collection. USD-quoted silver introduces a separate
commodity exposure at a materially higher observed minimum margin. NZDUSD
is a lower-margin FX complement. No RRP1 signal is included or changed.

Silver: require a completed H1 silver move of at least 20 bps, a concurrent
EURUSD move of at least 4 bps in the same direction, and confirmation from
the latest silver M15 candle. Forecast the silver direction. Test whether
dollar repricing carries through to the metal beyond current quote costs.
Use the existing ATR Chandelier exit, with a 60-minute ceiling.

NZDUSD: require absolute AUDUSD H1 movement no more than 5 bps and a
NZDUSD-minus-AUDUSD H1 residual of at least 9 bps in magnitude. Require the
last NZDUSD M15 candle against the residual. Forecast an unwind of the
local displacement, with existing equilibrium-reversion exit and a
60-minute ceiling. Both forecasts use the existing native economic gate.

Entry decisions on fresh M15 closes plus 1.5 seconds from 07:00 to 11:00 UTC
exclusive. Collect original M5 bars and BID/ASK/EUR conversion marks on the
M5 clock from 07:00 to 13:00 UTC exclusive, weekdays. Five consecutive
exposed weeks, 2026-06-22 through 2026-07-27 exclusive. No independent
confirmation. Current original-account contract terms and margin are
retrospective scenarios. Slippage is modeled.

Use one continuous EUR300 book through the full window. Run standalone
funded ablations. For fixed-side funded references, use the same raw signal
opportunity clocks, magnitude, native cost and allocation gates and exit
policies, replacing only the forecast direction by long or short. The
reference books may differ in actual admissions, exposure duration and
turnover. Also report the original matched-entry-and-exit descriptive
benchmarks at identical clocks and volume. Cash is zero. Compare against
both kinds of benchmark, report weekly counts and sampled floating risk.
No trading or Cloud activation. No promotion without independent evidence.

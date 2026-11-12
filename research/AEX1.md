# AEX1 — contemporaneous FX breadth and commodity impulse, adaptive exits

OWNER v2.0. Registered **before** scoring. Distinct exploratory mechanisms on the
original Pepperstone FCE1 tape (run 43036474843, artifact 13863803890).
Reuse authenticated 2026-02-09 to 2026-03-20 minute BID/ASK and M5 for
AUDUSD, GBPUSD, NZDUSD, XAUUSD, SpotBrent, EURUSD. No broker requests.
All six calendar weeks are globally exposed development; no independent holdout.

## Causal shared-clock decision
Weekdays 15:30:01.500 through 16:30:01.500 UTC every 15 minutes.
At each quote clock only the 16 most recent **contiguous completed M5 bars**
of each target and EURUSD context ending at the last 5-minute boundary are
available; no future intra-M5 highs/lows or completed M15 outside causal prefix.
Do not fabricate bid/ask, missing quote clocks or mark-to-market valuations.
The same EUR300 book and existing native contract/tariff/cost/margin/FX/ledger
apply, initial model capitalization once, without reset or leverage escalation.

## Family A: synchronized USD repricing following local range break
Only AUDUSD, GBPUSD, NZDUSD (EURUSD context, never traded).
Of 16 completed M5 candles, the first 12 define a prior 60-minute
range, the most recent four a subsequent 20-minute confirmation.
Require last close outside the prior high/low and all four-bar return
in the breakout direction. Require latest 4 tick-update count to
exceed preceding 4 and EURUSD's last four-bar return to have same sign,
with both instruments' context contiguous. Trade in breakout direction.
Exploratory expected gross fractional move = min(abs(target 20-minute return),
abs(EURUSD 20-minute return)); no hindsight calibration. At fill record
ATR14 from 15 complete M5, and management uses one-way ATR(14) Chandelier
from observed completed extrema and executable quote liquidation,
plus 1.5 ATR initial invalidation and risk/cost gate. The 135-minute
safety cap is a stated mechanism-specific exposure protection, not a
universal time-profit exit. Do not treat completed bar extremes as
guaranteed historical stop fills.

## Family B: commodity impulse supported by rising update activity
Only XAUUSD and SpotBrent, no index or unobserved intermarket proxy.
Take last 16 contiguous M5 bars, last four 20-minute signed move
and previous four 20-minute signed move. Require the two signed moves
to agree, last four total tick updates to exceed previous four,
and magnitude of the last 20-minute return to exceed the mean
absolute return of the preceding two nonoverlapping 20-minute blocks.
Trade in the last move's direction. Forecast magnitude is one-half
the absolute most recent 20-minute return. At fill use 1.5 ATR14
protective invalidation, M15 closed-bar prediction reversal and a
120-minute protective exposure cap. All exits are checked at *available
one-minute original BID/ASK marks*, with 1-second execution latency
as in the existing ledger; neither intrabar ordering nor OHLC
stop-vs-target ambiguity is assumed.

## Complete common-portfolio comparison
Modes AEX1_JOINT / AEX1_FX / AEX1_COMMODITY /
AEX1_LONG / AEX1_SHORT / AEX1_FIXED / AEX1_CASH.
AEX1_FIXED has exact same proposed predictions and shared native entry
financing/cost gates but exits after 90 minutes (separately-labeled
fixed-horizon CONTROL; it is not a change to the original FCE1 study).
Direction controls maintain same prespecified eligible opportunities,
exit policies, costs and shared-model capital. Fixed control uses same
entry rule/price and minimum broker volume as its adaptive counterpart.
No optimized grid, outcome-ranked subset, direction flip or performance
tuning.

Report: EUR NET central/adverse, return on whole EUR300 capital, per-week
complete funded roundtrips, margin peak and time integral, per-trade durations
and entry-to-exit costs, sampled floating-equity adverse maximum drawdown,
unknown held marks, adaptive exit reasons, adverse vs cash and funded side
controls, and family ablations on separately-funded EUR300 counterfactuals.
If insufficient source/symbol/held quote completeness, fail closed rather
than replacing unknowns. AEX1 may result in zero admissions or negative NET;
that is a valid exact result and does not reject a symbol globally.
No independent confirmation, simulated orders only, no LIVE/DEMO/Cloud.

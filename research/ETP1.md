# ETP1 — extended-session technology relative repricing with adaptive exits

New OWNER v2.0 development-only experiment, **frozen before new broker requests
and return labels**. Two specifically screened original Pepperstone contracts:
AAPL.US-24, GOOG.US-24. EURUSD supplies quote/EUR cost conversion.
Original PDR1 observations do not have sufficient continuous exit marks and
its exact mechanisms, signals and receipts are CLOSED; do not recompute PDR1.
No global instrument blacklist or forced entry.

## Collection / identity / economical boundedness
Original Pepperstone EUR LIVE account, authenticated through protected existing
OAuth variables, strictly read-only allowlisted requests, unchanged account
fingerprint and sealed original-source custody. Use original officially paginated
M5 bars and original BID/ASK tick marks. Fixed 8-week DEVELOPMENT calendar
2026-08-31..2026-10-25, M5 warmup from 2026-08-28.
Observe weekday 15:00:01.500–18:55:01.500 UTC at 5-minute intervals for
AAPL.US-24, GOOG.US-24 and EURUSD, 30-second max quote age per side; no
OHLC synthetic fills, no forward/back fill, no extrapolated historical tariff.
Maximum expected nominal quote windows 8*5*4*12*3=5760, plus bounded bars,
contract and pages; reject before exceeding existing 7000-request ceiling.
Equity venues' actual broker sessions, enabled status, buy/sell permissions,
current min-volume/step, commission, conversion, directional margin and
financing are preconditions; skip/reject missing evidence, never assume.

## Hypothesis 1 — leader cash acceptance, AAPL.US-24
Decisions every completed M15 from 15:30 to 17:00 UTC inclusive.
Using 16 strictly contiguous M5 bars ending before decision, require target
last 20-minute price close outside the preceding 12-bar high/low in breakout
direction, target last-four-bar tick updates greater than previous four,
GOOG.US-24 last-20-minute return nonzero same sign, and AAPL absolute
20-minute return greater than GOOG. Trade AAPL in breakout direction.
Forecast magnitude = min(abs(AAPL last20 return), abs(GOOG last20 return)).
Exit at observed quote with ATR14 entry invalidation, M5 ATR Chandelier
trailing on completed M5 extremes, protective 90-minute maximum. The
maximum is a safety bound, not the primary profit exit.

## Hypothesis 2 — laggard catch-up, GOOG.US-24
Same clocks and 16 contiguous M5 bars, require AAPL previous-20-minute
return and GOOG latest-20-minute return same sign, AAPL previous20
absolute return at least twice GOOG current20, GOOG last4 tick updates
greater than prior4; target last two completed M5 returns agree with signal.
Trade GOOG in the leader's sign. Forecast magnitude =
min(abs(AAPL prior20), 2*abs(GOOG latest20))/2.
Exit at observed quote with ATR14 initial invalidation and explicit
M15 direction invalidation, 105-minute protective maximum. Thus latest
17:00 entry ends by 18:45 observed window, unless quote missing. No
unobserved intrabar stop/TP priority or invented liquidation.

## Executable shared-model experiment
One continuous original-model 300 EUR ledger, native C# same orchestrator,
contract fee/FX conversion and two-way margin checks; minimum legal
broker size, no extra deposits. Evaluate joint, AAPL-only, GOOG-only, same
opportunities always-long and always-short, fixed 90-minute control, cash.
Funding and historical marks missing -> unknown/not free. Report central
and adverse closed EUR NET, return on full EUR300, per-week complete
financed closures, mechanism ablations, long/short/cash absolute benchmark,
margin pressure, sampled adverse floating-equity drawdown, held mark
completeness, exit reasons/durations and cost components. Equity outside
observed quote window is not certified continuous.

All original 2026 dates are exposed research development. No independent
confirmation or qualification on this tape even for positive results.
No LIVE/DEMO orders, Cloud activation, new external service or OAuth
reauthorization. Preserve source hash and public receipt separately.

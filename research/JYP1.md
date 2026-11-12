# JYP1 — Pacific/JPY session relative repricing with causal adaptive exits

OWNER v2.0, distinct prospective DEVELOPMENT protocol, frozen *before*
new Pepperstone source access and before viewing any JYP1 outcome.
This is **not** a rerun, inverse, or parameter change of closed JRC1,
AEX1, ETP1, LDP1, or MCT2.

## Market rationale and ex-ante target choices

- **NZDJPY**, economic direction B: new native-financial target relative to
  prior research. Its current minimum lot and margin were observed by CMA1
  only; they do not imply historical liquidity or profitable fills.
  Hypothesis: a sustained AUDJPY yen-risk impulse transmits with lag to
  NZDJPY when NZDJPY has begun traveling in the same direction but remains
  relatively under-displaced. Trade NZDJPY in AUDJPY's one-hour direction.
- **AUDJPY**, economic direction A/new specific mechanism: yen-risk
  participation confirmed by NZDJPY when local pressure is accepted beyond
  a three-candle M15 range with rising broker tick activity. Trade
  AUDJPY in the aligned relative-risk direction. This is not the closed
  JRC1 EURJPY H1 or USDJPY volatility unwind study.
- USDJPY and EURUSD supply original causal JPY -> USD -> EUR conversion
  and USD account cost context. Never substitute midpoint conversion.

## Fixed clocks, exposure and genuine source

Original authenticated Pepperstone EUR LIVE account, read-only official
Open API. Collect original M5 OHLCV from 2026-08-28 through 2026-10-26
exclusive for AUDJPY, NZDJPY, USDJPY and EURUSD. Eight complete
development calendar weeks 2026-08-31..2026-10-25, 40 weekdays; all
historically exposed (no independent holdout).
Read original BID and ASK tick-derived *as-of* marks at five-minute
clocks 03:00:01.500–07:55:01.500 UTC, no side older than 30s;
batch historical tick pagination safely under the existing 7000
read-only-request ceiling, account identity guard, authentic symbol
contract, current min/step/swap/commission and two-sided margin.
Missing valid FX route, contract, observed quote, or financing: fail
closed. No quote interpolation from M5/OHLC and no after-clock ticks.
The schedule is bounded for economic hypothesis and API efficiency,
not a universal symbol/hour blacklist.

At 03:15:01.500 through 05:15:01.500 inclusive, every 15 minutes,
use only contiguous **completed M15** aggregated from original M5.
No bar may close after decision UTC time minus 1.5s.
Entry costs and liquidation use original executable BID/ASK marks,
with existing central/adverse cost/financing and execution-latency
model, not broker-executed fills.

## Frozen mechanism N — NZDJPY delayed yen-risk catch-up

Require eight contiguous completed M15 candles for NZDJPY and AUDJPY.
Measure each latest 60-minute signed return as last close divided by
the close four 15-minute steps earlier minus one. Both signed returns
must agree, the AUDJPY absolute move must exceed NZDJPY absolute move,
and the last NZDJPY M15 candle body must agree with AUDJPY direction.
No fixed minimum bps; the existing EUR-net uncertainty-adjusted selector
determines whether the possible remaining impulse is worth costs.
Forecast gross fractional movement = min(abs(AUDJPY latest H1) -
abs(NZDJPY latest H1), abs(AUDJPY latest H1)/2), strictly positive.
At entry, freeze ATR14 based on completed contiguous M5.
Use entry volatility invalidation (1.5 ATR), M15 signed
prediction invalidation and a 150-minute *protective* maximum,
never an automatic take-profit rule.

## Frozen mechanism A — AUDJPY aligned local price acceptance

Require eight contiguous completed M15 candles for AUDJPY and NZDJPY.
Signed latest 60-minute returns must agree and be nonzero.
AUDJPY most recent M15 close must exceed the high (long) or fall
below the low (short) of the preceding three M15 candles, and
last M15 broker tick-update volume exceed the average of those
preceding three. Treat broker tick volume only as quote updates.
Forecast fractional gross move = 0.5 * min(abs(AUDJPY latest H1),
abs(NZDJPY latest H1)). At entry seed ATR14 and use ATR Chandelier
trail on strictly completed M5 extrema with executable quote test,
entry 1.5 ATR invalidation and a 135-minute protective maximum.

## Common financial replay, not standalone wallets

Native C# EUR300 one continuous ledger and allocator; same existing
owner risk control, original two-sided costs/conversions, funding and
exact broker min volume. No reset/deposit per market or per week,
no forced fills, no trade orders. Carry simultaneous positions only
when common free capital and risk allow. Causal uncertainty-adjusted
net edge remains a necessary funding condition.
Compare JYP1_JOINT, JYP1_NZD, JYP1_AUD, JYP1_LONG, JYP1_SHORT,
JYP1_FIXED (90m *actual* frozen exit comparator, same entry signals,
separate continuous common book), JYP1_CASH. Policy-specific exposure
can change which later entries are funded; report that distinction.

Primary outcomes: central/adverse closed NET EUR, return on initial
EUR300 capital, absolute NET vs cash and funded constant-side controls,
family ablations on separate EUR300 counterfactuals, weekly completed
financed round trips, durations, hold-time marks, margin occupancy,
sampled floating-equity adverse drawdown, equity unknowns, exit reasons
and broker-fee components. No synthetic intrabar stop/TP order assumption.
No candidate qualifies from eight exposed weeks; eventual min 12m,
independent chronological confirmation, true Cloud restart protection
and system-level HARD21 are separate unresolved owner requirements.

No LIVE/DEMO order, Cloud activation, OAuth refresh, new service, repo
or overwritten original archived result. Exact JYP1 may be rejected
without blacklisting any instrument or strategy family.

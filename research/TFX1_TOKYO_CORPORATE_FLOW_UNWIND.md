# TFX1 — Tokyo 09:55 JST importer order-flow unwind in USDJPY (fixed calendar)

Authority: `docs/OWNER_SPEC.md` OWNER v2.0 and 2026-11-15 OWNER
correction. **EX-ANTE FROZEN** before source or economic
outcomes. NOT a retune of LFX1 London 16:00 fix, EURJPY
triangular quote parity, JYP1 Pacific yen-risk or any
previously closed rule; new *institution and economic
information arrival* at 09:55 JST.

## Economic mechanism and competing choices first

1. Continuing SFV1 JPN225/USD futures spread merely
   because 190.35/206.54 EUR minimum pair margins fit
   300 EUR is economically UNSUPPORTED. Contract
   expirations, rolling, point values and true net
   hedge ratios unproven. Do not launch a strategy.
2. A new oil-to-energy-equity lead-lag is too close
   to closed exact OSA1 and BWR1 without a new
   causal information boundary; not selected here.
3. **Select Tokyo local-bank FX fixing inventory
   unwinding:** importers with JPY liabilities
   often require USD settlement on Japanese
   monthly `gotobi` corporate payment dates.
   Bank customer FX flow concentrates before
   local 09:55 fixing and dealer inventory may
   be liquidated after the benchmark. Ito/Yamada
   original peer-reviewed evidence:
   https://doi.org/10.1016/j.jinteco.2017.09.005
   and NBER https://www.nber.org/papers/w21518.
   Different fixing institution, time, user-base
   and currencies from closed LFX1 London 16:00.
   Neither paper observes 2025–2026 Pepperstone
   customer order flow: date/clock is a
   *predetermined economic-flow proxy*, NOT proof
   of order imbalance or positive CFD NET.
4. Competing explanations: efficient market
   preprices the unwind, other Asia-wide risk
   news dominates, holidays suppress local
   corporate payments, broker quote spreads
   widen, the time effect exists equally on
   non-gotobi days, or dealer flow persists
   rather than reverses. The expected short
   USDJPY move may have already occurred
   before a causal 10:00 executable entry.
   Future negative results are retained, not
   inverted or adjusted to the best weekday.

## Fixed cohort, dates, availability and signal

52 exact Monday–Friday calendar weeks:
2025-11-03..2026-10-30, 260 scheduled dates;
America/Tokyo is fixed UTC+9. All previously
globally EXPOSED development data, no independent
confirmation. At each scheduled weekday, set
`gotobi=True` iff JST calendar day in
`{5,10,15,20,25,30}`. **No moved weekend/
holiday dates, no last-business-day substitution,
no outcome-driven calendar edits.** This tests
only literal gotobi weekdays, not all possible
Japanese corporate settlement days.
The other weekdays are an exposure-neutral
same-clock **non-gotobi placebo**, not
a replacement strategy chosen by outcomes.

At **09:55 JST / 00:55 UTC**, declare an immutable
`FIXING_UNWIND_INTENT` for *every* gotobi weekday,
with `side=-1` USDJPY (sell USD / buy JPY).
Decision depends ONLY on known calendar, not
current or future source availability, quotes,
9:55 post-fixing price, future liquidity or
returns. On other weekdays `ABSTAIN_CALENDAR`
for primary, irrespective of future prices.
One attempted trade per eligible gotobi date,
no overnight carry assumed; no repetition
to manufacture HARD21.

Economic timing: **10:00 JST** executable
as-of USDJPY BID entry, monitor at a fully
completed **10:10 JST** M5, **10:15 JST**
early exit if *completed* 10:10 close
lies ABOVE the maximum of six contiguous
predecision USDJPY M5 highs ending at
09:55 JST; else fixed **10:35 JST** exit.
The threshold is the mechanically known
pre-fix range, not an optimized numeric
bps threshold. Safety monitor is not an
assumption of a broker stop fill. If monitoring
bars missing, the intent remains; outcome
`EXIT_MONITOR_UNKNOWN`. A comparator
always exits 10:35 regardless of monitor.
All times fixed ahead of outcomes.
Any open quote needed for entry/exit missing
means `FINANCIAL_UNKNOWN`, never abstention,
zero loss or substituted OHLC fill.

## Source evidence, contracts and causal separation

Original Pepperstone EUR account only, original
unmodified fingerprint; existing read-only
Open API OAuth transport, custody, no orders.
All 260 scheduled dates: genuine ORIGINAL
USDJPY consecutive 5-minute bars at
09:25..10:15 JST and independent BID/ASK
ticks for USDJPY and EURUSD with 60s
lookback ending at each 10:00,10:15,10:35
JST clock. Each side sampled last <=20s
as-of, bid <= ask, no `hasMore`; quotes
missing/late = UNKNOWN. Collect same
quotations on non-gotobi days for placebo
without cherry-picking event days.
Current account min/step volume, signed
margin, commission type/floor, JPY USD EUR
FX route, P&L conversion fee and explicit
swap schedule. Only original current
contract terms, never historic tariff
continuity or actual fills; 0.5bps central,
2bps adverse extra modeled roundtrip
slippage, not broker commission.
Fixed post-auth ceiling 3700 requests
(260*12 two-sided side queries + 260 USDJPY
bar requests + roster/contract/margins).
No selected days are removed after
observing source outcome completeness.

**Strict separation**:
- `intent`: immutable calendar-only at 09:55;
- `decisionFeature`: six complete M5 bars
  strictly with closed timestamp <=09:55;
- `monitoringFeature`: all three complete
  M5 bars 09:55–10:10, available only at 10:10;
- `financial`: actual quote source at
  10:00,10:15,10:35, used ONLY for
  post-intent evaluation. Future source
  completeness NEVER removes signal.
Seal original raw protobuf and decoded
  partitioned source BEFORE scoring
  post-entry returns.

## Costed comparisons and economic admission

Conditional one-minimum-volume USDJPY short
in actual original JPY quote units, signed
JPY->USD via original USDJPY BID/ASK, then
USD->EUR via original EURUSD BID/ASK at
each exit; current USD-based commission
paid in EUR at BID, native min-volume
and step and max margin buy/sell. Do
not reinterpret USD/JPY quoted P&L as
USD P&L or use a synthetic midpoint.

On *exact same matched gotobi entries* compare
PRIMARY adaptive invalidation vs same-side
fixed 10:35, always long, own prior
30m-return reversal (negative of
09:25..09:55 return), and CASH (0 EUR).
Placebo: fixed 10:35 SHORT on all
non-gotobi same-clock days, separately
reported only as between-day
counterfactual/seasonality check;
do NOT compare active-only gotobi sum
to unconditional many-day placebo sum.
Report event counts and missing reason
on all 260, 26-week halves, same-clock
per-observation EUR NET central/adverse,
matched benchmark increments, contract
as-of and quote coverage. No regular
gotobi signal is allowed to depend
on future quote existence. All matched
policy comparisons use the same initial
€300 notional constraints, but individual
conditional EUR sums are NOT a funded
native common portfolio or multiple wallets.

If primary adverse NET <=0 either half
or fails both CASH and relevant same-event
FIXED + own reversal comparators,
close its exact rule. Positive historical
does not certify C# funding, true intrabar
DD30, system HARD21, 12mo independently
confirmed returns, or LIVE/DEMO orders.
No retuning, no day-of-month selection
based on outcome, no reverse-side
promotion, no future source backfill,
and no Cloud activation. The final
cBot can compute JST clock & day,
native closed M5 bars and independent
MarketData quotes without HTTP/news.

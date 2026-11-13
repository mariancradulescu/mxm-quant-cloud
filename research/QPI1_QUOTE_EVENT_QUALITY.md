# QPI1 — Genuine broker quote-event pressure, signal quality and causal exits

OWNER v2.0 and 2026-11-13 signal-quality amendment. FROZEN BEFORE research
implementation and BEFORE ANY NEW Pepperstone collection or outcome scoring.

## Economic alternative selection

Rejected design alternatives before seeing outcomes:
1. Another OHLC return/wick threshold or higher-momentum filter adds no
   demonstrated information channel and risks revisiting exact closed studies.
2. Historical Level-II order-book imbalance is inadmissible without genuine
   archived depth events: the official cTrader API documents *live* depth
   subscription, not historical order-book snapshots.
3. Choose **individually timestamped separate BID and ASK revisions**, which
   cTrader Open API supports historically. Neither quote updates nor bid/ask
   price changes are executed orders, transaction volume, signed trade flow,
   or evidence of broker fill liquidity. Unlike SQIC1's *two one-minute
   synchronized displacement tests*, QPI1 uses the distribution of the
   *number and direction of actual revisions* within ten minutes,
   observed at all nonzero scores rather than after arbitrary pressure
   filters. Distinct from VIA1's midpoint impulse and structural rebound.

Use two predeclared FX crosses on the *original Pepperstone EUR account*:
**USDCHF** (historically familiar FX universe, new quote-event mechanism)
and **EURGBP** (new exploratory target, subject to verified broker roster).
No substitution of another symbol if missing. Do not claim EURGBP was never
viewed by any earlier programme; its original tick-event research is new.
No initial empirical direction, score sign, cost or performance assumption.

## Genuine source, exact clocks and custody

8 exposed chronological weeks from 2026-09-14 through 2026-11-09
exclusive. Monday–Friday at UTC **09:00 and 14:00**, 40 weekdays, 80
decision clocks per target, 160 combined; two time windows are economics
context (Europe and transatlantic overlap), not filters chosen from results.
Retain original underlying authenticated broker identity, zero OAuth
reauthorization, only already authorized ProtoOA read-only messages.
For each decision t request separate original BID/ASK *tick events* in
[t-10m-20s,t] and [t,t+31m], which are both <= one week; treat hasMore as
truncation and reject rather than silently discarding pages. A tick's
timestamp is a quote timestamp; reconstruct exact times via existing
`decode_side` and require ordered, valid positive price ticks.
All raw request/response protobuf bytes and derived tick data remain in
**one sealed original-source artifact**, encrypted before evaluation.
Public report contains counts, aggregate returns and SHA-256 only, never
raw prices, account, symbol IDs or credentials. Target and underlying
contract current metadata are source facts, not certified historical
eligibility. No new service, token refresh, order, Cloud or DEMO.

## Signal and signal quality — exactly one policy per target

At t, require fresh paired BID and ASK within 20s, plus a paired
observation at t-10m within 20s for own-momentum control. Reject crossing
BID>ASK and nonpositive values. Count from **individual ticks** in the
last ten minutes each strictly upward or downward *price revision*
versus the prior tick of the same side. Initial tick establishes
reference and is not counted as a directional event. Unchanged-price
ticks do not count. Define

  U = up_bid + up_ask, D = down_bid + down_ask,
  signed_pressure = (U-D)/(U+D), strength = abs(signed_pressure).

No revision -> no signal; exact balance -> no directional signal. All
other observed signed scores become predictions sign(U-D), with **NO
additional threshold**; score magnitude is a forecast-quality ranking,
not a cumulative admission filter. Record separately true zero-update,
balanced, positive and negative score clocks; no bar-return or spread
threshold rescues a negative outcome.

Enter at the first valid **t+60s** as-of paired mark, within 20s
per side; missing quote is UNKNOWN, not zero return. This is a sampled
quote-price policy, NOT an order/fill model.
At t+10m and t+20m use only the subsequent tick revisions since
the previous sample (strict event window) to check whether the **new
10-minute directional pressure** changes sign *against* the original
prediction. If so, exit at that first available fresh paired mark.
Otherwise exit protectively at t+30m. First complete valid exit is
required. If an intervening scheduled monitor is missing, close status
as UNKNOWN; cannot infer that price stayed within a stop intrabar.
Paired 30-minute comparators also require the exact t+30m mark.
This is a *policy-specific maximum*, not a universal fixed hold or
a retrospectively optimized exit.

Score independently against matched **own last-ten-minute midpoint
momentum**, matched long, matched short and cash, all at the same
entry and candidate 30-minute clock, plus QPI1's own 30-minute
directional fixed hold. Distinguish its own causal adaptive-exit
payoff from the full paired comparison. For every priced pair report
gross midpoint bps and executable-side quote-crossing bps before fees
and slippage. No historical tariff imputation, no NET EUR, no funded
claim, no margin or short eligibility inference from historical quotes.
Separate decision completeness, no signal, missing entry,
missing monitor, exit-available, paired-full-path.

## Does *strength* contain predictive quality?

Predeclared read-only diagnostic of prediction *quality*, not a learned
economic admission threshold. First four calendar weeks seed the
strength distribution. Beginning week 5, classify each new score as
above-or-below the median magnitude of **earlier matured scores only**,
updated after each completed prior week; do not use the current week's
future outcomes or label-driven threshold selection. Disclose
directional hit rate, signed 30m midpoint gross, price-crossing
friction and paired advantage vs own momentum for both cohorts
**including zero/negative effects**. This tests whether higher score
strength distinguishes directional informativeness, not just activity.
Do not choose the winner, target, interval, sign or cohort after scoring.

Falsification: no positive paired midpoint advantage over own momentum,
or sign strength fails to discriminate in a stable manner, rejects this
exact rule as a candidate for complete financial validation.
A positive *gross* result authorizes cost work only after sufficient
coverage and chronologically consistent paired evidence; no independent
confirmation exists on exposed 2026 weeks. No universal HARD21
candidate-level gate. The final target still requires 12+ months
relevant genuine evaluation, untouched subsequent confirmation, EUR300
shared C# funded ledger, exact costs and floating DD <=30%, HARD21
portfolio-wide and no LIVE/DEMO order or trading Cloud activation.

# SQIC1 — Pooled spread-stable quote-impulse continuation (original Pepperstone)

Authority: `docs/OWNER_SPEC.md` OWNER v2.0 including 2026-11-11
technical-diagnostic clarification. **Prospective, outcome-blind
registration** before access to any new SQIC1 price/return label.
Every exact closed MEF1, CMR1, QSR1, RRP1, ESP1, IMT1 and trend study stays
closed. This is not a parameter revision of any of them.

## Distinct economic premise

When both dealer BID and ASK independently reprice in the same direction
over two consecutive short intervals *without spread expansion*, the
joint quote change may reflect persistent price discovery rather than
one-sided dealer spread management. Test whether this condition predicts
**subsequent 20-minute executable-side price continuation after a
30-second delay**, net of observed spread, current minimum-size
contractual commissions and conservative modeled slippage.

This is a quote-event microstructure hypothesis, not exchange order flow,
a filled order, verified transaction volume, true DOM imbalance, VWAP,
a scheduled-event or OHLCV trend rule. It may fail completely.

## Source and population, frozen

Research three **complementary low-cost routes** identified without
directional return labels in MEF1: AUDUSD (FX), US2000 (US small-caps),
SpotCrude (energy). EURUSD is conversion context only. Their sampled
cost/margin feasibility does not prove realized alpha or shared funding.

26 weeks, Monday 2026-05-04 to Friday 2026-10-30, two chronological
13-week halves, all previously exposed global research history.
New York local 10:00, 10:30 and 11:00 on weekdays (the first 90
minutes of regular US cash-session repricing). At most 45 raw
opportunity slots per week across all three markets; no forced trades.
All are candidate clocks even when no valid quote or signal; report
missing observations separately, no outcome-driven date selection.

At each decision clock t use paired original BID/ASK no more than
20s old sampled at t-120s, t-60s, t. Use immutable as-of logic; retain
positive BID=ASK; reject missing, truncated or crossed tick arrays.
Require both BID and ASK move strictly in the **same** signed direction
on *each* of the two 60s legs, with agreement between legs. Require
2-minute midpoint displacement >= twice the larger spread observed
at t-120s/t-60s (both measured in raw price ticks); require spread at t
<= larger of these two prior spreads. Predict continuation in the
joint direction. This is a single fixed exact rule, not a grid.

Entry t+30s, exit t+20m30s, historical executable-side BID/ASK pairs
no more than 20s old. No re-selection from entry/exit quotes. Use
original enabled contracts, minimum broker volume, cost conversion,
USD/EUR historical rates at entry/exit, both current minimum margins,
short-sale permission, verified trading schedule and contract swap
timing; any missing item is **unknown**, never zero. Current tariffs,
volumes and margins are retrospectively applied scenarios, not certified
historical trade terms. No signal may cross a swap-charge clock.

## Economic comparisons and stopping

On exact same priced *signal* clocks, compare model, long, short and cash
with the same minimum volume, entry/exit as-of, currency conversion and
contractual cost. Charge modeled additional round-trip slippage of
0.5bps central and 2.0bps adverse to EVERY non-cash comparator;
report adverse and central bps relative to entry notional. No real
fills, position ledger or EUR NET certification at this screening stage.
Disclose every instrument and both halves, whether positive or negative.

Within each half, require >=30 completely priced signal opportunities
across >=8 active calendar weeks, >=75% priced/signal completeness,
and the **pooled** weekly-equal-weight adverse modeled bps must exceed
zero AND long and short on their own same clocks. No per-instrument
HARD21 test or winner-only substitution. If either half with
sufficient coverage fails, close the exact SQIC1 rule; otherwise
`INSUFFICIENT_COMPARABLE_EVIDENCE` if the gate cannot be assessed.

A passing screen authorizes a **separately registered native C#**
single EUR300 financed historical exploration using synchronized
cross-instrument quote+exit snapshots, benchmark books financed under
identical grid and lifecycle, global equity/margin/slippage,
counterfactual ablations, frequency, and risk. It does NOT qualify
the cBot, prove incremental NET after global funding, replace
independent 12-month validation or grant order/Cloud permission.
All data through Oct 2026 are exposed; only new unexposed chronology
could independently confirm the mechanism.

Original Open API authenticated Pepperstone requests are strictly
read-only, original account commitment and <=10,000 post-auth
requests. Quote lookup cannot use any future timestamp relative
to its predefined observation clock and cannot substitute mids for
missing BID/ASK. No orders, account changes, Cloud activation,
retuning or closed study replay.

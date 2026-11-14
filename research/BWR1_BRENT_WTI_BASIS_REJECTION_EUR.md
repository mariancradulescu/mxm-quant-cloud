# BWR1 — Brent/WTI transatlantic grade basis failed-dislocation and funded-cost preflight

Owner v2.0 and amendments, 2026-11-14. Freeze FIRST, independently
of any BWR1 historical returns/quotes, financial scores or result-informed
changes. This mechanism is DIFFERENT from closed Brent-to-Crude
unidirectional lag `ENERGY_BRENT_TO_CRUDE_LAG` W30–31
and from standalone AUDUSD/NatGas range reversion W38–39:
BWR1 is the **simultaneous paired long-short Brent-versus-WTI
crude grade dollar-per-barrel basis**, formed from two liquid
commodity instruments, its US physical futures session
dislocation and failure. No old rule/period reexecution.

## Compare hypotheses and costs BEFORE source inspection

1. Repeating old Brent-leads-WTI long-only signal with changed
   momentum or exit: prohibited retrospective retuning. Reject.
2. Price-only bar expansion at any time without a physical
   reference market: weak economic premise, close to old
   generic shocks. Reject.
3. **Select transatlantic Brent–WTI grade basis liquidity sweep
   and rejection at the US energy-market open.** Physical grades
   are linked by refinery substitution, shipping and inventories,
   although the freight/quality difference is not constant.
   A transitory morning widening beyond the prior one-hour
   traded basis, immediately rejected back within that range,
   may reflect liquidity inventory rather than a durable physical
   supply valuation. Simultaneously short the rich relative grade
   and long the cheap grade, equally at each CURRENT broker
   minimum unit (not idealized dollar-neutral sizing).
   The competing explanation is news that permanently shifts
   the actual physical basis, noncomparable spot CFD financing
   schemes, two spreads/fees and adverse USD->EUR conversion.
   Therefore test only the **paired NET EUR**, not 4bps of
   hypothetical spread return, under one EUR300 capital book.
   A changing Brent/WTI futures maturity or CFD reference
   can break physical parity; no assumption that continuous
   CFD prices are identical-delivery futures.

Known current original-account evidence BEFORE this new test:
`docs/OWNER_EXECUTED_MULTI_ASSET_COST_CAPITAL_SCREEN_20261108.json`
reports one-min-volume margin SpotCrude EUR7.81,
SpotBrent EUR8.67, observed spread around 3.62/3.55bps
from limited XUA1 quotes. Another CSP1 snapshot shows
around 2.5/3.1bps respectively; ranges are snapshots,
not historical distributions. Even two 1-unit legs
and all minimum costs must be explicitly broker checked.
BWR1 requires individual quote and current contract
readback before monetary scoring. Gross ≠ NET.

## FULL frozen one-year causal strategy

52 Monday–Friday weeks 2025-11-03..2026-10-30,
260 fixed NY trading weekdays, including holidays
counted UNKNOWN if broker source unavailable.
Markets exactly `SpotBrent`, `SpotCrude` with
`EURUSD` conversion only, original Pepperstone
LIVE EUR account, read-only SCOPE_VIEW.
At 10:00 America/New_York, require both original
consecutive COMPLETE M5 bar close sequences:
basis B(t) = Brent close(t) minus WTI
SpotCrude close(t), USD/barrel proxy.
Prior closed 1-hour **reference** basis 08:30,
08:35,...,09:30 inclusive. Define H max and L min.
Use two complete closed marks at 09:45 and 10:00.
A **rejected basis sweep** occurs if:
- 09:45 basis is strictly ABOVE H, and the 10:00
  completed basis closes back in [L,H],
  then direction SHORT Brent / LONG Crude;
- OR 09:45 basis strictly BELOW L, and the 10:00
  completed basis closes back in [L,H],
  then direction LONG Brent / SHORT Crude.
No percentage/magnitude filter. If previous H==L
the rule is still exact and uses strict sweep.
No signal at any other clocks, no arbitrary
minimum gross bps gate to reduce activity.
Both prices at 10:00 are already closed and known;
the two legs are the one pair signal, not 2
independent signals.

At nominal 10:05 NY trade both legs at
original ≤20-second as-of ASK for buy/BID for
sell, minimum original broker unit volume for
each instrument, in a single risk-aware
portfolio book. No fake atomic guarantee of
pair fills. At the 10:35 COMPLETED M5 mark
(monitoring only), if basis re-breaks the SAME
original upper/lower H/L extreme against the
reversion prediction, both legs exit at
the 10:40 sampled BID/ASK; otherwise both
exit 11:35. No backfit stop, no intrabar
fillable stop claim.
Prespecified same-entry comparators on EVERY
matchable event at 10:05 to 11:35:
(A) same exact pair side but fixed 11:35 exit,
(B) always long Brent/short Crude,
(C) always short Brent/long Crude,
(D) cash. Same current minimum units,
original observed entry and exit quote
sides, fees/FX, central/adverse assumptions.
Compare on EXACT common priced entry/exit
subset, split 26/26 weeks, include all missed
source/quote/FX/cost/sessions as UNKNOWN;
never select winners, one grade only, or
one chronology half.

## Original read-only source capture / custody

For all 260 predeclared weekdays, request genuine
historical M5 trendbars for Brent AND Crude
from 08:25 to 11:40 NY (up to 520 bar requests);
read outcome feature event at **only 10:00 or
earlier** before collecting event-specific ticks.
For every historical causal intent (regardless
its future return) request original BID and ASK
independently for SpotBrent, SpotCrude, EURUSD
at all three 10:05,10:40,11:35 local clocks:
18 original tick requests per event. request
60sec lookback, accept only LAST AS-OF
positive BID≤ASK with each side age≤20sec;
hasMore and no-quote means UNKNOWN; never
backfill, substitute OHLC, or loosen quote age.
One small original account roster, contract
fields, fee/min and expected margin query
per symbol. Hard ceiling 6200 post-auth read-only
requests; stop rather than narrow historical
calendar when source capacity is exhausted.
No OAuth refresh, external services, news
download, Cloud execution or LIVE/DEMO orders.
Raw original protobuf and decoded source
are sealed RSA/AES-GCM under installed
custody recipient **BEFORE any post-entry
economic outcome/exit/pricing scoring**.
Only aggregate public result and SHA-256
of private original published.

## Evaluation after original protection

For BOTH paired legs apply minVolume/step, true
current contract type, preciseTradingCommission,
preciseMinCommission and charge schedules;
current broker 2026 tariff is CONDITIONAL
historic estimate, not certified 2025/2026
as-of tariff. Price real executable BID/ASK
and signed EURUSD BID/ASK. Use existing
`research.rne1_eur_protected_exact_reconciliation.current_eur`
only where contract and quoted unit format
match; 0.5bps central and 2.0bps adverse
additional roundtrip modeled slippage per leg,
both legs, and actual PnL currency conversion.
No financing silently set to zero;
no_swap verifies no swap-charge crossing.
Current min buy/sell margins of both legs
must sum < 300 EUR (without assuming
netting), and reserve/available cash after
open loss evaluated conditionally. Capital
is one EUR300 book without deposits/reset.
Report quantity-correct original min unit
pair PnL gross EUR, crossed EUR,
commission EUR, FX conversion EUR,
slippage EUR and conditional NET EUR
separately for 26w halves and comparators.
Do not call a basket financed if broker
historical leverage, pair atomicity or
available float are unknown; no sourced
5-min liquidation marks except those
explicitly provided, so do not claim
continuous or worst-case DD30.
If a robust after-cost candidate survives
both chronological halves and matches
benchmarks, advance to existing native
C# common EUR300 ledger and original
dense quote-path collection. If negative
do NOT automatically port/research exact
BWR1 further. HARD21 is system-wide,
never by forcing grades to trade.
No independent confirmation: 52w calendar
already globally exposed. Do not add
post-results filters or switch entry/exit.

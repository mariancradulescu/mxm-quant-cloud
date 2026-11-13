# ECA1 — cash-open index-ETF lag and ETF creation/redemption absorption

OWNER v2.0, 2026-11-13. **This exact economic protocol is FROZEN
in its own commit BEFORE collection of any ECA1 historical price
or return**. Distinct from RNE1, VIA1, QPI1, US2000 morning gap,
OSA1 oil-producer opening, and closed generic breakout families.
No old result is rescored or retuned.

## Competing economic mechanisms considered before code

- Another BID/ASK revision-pressure score has no distinct source of
  edge after QPI1. Rejected.
- Another crude/gas weekly announcement rule is economic but requires
  calendar exception continuity unavailable through cTrader Cloud HTTP.
  Leave exact RNE1 unchanged and do not add a lookalike.
- **Select tradable ETF cash-opening price discovery**. US500 and
  NAS100 index CFDs already trade before 09:30 NY, while index-tracking
  ETFs SPY.US and QQQ.US begin cash trading around 09:30. The index
  and fund represent closely related equity baskets but cash ETF
  creation/redemption, opening auction imbalance and dealer hedge
  inventory can sometimes leave the ETF's *first completed 5-minute
  price change* opposed to the index CFD's first completed five
  minutes. Subsequent arbitrage/inventory normalization may transmit
  the index move into the ETF over the following ~55 minutes.
  All inputs use *broker-internal historical M5* and at live time
  cTrader Algo `MarketData.GetBars(TimeFrame.Minute5,symbol)`.
  No internet, news or analyst forecast; the NY clock is a
  deterministic zone mapping. Opposing mechanism: ETF's contrary
  move may contain genuinely superior price information, a basket
  tracking/CFD basis can legitimately diverge, 09:30 microstructure
  might favor the ETF, and real spread, fee and slip may dominate.
  The futures CFD may not accurately stand for underlying NAV.
  This hypothesis is about a **discrete economic opening
  discrepancy**, not an arbitrary indicator intensity or permanent
  every-bar trade.

The two PAIRS are frozen BEFORE collection, irrespective of results:
`US500 -> SPY.US` and `NAS100 -> QQQ.US`. No substitutions;
both exact names are enabled in the PHX1 current original-account
public artifact #14071594612 (run 43497156352), with
current min buy margin 34.28/13.68 EUR for US500/SPY.US and
126.73/12.34 EUR for NAS100/QQQ.US respectively.
This is CURRENT eligibility, not historical settlement.

## Historic exposed data panel, causal decisions, benchmark rules

Exactly 26 full weeks Monday 2026-05-04 through Friday
2026-10-30, Monday through Friday, two fixed pairs. 130
prespecified market weekdays per pair. This calendar has substantial
GLOBAL prior exposure to other MXM studies, so ECA1's 2026 results
are **exploratory development**, never independent confirmation,
even if each ETF symbol was previously unscored.

At local New York cash open:
- Acquire two independent original Pepperstone M5 bar streams,
  index and ETF, for each prespecified weekday from 09:25
  to 10:40. All bars must be COMPLETE and consecutive.
- At 09:35, having just closed the 09:30–09:35 bar, calculate
  signed log return from the 09:30 bar opening reference
  (09:30 M5 bar first close? The *open* price of the 09:30
  bar is available at 09:35) to the 09:35 close. Use
  genuine bar Open and Close of the same 09:30 M5 bar,
  not a prior-day close or adjusted ETF NAV.
- **Economic discrepancy event** iff both within-bar index
  and ETF returns are strictly nonzero and their signs are
  opposite; otherwise `NO_CROSS_MARKET_DISCREPANCY`.
  No tunable magnitude, spread or volatility threshold.
  Predictor is original index first-bar sign; execution
  target is the ETF, never a synthetic index hedge.
  One event per pair per day maximum, no signal
  without completed causal bar.
- At 09:40 first executable sampled ETF original ASK/BID
  clock, enter in the index direction (not in ETF
  first-bar direction).
- At **10:00 NY** calculate signed cumulative *completed*
  index CFD close-to-close movement from 09:35 to
  10:00. If this is strictly opposite the original
  index first-bar sign, mark index repricing as
  invalidated and use 10:05 sampled exit.
  Otherwise hold to fixed 10:30 sampled exit.
  This is NOT an intrabar stop, and the decision
  requires the complete historical M5 path.
- For both ETF and original-account EURUSD, collect
  original BID/ASK as-of 09:40, 10:05, 10:30 NY,
  separately with each side fresh <=20 seconds,
  bid positive <=ask. If one or both absent
  mark UNKNOWN, never infer a price from OHLC.
- Same-entry controls: own ETF first-bar momentum
  held to 10:30, index-side fixed to 10:30,
  always-long, always-short and cash. All comparisons
  on EXACT shared eligible original priced entries.
  Importantly, 10:30 end price is needed to pair
  against fixed even when ECA1 closed at 10:05.
- No extra participation filter just to reduce signals.
  Cause detection / cost pricing / funded risk are separate.

## Original source, financial comparability and validity

All historical original-account auth SCOPE_VIEW, no new OAuth,
no broker orders or Cloud trading; check original Pepperstone EUR
deposit asset and original contract/roster for every fixed
symbol, min, step, quote USD and commission/rollover details.
Source must be FULLY protected: raw original broker protobuf
requests/responses (M5, ETF ticks, EURUSD tick and contracts) and
decoded bars/ticks sealed in existing RSA/AES-GCM custody
**BEFORE evaluation of ANY post-entry outcomes or performance**.
It is permissible to check 09:35 *causal events* in memory to
decide which days need tick source; this must not access future
price, future quote or outcomes. SOURCE OUTPUT audit must expose
every one of 260 scheduled pair-days and complete/missing
bar decision, absent/no-event/active, priced/unpriced and FX
state, no private identifiers and no raw quotes.

Read-only request ceiling 3200; if exceeded stop original run,
report technical interruption, never lower the window or
select a convenient profitable subset. Use only 09:25–10:40
historical M5 bars on prespecified weekdays; as-of ticks
query t-60sec to t, hasMore unresolved, no older than 20sec.
Broker original 09:30 bar timestamps must match fixed causal
decision; closed bars only, no rounding future ticks into a
earlier decision. No historical MarketDepth claim.
Quotes accepted only from authentic response tick deltas.

Economic outcomes:
1. BAR-source coverage and event counts across BOTH targets,
   first and second chronological 13-week halves.
2. Gross midpoint and original executable-side quote crossing
   in bps, before other cost, on matched clocks.
3. Contract minimum units (wire /100), fee/minimum by explicit
   original current proto contract; signed as-of EURUSD BID/ASK
   conversion credit/debit, FX conversion fee if declared,
   central 0.5bps and adverse 2.0bps additional roundtrip
   modeled slippage. Missing fee asset, conversion, rollover
   or session proof => `UNPRICED`, not zero.
   Current November 2026 tariffs and current margin are
   ex-post conditional assumptions, NOT certified historical.
4. Compare against matched index-side fixed, own-ETF momentum,
   long, short, cash *NET advers* at same current contract
   min volume. Do not choose the more favorable of ETF pairs,
   time split or benchmark retrospectively.
5. If economically positive and source completeness sufficient
   to warrant finance, separately integrate original matched
   quote paths into EXISTING C# funded ledger and joint
   EUR300 portfolio. No per-symbol HARD21 required; no
   inferred 30% floating DD from sparse quotes. No claims
   of actual fills, broker EUR net or 12m independent validation.

Research does not depend on an EIA calendar and has an
implementable cBot market/time signal path using a SINGLE
C# Cloud/Android cBot with no HTTP calls; **actual 24/7
Cloud runtime, historical permissions and quote equivalence
still need native verification before deployment**.

## Stop rules

If both frozen pairs unavailable, source not genuine,
or historical ETF 09:30 first bars missing, report a
technical no-source verdict. If first-bar discrepancy
carries no advantage over the better matched simple
benchmark after adverse costs, close ECA1 exactly; no
retuning signs, times, exit, magnitude, instrument or
period to rescue losses. Positive gross or conditional
EUR NET alone is not portfolio admission. Always retain
the two independent economic workstreams: new mechanisms
on old symbols and new original Pepperstone instruments.

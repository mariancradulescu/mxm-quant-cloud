# RNE1 — EIA gas-storage-release absorption and gas-producer transmission

OWNER authority: docs/OWNER_SPEC.md v2.0 and 2026-11-13 corrections.
**Frozen on a unique Git commit before any RNE1 source collection or outcome
scoring.** Globally exposed 2026 history is development, never independent
confirmation. No closed OSA1, ESP1, MSE1, VIA1, QPI1, FCE1, RRP1 or other
configuration is rerun, retuned, inverted or promoted.

## Economic rationale and alternatives, before implementation

1. QPI1's bid/ask revision imbalance is an almost-always-on quote
   descriptor, not an independent economic information arrival. Reject
   new tick-window, sign and threshold variants.
2. A generic OHLC impulse/price-acceleration variant on existing targets
   has no distinct new causal mechanism. Reject.
3. **Choose dated public U.S. EIA weekly natural-gas storage announcements**
   as an externally scheduled information-arrival event, and ask whether
   the initial NatGas CFD repricing is only partially transmitted over
   the next 75 minutes to (A) the established NatGas CFD itself and
   (B) one new U.S. natural-gas producer stock CFD, EQT.US, if Pepperstone
   currently lists this exact symbol. No target substitution.
   This is *not* an EIA inventory surprise trading model: no
   contemporaneous consensus, as-published historical inventory values
   or announcement contents are proven to be available at the minute
   for the tested events. Do not describe them as observed input.
   EIA source: https://ir.eia.gov/ngs/schedule.html and
   https://www.eia.gov/naturalgas/storage/.
   Standard WNGSR Thursday 10:30 America/New_York; the EIA schedule's
   listed 2026 holiday exception is 2026-11-13, **outside this test**.
   Distinct from OSA1's pre-equity-open oil → XOM/CVX handoff:
   simultaneous price discovery during *weekly public gas information
   arrival* with gas-producer equity already trading and a same-clock
   nonrelease control, not overnight oil information before cash open.

Mechanism: news is publicly released at 10:30 ET, gas reprices
immediately, inventory/hedging/equity flows may continue absorbing it;
the gas producer's exposure to input prices can cause delayed
transmission. Competitors: report anticipated by market; new data fully
absorbed before entry; NatGas CFD not the relevant regional physical
price or EQT equity beta confounded by market index and other news;
minimum spread/fees dominate; one gas producer may not be tradeable.
Do not impute anything in these cases.

## Source, event panel, price clocks, and data gating

Exactly 26 full Monday weeks 2026-05-04..2026-11-01 inclusive. One
prespecified EIA **Thursday** at 10:30 local NY per week, plus **Tuesday
10:30 NY placebo** of the same week. In total 26 release events and 26
calendar-time controls. The official EIA release-calendar assumption is
fixed before price retrieval; verify official exceptions. If a release
was delayed/unscheduled and exact as-of release timing cannot be
certified, label it UNKNOWN and do not treat Thursday as a confirmed
publication. Calendar source is current official policy, not an
archived per-release timestamp receipt.

Markets: NatGas mandatory, EQT.US optional as an additional new
Pepperstone target if exact original-account broker symbol exists.
Never switch to another equity after observing historical returns.
Confirm original Pepperstone EUR account, current symbol presence,
min and step volume, quote asset, current margin buy/sell and contract
terms (these are current facts, not historically certified). No
historical margin certification means NO financially admitted trades.
EQT absent is NOT a negative equity result.

At each NY Tuesday and Thursday acquire genuine **completed M5 bars**
for NatGas and available EQT.US, 09:25 through 12:10 NY; no current
or future candle at any decision, no OHLC quote-precision claim.
Timestamp convention: close at bar open + 5m; require all needed
consecutive completed M5 bars. For each target acquire paired original
Pepperstone BID/ASK quotes within 20 seconds as-of 10:50, 11:20, 12:05
NY (3 paired clocks) with independently verified actual timestamps.
Original BID=ASK is legitimate; crossed or missing side is UNKNOWN.
No extrapolation across market closure; any hasMore tick response
is unresolved, not dropped. No made-up quote, market-depth,
execution or historical fill evidence.

At **10:45 NY** (after the completed 10:30–10:45 bars), define the
NatGas release reaction as the completed 10:30 to 10:45 price log
return in bps. Define ambient 15-minute magnitudes using four
independent previous completed windows [09:30,09:45],
[09:45,10:00],[10:00,10:15],[10:15,10:30].
A **real repricing event** is declared iff absolute observed
10:30–10:45 move exceeds *the largest of those four preceding
15-minute changes*. This is a causal prior-regime surprise definition,
not an optimized bps or score threshold. Zero/generic moves are
**NO_EVENT_ANOMALY**, not forced market participation.
Same exact criterion on Tuesday is a falsification/placebo.
The event direction is sign of the completed release reaction,
never the future target return.

Entry at sampled t=10:50, 5 min after event recognition. For both
NatGas and EQT.US apply the same predicted direction.
Check the **completed** NatGas change 10:45 to 11:15 at
11:15 ET: if opposite the initial event direction, exit at the
11:20 quote mark; otherwise protective exit 12:05 quote mark.
This is a *sampled* invalidation and ceiling, NOT an intrabar stop.
EQT own 10:15..10:45 price direction is a prospective competing
predictor, and matched same-clock long, short, own-direction,
same-side fixed 12:05 and cash are descriptive benchmark policies.
The benchmark exits are fixed independently of RNE1's dynamic
event-invalidated exit; report both sides on shared entries, not
invented fills. Split release and placebo and chronological halves
(13 weeks each). Report missing bars, no anomaly, active signals,
entry/monitor/exit quote absence, conditional match counts,
weeks, signal frequency and exact financial eligibility unknown.

Only **gross midpoint bps and original executable-side BID/ASK crossing
bps before commissions, slippage, swap and EUR conversion** are scored
at this phase, with NO hypothetical EUR NET or financed trades.
The EIA report contents/forecast surprises are not inputs.
A signal may be interesting as price discovery yet economically
unviable: no financial promotion until current and as-of contract
terms, original quote+EUR currency conversion, modeled costs,
native EUR300 single ledger and independent 12+ months establish
incremental adversarial net and <=30% open-equity drawdown.
Do not convert Tuesday placebo into a trading strategy, select
advantageous subsamples, drop unfavorable EQT or NatGas signals,
change threshold/sign/exit/horizon, or turn repeated same-week
observations into independent held-out validation.

## Falsifiability and stop boundary

Assess release vs same-week Tuesday placebo anomaly rate, and
conditional signed markout vs each target's own completed-move control,
long, short, fixed and cash. Strong evidence requires favorable
**release-specific increment** over comparable Tuesday placebo,
chronological consistency and actual cost feasibility. Otherwise
close this exact experiment without promotion; low complete event
counts mean INSUFFICIENT EVIDENCE, not proven negative alpha.
Source acquisition remains allowed on later distinct hypotheses.
No order LIVE/DEMO, no Cloud trading, no OAuth reauthorization.

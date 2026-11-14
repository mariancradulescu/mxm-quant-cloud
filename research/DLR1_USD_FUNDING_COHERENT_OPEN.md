# DLR1 — coherent USD funding-demand repricing at U.S. equity cash opening

OWNER v2.0 as amended 2026-11-14. This is a *NEW DISTINCT economic
hypothesis* on existing globally EXPOSED development data, not retuning
a closed model, not RNE1/ECA1/VIA1/SRO1 and not an independent holdout.
This exact protocol is committed in a separate immutable freeze
BEFORE any DLR1 outcome scores/decryption of BDP1 source.

## Economic reasoning and competing explanations before implementation

U.S. equity cash opening at 09:30 America/New_York can induce
broker/dealer USD funding and collateral demand, globally repricing
FX and gold. A *coherent* USD balance-sheet demand shock should
drive EURUSD DOWN (USD up against EUR), USDJPY UP (USD up against
JPY), and XAUUSD DOWN (gold priced in USD), with all THREE
price directions agreeing on USD strength. Reversed signs may
represent easing USD funding demand. The first completed cash
M5 bar ends at 09:35 and is accessible to a native C# cBot
without news/online API.

Competing economic interpretations: ordinary USD factor exposures
fully incorporated by 09:35, mere FX denomination effects with no
dealer inventory friction, alternative risk-off gold demand
overwhelming USD funding, random correlated movement or
spreads/fees erasing any continuation. Gold may respond to
real rates instead of USD funding; the triple sign condition
is therefore FALSIFIABLE, not assumed to be a true funding shock.

Before any historical outcome, choose ONE primary exact hypothesis:
when EURUSD M5 first bar is DOWN, USDJPY UP and XAUUSD DOWN,
enter at 09:40 a 3-leg equal-notional USD-long synthetic
(short EURUSD, long USDJPY, short XAUUSD); reverse ALL 3 legs
only if EURUSD first bar UP, USDJPY DOWN and XAUUSD UP.
Otherwise ABSTAIN. This is NOT an always-on nonzero
descriptor: participation requires three directionally coherent
markets at one economically specified clock, no tuned size threshold.
Hold until the same day's 10:30 NY cash-open auction unwinding
horizon, no retuned exit or stop. Pair/asset weights: 1/3
equal notional for each of 3 legs, **gross proxy only**; no
fictional broker min-unit scaling or risk-netting.

Alternatives considered and rejected as primary:
- Tuning old USD-relative bps or QPI1 quote imbalance: forbidden
  recovery of closed exact descriptor outcomes;
- one-market FX bar momentum at arbitrary hours: no distinct
  funding-flow rationale and near-permanent participation;
- spot-only gold impulse without funding corroboration:
  no separate economic causal state.
Predeclared falsification comparisons:
1. always-flat cash (0);
2. fixed all-day long USD 3-leg basket, same 09:40/10:30
   historical bar proxy and equal notionals;
3. fixed short USD 3-leg basket on same days;
4. EURUSD first-bar directional USD 3-leg momentum WITHOUT
   triple-market corroboration, on all observed weekdays.
A conditional confirmation claim must beat both USD momentum
without coherence and cash on ALL shared complete 2026
weekdays, and show the economic direction in both fixed
26-week chronological halves. Never reinterpret an
opposite-sign result as a strategy to promote.

## Zero-broker-requests authentic original archive reuse

Use ONLY prior sealed BDP1 / 52-week original source,
Pepperstone EUR original account:
- original Actions run `41724643418`;
- artifact `13273950911` `sealed-source`;
- v2 original sealed envelope:
  `sealed-output/source.envelope.json` with
  `sealed-output/receipt.public.json`;
- authenticated BDP1 previous public exact original
  ciphertext SHA256:
  `e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370`;
- public readback result `13275041084`
  from the ORIGINAL authorized BDP1 program, with
  `RawReadbackMatched=true` and authenticated
  `SourceAudit.bars`: EURUSD 74195, USDJPY 74031,
  XAUUSD 70550. DO NOT rerun BDP1 original study or
  BDP1 test economics.
- Use existing `unseal_new(source_envelope, installed private key,
  "41724643418")` in preexisting
  `mxm-r3-custody-v1`, hash verify, read only
  original `bars` on exactly EURUSD/USDJPY/XAUUSD.
  Never emit original raw prices, account IDs, credential
  values, raw protobuf or decrypted source; no new
  broker queries, no OAuth, no Cloud, no orders.
  If source missing/truncated/corrupt, stop with
  `ORIGINAL_CUSTODY_UNAVAILABLE`.

## Exact dates, feature/entry/exit, missingness and reporting

Calendar 52 fixed Monday–Friday weeks
2025-11-03 through 2026-10-30 (260 scheduled days)
America/New_York local trading hours, DST handled.
Holiday/exchange closure counted as missing, never
silently excluded. At 09:35 only completed **09:30–09:35**
M5 open/close from all three instruments.
Define USD direction from sign of (EURUSD CLOSE−OPEN)
negated. Require USDJPY same sign as USD direction
and gold XAUUSD sign OPPOSITE USD direction.
Zero changes and unavailable first bars => abstain
or UNKNOWN, not forced trade. All 3 M5 required
consecutively from 09:30 through the bar opening
10:30 (full original bar 10:30–10:35) for gross
outcome admission. Primary 09:40 entry and 10:30
exit prices use OPEN of their original complete M5
bars — explicitly **ex-post OHLC OPEN PROXIES**, not
as-of executable BID/ASK, source quote completeness,
real cBot fills, or assured latency-free execution.
Model 3-leg total gross bps as average of
`direction*10000*log(exit_open/entry_open)`
with signs [-USDdirection, +USDdirection,-USDdirection].
No absolute price levels are public.

On 260 scheduled days record:
- source incomplete vs genuine no-coherent-event vs primary
  causal intent vs complete gross proxy;
- first 26 and last 26 full weeks in chronological order;
- aggregate 3-leg signed gross bps per active, per
  scheduled day and monthly/week frequency;
- on EXACT common source-complete weekdays (including
  abstention cash), compare primary vs both static dollar
  baskets, pure EURUSD first-bar USD momentum, cash.
  Do not compare primary active-only average against
  an unconditional per-day benchmark; same denominator.
- Also report primary on its events separately to
  reveal the selected opportunity behavior and
  baseline same-event gross bps, but never confuse
  it with independent confirmation.

Hard stop: if primary gross cumulative <=0 on shared
260-day calendar, if either chronological half <=0,
or if it does not beat EURUSD-only directional USD
basket *on same complete weekday denominator*,
no broker quote collection solely to repair this
exact rule; preserve negative/unknown result as
closed exact. Positive gross cannot automatically
promote: any original BID/ASK/FX, current fees/swap,
historical tariff, slippage, risk, native EUR300
funded C# and 12+month genuine independent
chronology require a SEPARATE precommitted follow-up.

No arbitrary filter added after results; no retune
the above times/horizon, universe, route or
direction. Final Cloud cBot may use multi-symbol
completed M5 from `MarketData.GetBars` without
HTTP/AI/news, subject to native parity/market
permission tests before admission.

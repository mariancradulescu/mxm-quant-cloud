# SFV1 — multi-class spot/forward necessary economic feasibility, BEFORE a price strategy

OWNER v2.0 and 2026-11-14 post-CSI1 causality amendment.
**FROZEN before new account queries and all source or outcome inspection**.
This is a **contract and quotation preflight**, NOT an alpha strategy,
new backtest, monthly forecast, financed portfolio, or trading approval.

## First: preserve and reuse the 2026-11-05 original public inventory

Original Pepperstone EUR full roster read-only run
[#41939175379](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41939175379)
public artifact `#13375915761`, original
`full-inventory.public.json` uncompressed SHA256
`1b15d08fa14bf67239acf31109b1f0f11093df7fe5c1b04fcbf1bff893040c5a`.
Source: 5,339 returned symbol names, 1,755 visible, only 96 contract probes.
A symbol in `instrumentNames` does not establish **enabled** or tradable.
The independently verified original source shows, at minimum volume:
SpotCrude EUR7.91 vs Crude-F EUR785.87;
SpotBrent EUR8.76 vs Brent-F EUR843.04.
Both oil -F single legs already cost MORE than the entire
OWNER EUR300 budget on that source date. No economically executable
300-EUR two-leg oil term basket under those same contract terms.
`SpotBrent` and `SpotCrude` are different geographic oil
benchmarks, not a spot/forward maturity pair. Neither the margin
gate nor name proves real futures deliverability or contract rolls.

## Choice among economically distinct directions, BEFORE data

- **Brent-F / SpotBrent, Crude-F / SpotCrude**:
  reject as a current EUR300 strategy under original as-of
  min-volume margin. Do NOT re-probe or score their historical
  outcomes merely for an easier relative-bps result.
- **JPN225-F / JPN225, NatGas-F / NatGas, US500-F / US500,
  AUS200-F / AUS200, USDX-F / USDX**:
  SELECT for a bounded original-current-contract preflight.
  This outcome-blind fixed order spans equity index, energy,
  and dollar-index term structures and explicitly covers new
  Pepperstone `-F` instruments instead of choosing a favorite
  after observing price returns. Every spelling came from the
  original 5,339-symbol readback. `-F` is an account **label**,
  NOT verified maturity or continuous futures convention.
- **EUBund-F / EUBobl-F yield-curve repricing**:
  distinct duration mechanism, not a two-maturity
  same-underlying spot/forward convergence; prior BCF1/RNV
  evidence remains frozen, no relaunch.
- **Existing FX, commodity or crypto mechanisms**:
  remain valid future alternative directions, not prohibited
  by failure of this exact term screen.
- A simple price differential, index-vs-future sign or
  same-direction ETF/index signal is **NOT** independently
  predictive information. CSI1 and CAC1 exact-rejected rules
  remain immutable.

The hypothetical information advantage IF such pairs prove comparable:
term structure of inventory carry, supply/storage shock, funding pressure
or index-dividend/funding repricing. Rival interpretations are:
contract/roll adjustment, index valuation/dividend carry,
spot and future different index mappings, seasonal futures delivery,
stale/out-of-session CFD quotes, currency conversion, insufficient
free equity and both-leg spread+fees. A normal arbitrage
convergence claim is not admissible without proving same reference
underlying, exact expiration, settlement/maturity and a defensible
causal fair-value reference. Spotware Cloud C# `Symbol.FuturesSettings`
contains last-trade/expiration when available; the installed Open API
ProtoOASymbol contract snapshot does **not** contain a verified
historical expiration/roll history. Current contract source cannot
manufacture that missing link.

## Bounded evidence collection, no price scoring

Only authentic original EUR account SCOPE_VIEW read-only;
reuse existing `owner_readonly_auth.authenticate`,
`StdlibCTraderTransport`, `guard.require_read_only_request`,
new-recipient custody and AES/RSA seal. No OAuth authorization
flow, no orders, no LIVE/DEMO trade, no Cloud activation.
One original enabled roster list and exact ten symbol
contracts where present; current minimum/step/max volumes,
long/short enabled, commission and minimum commission,
swap and financing, sessions and expected exact min-unit
buy/sell EUR margin. No missing optional field becomes zero.

For each enabled symbol choose exactly three **fixed** UTC
quote clocks on Thursday 2026-11-12: 08:15, 14:45, 19:45.
At each clock ask two independent historical
`ProtoOAGetTickDataReq` BID and ASK <=60s, causal as-of
<=20s age and <=20s timestamp skew. This is only a
very small indicative spread sample; no historical
execution schedule, depth, fills or spread distribution
is established. No future quote is involved.
If a symbol is disabled or not in original active roster,
mark that fixed pair UNKNOWN and do not substitute.
If a response is truncated or missing mark price UNKNOWN.

Absolute post-auth ceiling: **100** read-only
request/response calls, expected <=83 for all ten active.
Preserve every original raw protobuf, identity and
decoded status into encrypted source **BEFORE** public
contract/cost summarization. Public output may include
the ten selected public symbol names, margins, spreads,
missingness, contract metadata class but NEVER account
ID, token, proprietary raw prices or protected source.

**Necessary gate**: each same-underlying pair's current
max(buy/sell) single-minimum volume margin must be below
EUR300 individually; compare simple sum to EUR300 and
EUR210 stress point, but never assume margin offsets,
unlimited depth or a funded trade. A failed current
gate stops that exact pair. Passing only means eligibility
to investigate; next require verified Cloud
`FuturesSettings` / documentable expiration, roll,
cash-index/CFD carry convention, matched fresh original
quotes, per-leg EUR fee and genuinely new economic
information with same-opportunity cash and static
index benchmarks. Do not choose a directional policy
or collect 52 weeks of prices based on `-F` names alone.

## Causality law

1. At decision (t), preserve only quote/bar/metadata
   known as-of (t); do not filter based on future
   source presence.
2. Signal state, monitoring state, economic-result
   eligibility are separate immutable fields.
3. A valid intent survives if later monitoring or
   endpoint quote is absent: `OUTCOME_UNKNOWN`;
   never replace with ABSTAIN, zero profit or
   a different instrument.
4. Chronological exposure remains global
   DEVELOPMENT even for distinct new mechanisms.
5. Economic admission requires positive matched
   adverse EUR NET, benchmark advantage, one C#
   EUR300 funded ledger, 30% floating drawdown,
   system HARD21 and ultimately >=12 months
   meaningful evidence with independent confirmation.

No exact closed hypothesis is rerun; this work only
checks source contract feasibility and falsifiability.

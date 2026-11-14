# SFV1 — original multi-asset spot / forward contract capital gate: authenticated economic decision

Authority: OWNER `docs/OWNER_SPEC.md` v2.0 including 2026-11-14
CSI1 causality and economic-priority amendments.

**Verdict: NO SPOT/FORWARD TRANSACTABLE ALPHA ADMISSION, NO PRICE
STRATEGY AUTHORIZED.** Exact contract preflight is complete.
Distinct futures-based hypotheses are not globally invalidated.
Do not repeatedly re-collect the same contract screen, retune
a rejected study or call a basis-spread an alpha signal.

## Chronological protocol freeze, immutable original receipts

- Ex ante economic reasoning and five exact prospectively fixed pairs:
  `research/SFV1_TERM_PAIRS_ECONOMIC_FEASIBILITY.md`,
  separate freeze commit
  `20627d274531828fd71c91203786605d85510c15`
  BEFORE implementations or any new source observation.
  Original protocol SHA256:
  `55651e838c7b476588a9462e5c1c82db562752f8a2ae5389fdd07e3af4e530c1`.
- PR [#300](https://github.com/mariancradulescu/mxm-quant-cloud/pull/300)
  merge commit `879736c29a581a83285b2d01f1978677a47c4d50`.
  Specialized unit/causal tests SUCCESS.
- Original Pepperstone protected read-only
  [Actions #43642534099](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43642534099),
  verify, one-time custody, original-account contract and quote
  collection **all SUCCESS**.
  **67** account-authenticated read-only requests after original account
  binding. No LIVE/DEMO orders, OAuth reauthorization or trading Cloud.
- Original raw protobuf and decoded original selected snapshots sealed
  BEFORE emitting public metrics:
  [encrypted source artifact #14133100260](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43642534099/artifacts/14133100260),
  inner `sfv1-original-protected.v2.enc`, original uncompressed
  ciphertext SHA256
  `aa6f5f18dfc77add5401a42b5b18e26d833377923566d0ddb28b2c2852e60023`.
  Protected-run plaintext SHA256 as reported in receipt
  `a217b33585cdd8ce6308977de0eeb0b83af1686a0dc4d909d5ed22e42df8f50d`.
  Do not claim independent decryption of private source in a public reader.
- Original [public artifact #14133135192](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43642534099/artifacts/14133135192),
  `sfv1-original-public-capital-screen.json`,
  original extracted uncompressed SHA256 independently verified:
  `e711049090931c8e87fd4ddd666e966432be7419f260cfcf40078419009c9e2c`.
- Reuse original 2026-11-05 full roster
  [#41939175379](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41939175379),
  public `#13375915761`, SHA256
  `1b15d08fa14bf67239acf31109b1f0f11093df7fe5c1b04fcbf1bff893040c5a`.
  That original artifact exposed all 5339 names but **only 1755
  visible** symbols and 96 probed contracts. Name alone != enabled.

## Authenticated current contract static necessary gates — EUR300

Margins below are maximum of current minimum-volume buy/sell
on 2026-11-14 source; **NOT historical as-of or filled positions**.
The 210EUR stress reference is a simple 30%-down static cash
point, NOT pathwise OWNER DD certification or risk allocation.

| Exact pair | Current min spot EUR | Current min -F EUR | Simple sum EUR | Result |
|---|---:|---:|---:|---|
| JPN225 / JPN225-F | 173.03 | 17.32 | 190.35 | PRELIMINARY_ONLY |
| NatGas / NatGas-F | 27.93 | UNKNOWN | UNKNOWN | -F MISSING_OR_NOT_ENABLED |
| US500 / US500-F | 34.22 | 343.18 | **377.40** | REJECT_EXACT_PAIR_CAPITAL |
| AUS200 / AUS200-F | 27.88 | UNKNOWN | UNKNOWN | -F MISSING_OR_NOT_ENABLED |
| USDX / USDX-F | 187.78 | 18.76 | 206.54 | PRELIMINARY_ONLY |

Previous 2026-11-05 original account:
- SpotCrude EUR7.91, **Crude-F EUR785.87** at min unit.
- SpotBrent EUR8.76, **Brent-F EUR843.04** at min unit.
- HK50 approximately EUR27.71 plus HK50-F EUR277.33 =
  EUR305.04 before spread/fees, indicative then.
- GER40-F EUR1335.98 at min unit.
No new price or contract request was made for these old costly
pairs in SFV1. A stale contract snapshot is not a permanent
claim that future terms can never change.

All queried enabled legs had original tradingMode=0
and short permissions explicitly true. `NatGas-F`
and `AUS200-F` were not confirmed enabled (the public
report does not differentiate missing from disabled).
No substitute symbol, other account or arbitrary `_SB`
suffix was used.

## Crucial hidden economic problem: spot/-F min-volume hedge imbalance

On BOTH apparently inexpensive pairs:
- JPN225 has **minimum 10 units**, JPN225-F min **1 unit**;
  JPN225 current lot size 100 units, JPN225-F lot size 1 unit,
  current quote currency both JPY.
- USDX has min **10 units**, USDX-F min **1 unit**;
  both current lot size 100 units and quote currency USD.
- Thus the minimum-volume **two-leg** scenario is not
  certified exposure-matched, even if simple sum margin
  fits EUR300. A *conditional one-for-one unit-value*
  thought experiment would require 10 units of -F to offset
  10 of spot, hence indicative linear scaled sums:
  JPN225 EUR173.03 + 10*EUR17.32 = **EUR346.23**;
  USDX EUR187.78 + 10*EUR18.76 = **EUR375.38**.
  These are transparent ILLUSTRATIVE linear margin
  assumptions, **not original broker expectedMargin(10)**
  requests, margin-offset proof, point-value equality,
  or a certified delta-neutral hedge. The different
  JPN225 lot sizes specifically require point-value
  contract reconciliation before invoking unit matching.
- Original **single minimum** margin JPN pair leaves
  EUR109.65 vs EUR300, but only EUR19.65 vs EUR210
  illustrative stress. USDX leaves EUR93.46 initially
  but merely **EUR3.46 vs EUR210**; no observed floating
  protection or correlated drawdown evidence.
- Therefore neither pair warrants a paired spot-forward
  **NET EUR** strategy simply from a below-budget
  unbalanced minimum-volume portfolio.
  A single-leg directional forecast is a **different**
  untested hypothesis, not a free hedge.

## Causal cost and contract basis evidence

Three fixed original-market quote clocks on
2026-11-12 08:15 / 14:45 / 19:45 UTC:
- JPN225: **3/3** fresh quote-side spreads, bps:
  1.150740, 1.311583, 1.308062.
  JPN225-F: **3/3**, 2.626826, 2.619743, 2.612863.
- USDX: **2/3** fresh, 5.244144 and 5.241345 bps;
  USDX-F: **2/3**, 5.834306 and 5.831187 bps.
  Third quotes fail freshness/asynchronicity and
  remain UNKNOWN, not zero.
- US500, US500-F, NatGas and AUS200 spots also had
  3/3 fresh original quotes but their paired futures
  gates already failed.
- These three observations do not prove expected
  historical spreads, actual fills or all-in EUR cost.
  Each two-leg roundtrip pays BOTH crossing spreads,
  plus any commissions, slippage, financing and
  currency conversion; relative basis in bps alone
  cannot imply profitable EUR risk-adjusted return.

Original public `brokerDescription`:
JPN225-F 'Japan 225 - Forward (9 Sep - 8 Dec)';
USDX-F 'US Dollar Index - Forward (10 Sep - 9 Dec)'.
These point toward a CURRENT broker-labeled term
period but do **NOT** certify the actual exact
expiring instrument at each historical decision,
historical changes in roll/continuous CFD adjustment,
fair carry, corporate action/dividend treatment,
or actual `FuturesSettings` in running native Cloud.
OpenAPI `ProtoOASymbol` contains no historical
maturity/roll series. **Current descriptions are not
a legal or financial reference to historical expiry.**
JPN225 spot historical swap terms differ from
JPN225-F current zero wire terms; USDX-F has a
four-hour swap period and absent explicit
swapCalculationType: never equate missing cost
calculation with zero or frictionless funding.

## Economic decision and continuation without study churn

1. **CLOSE EXACT financed double-leg Crude/Brent
   futures paired basis on the observed terms**, and
   **reject US500-F** now because minimum future leg
   alone exceeds EUR300.
2. Mark NatGas-F and AUS200-F `CURRENT_MARKET_UNAVAILABLE`,
   with no invented prices or economic negative return.
3. Retain JPN225 and USDX pairs as
   `NOT_YET_COMPARABLE_OR_FINANCED`:
   cheap future minimum volume is NOT a proved
   delta-hedged basket; expiry/roll/point value
   and cost/FX consistency remain unknown.
   **No strategy, price return backtest, signal,
   funded NET, or portfolio qualification** is
   authorized solely by this preflight.
4. For any distinct future JPN225 or USDX signal
   investigation, first prove native Cloud symbol
   expiry, point value and origin/roll conventions;
   then choose which INFORMATION arrives
   before decision and why it predicts subsequent
   relative repricing rather than trivial funding
   carry. Explicitly compare a single-leg target,
   no-trade and simple own momentum; freeze its
   entry, invalidation, exit and abstention before
   actual labels.
5. Continue both OWNER directions. Existing original
   bars/ticks can support **new** mechanisms on old
   symbols; new Spotware-enabled instruments may
   be investigated via original account read-only
   whenever economically relevant. BCF1 yield
   curve was previously authentic-source confirmed
   but had **0** fresh EUBobl-F quote pairs and **1**
   EUBund-F from 13 sample clocks each, so cannot
   pretend that bond spread economics were financed
   or exact BCF1 predictor evaluated. No rerun of
   any closed study to find favorable outcomes.

The final criteria remain one autonomously executable
native C# Cloud cBot, initially ONE EUR300 capital
without replenishment, 30% global drawdown incl
floating, HARD21 **systemic** with no forced
trades, true matched robust adverse EUR NET,
minimum 12 relevant months and independent
confirmation. None is certified by SFV1.

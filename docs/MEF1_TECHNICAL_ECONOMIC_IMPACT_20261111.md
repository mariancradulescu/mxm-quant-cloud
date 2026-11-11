# MEF1 original-versus-diagnostic economic source impact — 2026-11-11

Authority: [OWNER v2.0](OWNER_SPEC.md), 2026-11-11 methodological
clarification. The original MEF1 is closed **as an economic study**;
a material source-cost bug may still be measured through a separate,
transparent technical diagnostic. No historical results are overwritten,
retuned, inverted or promoted. There is no new independent time period.

## Exact provenance

| Cohort | Run | Public artifact | ZIP SHA-256 | Raw public JSON SHA-256 |
|---|---|---|---|---|
| Original frozen MEF1 | [42889124457](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42889124457) | 13796774195 | `b0ff18e3ccf1bf4ddacbc5cd4a038db1d08519ec4d94545025e532bc25a56a8c` | `ce3a2079296dfe5e68688bbd0782ec5bcd492fc5a00b0c1b2df5555851b47068` |
| Incidental historical diagnostic | [42999359354](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42999359354) | 13844254968 | `e7e6ea2cf4cd7e27ddee07b219873a44e57b206b166a75d7b68292840ea2fbcb` | `80e4a278c67cadadee4314019d784619ba412c6ac7a6954e747b3312bffea62b` |

The same original frozen MEF1 protocol hash
`0ae6bc874b6064d7e92495b4f870a75ab71ed94303f6750abb02bb18efb020bd`
appears in both receipts. Their respective post-auth read-only
request counts are 121 and 125. The second run is **NOT** a replacement
for the first. Both have `fundedNetEur=null`, zero orders and zero
Cloud trading activation.

## Complete as-observed difference (all five originally prespecified instruments)

| Market | Original valid → diagnostic valid quotes / 8 | Original → diagnostic quote+current-fee / 8 | Diagnostic observed median minimum friction (bps) | Diagnostic current minimum margin (EUR, buy/sell) |
|---|---:|---:|---:|---:|
| AUDUSD | 6 → 8 | 1 → 8 | 0.9805 | 30.83 / 30.82 |
| US2000 | 8 → 8 | 4 → 8 | 1.0581 | 25.46 / 25.46 |
| SpotCrude | 8 → 8 | 4 → 8 | 2.5492 | 7.82 / 7.82 |
| Coffee | 8 → 8 | 4 → 8 | 16.6557 | 238.39 / 237.96 |
| XPTUSD | 8 → 8 | 4 → 8 | 17.8326 | 140.52 / 140.26 |

"Minimum friction" here is sampled spread plus current contractual
minimum-size round-trip fee expressed as bps; it does not include
prospective fill probability, adverse slippage or rollover. Do not use
it as full net cost, a historical tariff certification or evidence that
three independent positions can be financed together.

- The exact two newly recognized historical paired quotes are AUDUSD
  **2026-10-06 and 2026-10-20**, both observed BID=ASK.
  All other originally valid non-null spread measurements remain
  unchanged at the matching eight dates.
- Quote equality alone **does not explain** why every market's fee
  coverage increased. Commission FX valuation corrections since the
  original run and the changed current-term observation clock affect
  fee completeness. The output records those factors separately; a
  one-error causal attribution from two executions would be unsound.
- Observed current margin changed between run dates even for
  unchanged historical quote clocks. This is not a broker historical
  margin or interest-rate reconstruction and not a portfolio leverage
  certificate.

A byte-pinned deterministic comparator in
[`research/mef1_technical_impact.py`](../research/mef1_technical_impact.py)
recomputes the full observation/date-level delta without broker requests.
Its CI downloads the original two already-existing *public* artifacts
with independent raw SHA verification, and publishes a third,
**technical impact only**, summary. No economic forecast is scored.

## Decision with economic value of information

The corrected surface supports treating AUDUSD, US2000 and SpotCrude as
**source-and-cost feasible research routes** relative to the expensive
XPTUSD/Coffee minimum-volume exposure. These are not selected by
profitable hindsight returns: MEF1 contains no directional return
labels. There is no favorable model hidden in a locked quote.

For any genuinely new *portfolio-level* predictive mechanism, favor
reusing existing authenticated instrument/FX/contract infrastructure
and collect only economically informative new source clocks. Require
full participant availability and synchronized clocks before testing
joint capital. Compare causal signals with funded long, short,
no-signal and relevant risk/feature benchmarks; include adverse
slippage, missed quotes, financing, open equity and adverse margin.
No statistical winner may be promoted on these already exposed
eight Tuesdays, and no one-family HARD21 hurdle is imposed.
The native C# single EUR300 ledger and allocator remain final
behavior authority.

**Status: source/contract information gain only. No new admitted
predictive model; no funded incremental NET, prospective HARD21,
12-month independent confirmation or Cloud activation.**

# Common-portfolio evidence after PR #195

Authority is [OWNER v2.0](OWNER_SPEC.md). This analysis reads original public
receipts at audited baseline `d6aae7d3462fef40b0c5ffcecc4a0841abd33dd6`.
The cohort consists of the W20–W21 and W32–W33 equity-index windows and the
RRP1, LDP1 original and replica, JRC1, OTC1, MCT2 and BMR1 receipts. Each has
one EUR300 joint C# book and two separately reported one-family counterfactuals.
The cohort covers these nine Pepperstone runs. Each row
is one preserved simulation. Cross-study totals have no common-capital meaning.

## Results on the original books

Amounts are modeled EUR after costs. Peak sampled margin is simultaneous used
margin in the joint receipt. Weekly maxima are computed from the recorded
closure week counts. Funded references have their own model ledger. Same-clock
descriptive references do not finance exposure. Cash is zero NET.

| Study | Closures | Highest observed weekly count | Central NET | Adverse NET | Peak sampled margin | Evidence against admission |
|---|---:|---:|---:|---:|---:|---|
| US index W20–W21 | 24 | 14 | +5.9442 | +3.4483 | 154.86 | Only +0.0377 central versus descriptive long. No symmetric funded direction reference published |
| US index W32–W33 | 25 | 13 | +20.2839 | +17.6108 | 157.48 | +44.0910 central versus descriptive long. No symmetric funded direction reference published |
| RRP1 | 57 | 11 | +18.4222 | +13.3879 | 216.84 | −24.0193 central versus best same-clock descriptive side |
| LDP1 original | 29 | 7 | +73.1209 | +7.2173 | 259.10 | Adverse gain only 9.87% of central gain. The later exact replication lost money centrally |
| LDP1 replica | 33 | 10 | −13.5808 | Unknown | 233.22 | 68 missing adverse equity samples. On available adverse marks, sampled drawdown reached 25.36% |
| JRC1 | 4 | 3 | −2.9689 | −3.4067 | 33.33 | Funded long +1.7707 adverse. USDJPY branch had zero closures |
| OTC1 | 8 | 2 | +0.2947 | −0.3596 | 39.90 | Funded long +0.9488 adverse. WTI branch had three signals and zero closures |
| MCT2 | 20 | 6 | −32.2647 | −33.5675 | 191.19 | Funded long −5.3238 adverse. Both mechanism ablations had negative adverse marginal NET |
| BMR1 | 17 | 2 | −2.9109 | −5.4101 | 213.77 | Funded short +73.0216 adverse on its own exposure and allocation path |

JRC1 uses its recorded ISO weeks W32–W36 under the existing [provenance
addendum](../research/JRC1_PROVENANCE_ADDENDUM.md). BMR1 is event-sampled.
The 47 observations of a study in an ISO week include overlaps and are
not a continuous 47-week calendar. Their maximum was 14 closures. None
of these recorded books demonstrated HARD21. All nine receipts flag
incomplete sampled calendars and lack continuous historical equity evidence.

## Incremental contribution and capital

For each run and cost scenario, subtract both one-family counterfactual
NETs from the joint NET. For all nine central and eight complete adverse
comparisons the absolute residual was at most EUR 0.000000000000009,
consistent with JSON export precision. The ninth adverse comparison is
unknown. The residual measures interaction in closed NET on these particular paths.
Drawdown, overlapping positions and future diversification require separate evidence. An exact-time join of the published
joint margin snapshots found only one cross-study pair with positive
margin on both books at the same timestamp. RRP1 and MCT2 had nine such
timestamps out of 600 common marks. No cross-study balance or exposure
was combined into a new book.

The LDP1 original ledger reached EUR259.10 of sampled used margin. Its
central gain declined by EUR65.9036 under the published adverse scenario.
The replica retained EUR233.22 peak sampled margin and lost EUR13.5808
centrally. Its missing adverse marks prevent closing the risk evidence.
This is a strong reason to require adverse marginal NET and synchronized
exposure marks before giving an allocator economic credit for a second
family, even when the sum of its standalone NETs looks attractive.

The positive index observations remain exposed, with the NAS100
configuration frozen. RRP1's positive absolute result is benchmark
inferior. Cash and appropriate directional references must accompany
future candidate assessment. Where a directional reference can be
financed, apply the same broker grid, fills, costs and risk in its own
reference book. A reference outperforming the model does not authorize
inverting or promoting it.

## Research implications for the common C# path

- Evaluate persistence and economically meaningful incremental advantage
  together. Use aligned calendars and compare the complete portfolio with
  the same selector and one family removed. Report joint capital
  constraints and floating risk separately from closed-NET interaction.
- Before an expanded evaluation, use actual source clocks, broker terms,
  fill eligibility and observed signal frequency to assess whether the
  proposed family could materially contribute. Low minimum margin is
  useful only when fills and opportunities exist. The Brent–WTI receipt
  had complete pricing on all 14 signals but failed both half-period
  sample requirements and had adverse NET of −31.53 and −14.93 bps.
  Its original verdict is `INSUFFICIENT_COVERAGE`.
- A new qualifying candidate needs a prospectively registered mechanism
  and source window, exact execution and FX evidence, synchronized marks,
  and sufficient chronological coverage. Include the existing native
  lifecycle, benchmarks and ablation in the admission design. Previously
  exposed weeks can be used for development only. None of the configurations
  in this analysis enters the next common ledger on these receipts.

## Prospective margin evidence

Original snapshots pair adverse equity with the central ledger's used margin
field. In the LDP1 replica, one sample at 2026-10-21 08:20:01.500 UTC
shows EUR232.9791 adverse equity and EUR233.22 central used margin.
These values come from different scenarios. The adverse free margin
at that time is unknown in the original receipt.

Future native historical receipts expose adverse used and free margin
directly from the same adverse ledger summary as adverse equity. Both
fields are nullable when the adverse evidence is unavailable. Central
used margin keeps its original definition. This supports measuring
simultaneous capital pressure in future common-portfolio evaluations.

This review made zero broker requests, scored zero new signals and reran
zero historical configurations.

## Original archives

| Study | Original run and archive | SHA-256 |
|---|---|---|
| US index W20–W21 | [42620847301 / 13676612881](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42620847301/artifacts/13676612881) | `c03f4dbd009b02b2c72002d89ef03730cba15c1647f321634209eb0501712e8b` |
| US index W32–W33 | [42657295123 / 13692989063](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42657295123/artifacts/13692989063) | `7fecb040de3ca676f148b33d09447bf860d2e0deb6075326562aee95070227a9` |
| RRP1 | [42781700638 / 13747681714](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42781700638/artifacts/13747681714) | `be16670064eaf4b253f961d2b927c430ccd11c36508211b44096612505e0a4cd` |
| LDP1 | [42797204156 / 13754657994](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42797204156/artifacts/13754657994) | `a0cbe24c57603d25a5a2039c4c57fb4d3818b1f8790cf79195ef14ea99957bba` |
| LDP1 replica | [42803043068 / 13757931330](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42803043068/artifacts/13757931330) | `1305674483de3033e81081df6fdc60d94bc266cb34a23d28d4c05c5ffafddd7a` |
| JRC1 | [42811179071 / 13764030872](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42811179071/artifacts/13764030872) | `f70fa959bb678fc10989351259cee56101ddf13899eae9c2abff91e24c29e6f4` |
| OTC1 | [42814122228 / 13765215820](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42814122228/artifacts/13765215820) | `32e86c84fe21a400bc2912da09bd1e104e17bbe4102466b42925d971b4bf9ec7` |
| MCT2 | [42822802931 / 13769185362](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42822802931/artifacts/13769185362) | `6e3ab526c44f146f68adc3f9c256844c7ce528b99a4355f48fd7397eb7c1a6ad` |
| BMR1 | [42838094280 / 13774657456](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42838094280/artifacts/13774657456) | `9295180de8c10450b23781b180a9144b6c2ff9b1f94c10e196354712b5d0e0a9` |
| Brent–WTI | [42969163659 / 13832866345](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42969163659/artifacts/13832866345) | `832b9a41117ebc285f7dc75063d288ffee0aca77b95ea46d12b8b984c9211b1c` |

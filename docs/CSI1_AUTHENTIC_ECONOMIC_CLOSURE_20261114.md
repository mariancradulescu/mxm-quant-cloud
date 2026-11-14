# CSI1 — original corporate overnight information-diffusion development: negative NET and source-selection limitation

Authority: `docs/OWNER_SPEC.md`, OWNER v2.0 and post-CAC1 decision
2026-11-14. **EXACT CSI1 RULE CLOSED / NO ECONOMIC PROMOTION.**
Original protocol and sources immutable; zero rerun, retuning, reversed-policy
promotion, favorable subgroup, changed symbol, clock or exit.

## Chronology, original-source evidence and honest evidence level

- Independent ex-ante protocol freeze `ed4189d3f9f0687d14cac49112466e312bab6e2e`
  before any source access or outcome scoring; implementation
  `research/csi1_company_gap_original_eur.py` and tests, PR
  [#297](https://github.com/mariancradulescu/mxm-quant-cloud/pull/297)
  merged at `03181f8792c70adba00d4caf77195321aa72483a`.
- Original protected Pepperstone account read-only
  [run #43639342108](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43639342108),
  every job SUCCESS. 1,922 authenticated original account read-only requests,
  zero orders, zero Cloud, zero OAuth reauthorization. The observed token
  was technically trade-capable, but OWNER allowlist restricted operations
  to read-only. Original exact AMD.US, INTC.US and NAS100 roster/contract
  and EURUSD route were present; original source identity was checked by
  authenticated source program.
- Authentic original encrypted source ZIP
  [artifact #14132045125](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43639342108/artifacts/14132045125),
  inner file `csi1-original-protected.v2.enc`, independently downloaded
  and SHA256 of uncompressed encrypted bytes =
  `7381fe718e84e5d24bb9b65cff6d5710930b71b8e72bd38a8899f73b0aad9a94`.
  Protected program published sealed plaintext SHA256
  `09dd31f5b47340ca4867bd6c8f059d640dffb6ba93c679feb5ff5f709d66b3e0`.
  The latter was NOT independently decrypted in this public assessment.
- Public original financial artifact
  [#14131830765](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43639342108/artifacts/14131830765),
  uncompressed `csi1-original-public-economic.json` original SHA256
  `73a66da55adf167d513696b8692474c68dd549465e817a8ab50f03e81e861e19`;
  protocol hash in original receipt
  `836adbc1b4e6db92f1217d4b1207ed7f530ded47417150f6f8b10f52aa0ca6e6`.
- Source calendar 56 weeks 2025-10-06..2026-11-01, first four
  calendar weeks warmup; 52 development weeks 2025-11-03..2026-10-30,
  260 scheduled weekdays. These are **globally previously exposed**;
  not fresh chronological confirmation or a 12-month certified portfolio.

## Original coverage and causal-event evaluation

| Original financial state | Scheduled days |
|---|---:|
| 09:35 AMD-vs-INTC and AMD-vs-NAS100 no directional concordance | 103 |
| Same-direction but not larger than four same-weekday prior residual shocks | 45 |
| Missing prior close/current morning gap | 23 |
| Incomplete four-week same-weekday reference | 70 |
| Exact causal intents AND complete original financial quote/FX/current-contract evaluation | **19** |
| **Total** | **260** |

19 events priced in 18 distinct weeks, first 26 evaluation weeks 10 events,
last 26 weeks 9 events. This is not 19 closed broker trades.
Original current min AMD buy/sell margin EUR9.75/EUR9.74.
Both margins are as-of-current, NOT certified historical funding.

## Exact matched EUR money — conditional only, original event subset

Original historical spot BID/ASK AMD and EURUSD signed conversion,
original CURRENT contract commission/FX/cost schedule, with additional
model 0.5 bps central and 2.0 bps adverse roundtrip slippage per
min wire-volume AMD share CFD. **Not historic broker-realized PnL,
not a common EUR300 funded C# book.**

| Same 19 causal events | Central NET EUR | Adverse NET EUR |
|---|---:|---:|
| CSI1 primary 09:40 adaptive invalidation and 10:20 / 11:00 exit | −1.843692 | **−1.931408** |
| Same primary side, fixed 11:00 exit | −2.321684 | −2.409390 |
| Own AMD first-cash-bar momentum | −1.152355 | −1.240061 |
| Fixed long | −2.300617 | −2.388323 |
| Fixed short | −0.138706 | −0.226412 |
| Opposite-side falsification control — NOT promotable | −0.117639 | −0.205345 |
| Cash | 0.000000 | 0.000000 |

Primary adverse advantage over fixed same-side: +0.477982 EUR,
but primary advantage over own momentum **−0.691347 EUR**;
absolute vs cash −1.931408 EUR. Thus improvements against a still
losing fixed exit DO NOT produce absolute or incremental advantage.

First 26 weeks: primary adverse −0.216459 EUR (10 priced);
same-side fixed and own momentum each +0.501321 EUR.
Last 26 weeks: primary adverse −1.714948 EUR (9 priced),
same-side fixed −2.910711 EUR, own momentum −1.741381 EUR.
Both primary chronological halves negative after cost.
Do not select the opposite-side falsifier, particular half, a modified
surprise threshold, or current quote costs to rescue the original policy.

## PRE-RESULT causality defect — original result must be bounded

The technical issue in
[`docs/CSI1_SOURCE_SELECTION_CAUSALITY_PRE_RESULT_20261114.md`](CSI1_SOURCE_SELECTION_CAUSALITY_PRE_RESULT_20261114.md)
was committed independently via PR #298 while the original source
was still collecting, **before original financial results were viewed**.
The collector set a day's full bar source unavailable if even its
*future same-day* 15:50..16:05 close-bars were missing, affecting
09:35 causal intent admission. This is forward source-availability
selection contamination, even though the signal direction itself
only reads already completed prices.

Therefore the 19 priced signals and above NET outcomes are an
**original financially priced subset**, not a full causal census
proving an edge or nonedge for every eligible 09:35 opportunity.
Original 93 missing/referential days are UNKNOWN, not economic
abstentions, zero returns or invented trades. Preserve original
result and hash unmodified. A fully correct separate source-intent
cold reconstruction could use the sealed raw protobuf without
changing signal/entry/exits, but any newly identified unquoted event
must remain UNKNOWN. Do NOT re-collect/re-score the exact study just
to search for a favorable result. No F1 promotes this rule on
this already exposed outcome sample.

**Economic decision remains conservative:** observed original
matched paths lose absolute and against own momentum, in BOTH
chronological halves; no supported NET-positive candidate, so
the exact CSI1 configuration closes without native cBot admission.
The selection defect additionally prohibits any stronger negative
population-wide claim. Retain all original artifacts and technical
audit. Never use the reverse falsifier as a recovered strategy.

No funded round trips, no realized fees, no sampled or continuous
cross-strategy DD30 proof, no hard21, no untouched 12month
confirmation and no independent Cloud/Android deployment evidence.
Final OWNER one €300 native cBot, no orders/Cloud remain unchanged.

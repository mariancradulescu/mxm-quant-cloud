# CMR1 — original authenticated result and exact closure (2026-11-11)

Authority: [OWNER v2.0](OWNER_SPEC.md). This is an evidence disposition
written AFTER the original once-only run. It does not alter, relaunch,
invert, retune or promote the frozen [CMR1 protocol](../research/cmr1.md)
or [CMR1 evaluator](../research/cmr1.py).

## Custody

- Original merged PR: [#199](https://github.com/mariancradulescu/mxm-quant-cloud/pull/199)
- Authoritative source execution: [42994900911](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42994900911)
- Original public ZIP artifact: [#13843721294](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42994900911/artifacts/13843721294)
- Original ZIP SHA-256: `306107af54cbce04c9efe8c3c7b2d182c41351f50e0ea8bfd8f1ac313a00da12`; matches GitHub artifact digest.
- Original uncompressed `cmr1-public-receipt.json` SHA-256: `dfd867512c2a58c2d0e2eaa126d84dc51af4271370e9469cadebf03486dce570`.
- Ex-ante protocol SHA-256, recorded by original run: `375edf39e4934b2056b95b3f10b4a98dfe4e5832a9181e29e0e534fff7bc2820`.
- 249 original read-only Pepperstone requests after account authentication, 25,416 decoded historical M5 bars, minimum observed current buy/sell margin 25.45/25.45 EUR.
- No orders, no Cloud activation, no funded C# replay, no certified historical fills/tariffs, no independent confirmation. Read-only authenticated original LIVE account; zero LIVE/DEMO trading operations.

## Fixed two-half outcome

| Original evidence field | Weeks 0–12 | Weeks 13–25 |
|---|---:|---:|
| Scheduled original dates | 65 | 65 |
| Completed-bar signals | 16 | 8 |
| Fresh side-priced and FX-convertible comparable events | 5 | 0 |
| Priced active weeks | 5 | 0 |
| Missing comparable quotes/FX at signals | 11 | 8 |
| Price-coverage gate | false | false |
| Cost-conditioned model adverse mean, bps | +13.065261840503256 | unknown |
| Same-clock long adverse mean, bps | +14.246683403538768 | unknown |

First-half conditional modeled reversion is inferior to the same-clock
always-long benchmark by approximately 1.18 bps on only five priced
observations. The second half has zero priced observations, and the
comparison is unknown. These bps are retrospective same-clock
current-term quote/cost scenarios, **not funded EUR NET** or a C# cash
ledger. The public receipt does not separate incomplete M5 calendars
from complete no-signal days in its combined count; no stronger claim
about that fraction is justified.

## Frozen disposition

Original verdict: **`INSUFFICIENT_COMPARABLE_SIGNALS`**. Coverage failed in both
halves. No route, configuration, rule, variant, instrument, side or
portfolio is admitted. Do not reopen CMR1 via lower thresholds, altered
session clocks, stretched as-of age, switched sides, revised splits or
outcome-based calendar subsets. There is no C# entry, position, exit,
risk or HARD21 demonstration to promote.

Preserve the source SHA and original artifact; a later, genuinely
distinct economic hypothesis needs separate ex-ante economic and
portfolio grounds, not a CMR1 rescue. Current system economic advantage
remains **UNPROVEN**.

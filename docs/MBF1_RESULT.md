# MBF1 — Authentic four-family economic screen: exact closed result

Controlling authority: `docs/OWNER_SPEC.md` OWNER v2.0. Original run: [#41971150620](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41971150620). The protocol `research/mbf1_protocol.json` was registered and merged before collecting outcomes.

## Original authenticated source

- Existing Pepperstone-linked cTrader SCOPE_VIEW account binding, encrypted v2 raw protobuf source, cryptographic readback verified; 531 read-only requests, zero orders and zero Cloud activation.
- 52 predeclared weekly H1 source windows; complete observed closes: GBPJPY 6,188; ETHUSD 8,713; HK50 4,198; JPN225-F 5,888 (24,987 total). No truncated H1 reply; missing bars remain missing.
- 39 development observation clocks per instrument: GBPJPY 21 valid paired quotes; ETHUSD 30; HK50 26; JPN225-F 9 (86/156). Unusable 70 quotes remain unknown, never zero-cost.
- Current minimum margins only: GBPJPY EUR39.93; ETHUSD EUR10.75; HK50 EUR27.90; JPN225-F EUR17.22. Not a jointly executable portfolio or historical margin guarantee.

## All eight predeclared selection outcomes

Means are **bps per unfunded close-to-close signal proxy**, with historical fixed-clock spread observations plus separately hypothetical commissions/conversion/slippage; financing, historical fills and future costs unknown. Price-close proxy is not a bid/ask fill.

| Family | Hold | Selection episodes | Gross bps | Conditional central bps | Conditional adverse bps |
|---|---:|---:|---:|---:|---:|
| Tokyo-London GBPJPY unwind | 2h | 19 | +1.12 | -5.53 | -12.03 |
| Tokyo-London GBPJPY unwind | 4h | 19 | -0.21 | -6.87 | -13.37 |
| ETHUSD weekend shock drift | 2h | 27 | -11.46 | -27.15 | -37.55 |
| ETHUSD weekend shock drift | 4h | 27 | -20.93 | -36.61 | -47.02 |
| ETHUSD to GBPJPY risk deleveraging | 2h | 37 | -1.96 | -8.62 | -15.12 |
| ETHUSD to GBPJPY risk deleveraging | 4h | 37 | -0.92 | -7.57 | -14.07 |
| JPN225-F to HK50 Asian handoff | 2h | 0 | UNKNOWN | UNKNOWN | UNKNOWN |
| JPN225-F to HK50 Asian handoff | 4h | 0 | UNKNOWN | UNKNOWN | UNKNOWN |

The Asia risk handoff has **260 feature-missing decision clocks** because joint exact completed four-hour index histories were unavailable. This is insufficient source support, not an adverse-profitability measurement.

Selection-only admission was fixed before source collection: at least 40 complete opportunities, 8 active selection weeks, at least 8 target historical quote pairs, and conservative 3-standard-error weekly adverse-cost lower bound above zero, across all eight groups. **0 of 8 groups pass.** Favorable-looking exposed audit intervals cannot rescue a group.

## Decision and prohibitions

MBF1 is frozen exactly with no tuning, inversion, source-subset cherry-picking or rereun. No group warrants native C# EUR200 funded incremental replay. Therefore `fundedNetEur=null`, no funded round trips, no measured portfolio drawdown, no system HARD21 or independent confirmation. Do not interpret absence of funded replay as simulated losses in EUR. ERP1, TWC1, IPF1 and other closed studies were not rerun.

Original public JSON SHA256: `94b582f5edafb1ec6098359898e0aa24a5cf4ebaf2603dd1700beffd45b2f7de`. Raw encrypted source SHA256: `5754b056f0e3995c8121d16d89bcaa557d30738a8c3d70d1a07cf79bf4559285`. Original result source artifact ID: `13390170888`; public artifact ID: `13390655078`.

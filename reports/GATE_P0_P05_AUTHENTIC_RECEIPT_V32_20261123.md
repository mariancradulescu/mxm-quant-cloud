# MXM V3.2 — P0 / P0.5 original authenticated read-only receipt gate

**Evidence:** [Actions #45134137836](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45134137836), original main HEAD 2fceac29455403c0e5597111d5c347bd75dc81ea, 2026-11-23. The run has completed successfully; it is a fresh A-only data collection, NOT an economic model test. This report does not mutate closed studies or their original receipts.

## Ten-line gate decision
1. **NET vs CASH:** UNKNOWN; all-in strategy P&L has not been simulated, 300 EUR is the continuous target, CASH benchmark is 0 EUR.
2. **HARD21:** UNKNOWN, zero evaluated closed funded trades; no qualifying ISO week certified.
3. **Floating drawdown:** UNKNOWN; 30% ceiling remains mandatory, no equity path has been measured.
4. **Data:** 5,343 nonarchived / 1,717 visible symbols, 48 sample markets, 355,449 reported M15–D1 bars; original encrypted hashes match.
5. **Verdict:** P0 read-only source VERIFIED, overall P0 INCOMPLETE; P0.5 full economic qualification INCONCLUSIVE.
6. **Cost blockers:** 48/48 missing all-in EUR cost and executable historical fills, financing, commission/FX/slippage.
7. **Coverage blockers:** 48/48 calendars not reconciled; some rejected/failed history pages; week eligibility UNKNOWN.
8. **Change:** offline public-receipt screen plus synthetic tests only; no C# or secret-bearing workflow changed.
9. **Execution budget:** zero broker calls and zero GitHub workflows dispatched by this report; five broker-free unit tests.
10. **Next:** reconcile Draft PR #423 with current main, complete all-in risk/contract evidence, then run same-Core chronological common-EUR300 economic replay.

## Artifact integrity (source, not economic validation)
- Sealed ciphertext ZIP artifact #14800002000: SHA-256 0dd19ae9f35e3fd9d11355a987f04bcd3d7664964425d1784132c6496a3d18a4.
- Public aggregate ZIP artifact #14799363946: SHA-256 8536052ab5782e107c63caa67a63ddfdec9923efb54a72f44e7925707e9fec3c.
- Public recipient ZIP artifact #14798419417: SHA-256 1fb291c87aed5bb6786dc3e85caf5038ab7def357f25f43e3be1ba8853e4a946.
- All **76 / 76** encrypted payload SHA-256 values match the original receipt (1 roster, 27 contract shards, 48 market shards). This does NOT certify decrypted prices, fills, profitability, or independence. No private ciphertext is committed.

## Source-based economic diagnostic
Authentic source window: [2026-08-24T00:00Z, 2026-11-23T00:00Z), all A/development. B and C are chronologically unavailable as of this report.

- 5,343 nonarchived account symbols, 1,717 visible and inspected contracts; 1,687 current margin observations, 1,660 minimum margins below EUR300. **Minimum margin alone does not prove portfolio fundability or risk acceptance.** Remaining symbols are not excluded.
- 48 markets sampled using original account categories and minimum margin, not favorable P&L; 42 have at least one valid as-of quote pair; **23,363** BID/ASK pairs total. One 0-bps sample requires manual source assessment, not a zero-cost assumption.
- No instrument has certified all-in cost in EUR, NET or financing; quote-age and matched fills remain UNKNOWN.

| Timeframe | Bars reported | Symbols with bars | Failed/rejected pages | Positive-ratio observations | Median sampled spread / median intrabar range at x1.5 | Sample ratios >= 100% |
|---|---:|---:|---:|---:|---:|---:|
| M15 | 191,394 | 46 | 38 | 40 | 55.2050% | 16 |
| M30 | 97,459 | 45 | 29 | 39 | 37.3894% | 14 |
| H1 | 49,867 | 45 | 21 | 39 | 25.7357% | 8 |
| H4 | 13,734 | 45 | 12 | 39 | 13.1847% | 2 |
| D1 | 2,995 | 45 | 12 | 39 | 7.7308% | 0 |

Ratios are limited to strictly positive calculable fixed-clock **spread-only** samples. Median range is an intrabar high/low amplitude, **NOT** a captured trade return. The x1.5 multiplier here adjusts only sampled variable spread; it is NOT the V3.2 fully-loaded x1.5 strategy cost scenario. Do not exclude symbols where this diagnostic exceeds 100% or treat low ratios as evidence of profit. M15–D1 bars overlap across timeframes. Two symbols had no bars at any horizon, but are UNKNOWN, not impossible. All 48 display sessionGapsReconciled=false; therefore HARD21 eligible weeks cannot be certified.

## Official Cloud capability matrix: documentation accepted, no redundant tests
| Need | Official reference | Boundary |
|---|---|---|
| Linux, compile-time and cross-platform dependencies, no HTTP/files | https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/ | Cloud constraints accepted; own binary compliance not proved |
| Multi-symbol closed bars | https://help.ctrader.com/ctrader-algo/references/MarketData/MarketData/ | MarketData.GetBars officially available in Cloud; depth account-specific |
| Bar history | https://help.ctrader.com/ctrader-algo/references/MarketData/Bars/Bars/ | LoadMoreHistory documented; coverage not guaranteed |
| Tick-triggered closed-bar event | https://help.ctrader.com/ctrader-algo/documentation/cbots/cbot-bar-events/ | OnBarClosed follows next tick, not clock alone |
| Volume/estimated margin | https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/ | Broker-specific terms still require authentic observation |
| Position reconciliation | https://help.ctrader.com/ctrader-algo/references/Trading/Positions/Positions/ | Positions.FindAll documented, own code/parity still unverified |
| CLI metadata/backtest | https://help.ctrader.com/ctrader-cli/cbots/ | .NET 8; CLI credentials differ from research OAuth; not Cloud-live evidence |

## Anti-bias, privacy and stopping rules
The existing C# Core/Replay/observation-only Cloud cBot and prior negative results remain unchanged. PR #423 is Draft and must be reconciled before merge; its preregistered B 2026-11-30..2027-05-31 and C 2027-05-31..2027-12-06 periods are future, NOT used for selection. At least 12 genuinely independent months remain mandatory. No order, Cloud Start, token/secret read/change, permanent deletion, source recollection, strategy retuning or re-launch of closed studies is authorized or performed. The existing OAuth trading-scope risk is only software-mitigated, not permission-revoked.

**Reproduce offline:** python -m unittest research.test_p05_receipt_gate ; then python research/p05_receipt_gate.py --public-zip PATH_TO_ORIGINAL_PUBLIC_ZIP --expected-zip-sha256 8536052ab5782e107c63caa67a63ddfdec9923efb54a72f44e7925707e9fec3c [--sealed-zip PATH_TO_ORIGINAL_SEALED_ZIP]. Outputs preserve NET=null, DD=null, HARD21=UNKNOWN. The script and tests do not import or call broker APIs.

> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# MXM economic data development — ex-ante protocol, 2026-11-02

## Fixed intended measurement BEFORE any economic collection

The working repository is **only** `mariancradulescu/mxm-quant-cloud`. This is a new read-only Pepperstone Europe LIVE account research tape using the existing authenticated OAuth, original pinned account identity and already confirmed custody-v2 recipient. No new keys, orders, refresh tokens, account switches, cloud launch, support emails or historical-key repair.

**Fixed account universe, before outcomes:** EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD and XAUUSD, **only when genuinely enabled on the original LIVE account**. Do not replace a missing instrument based on profitability. At least two must be available. This is not a permanent limitation on the final autonomous system.

**Fixed resolution strata:** 370 calendar days of H4 (twelve-month source-coverage attempt with a boundary cushion), 14 days of M15 (shorter-term execution context), plus a single historical one-minute bid and ask quote period for each supported instrument (last completed Friday, 14:00–14:00:59 UTC). Complete-bar timestamps are open+period. Data and broker symbol fields are encrypted **before** upload. A strict per-connection source-request budget and `hasMore` pagination gate prevent undetected truncation. Closed-market gaps are never interpolated.

**Original broker contract:** `ProtoOASymbol` min/step/max volume, lot size, commission type and precise rates/minimums, conversion fee rate, swap directions, swap type/times, leverage ID, trading mode and symbol scale — captured from Pepperstone as protobuf alongside unmodified source replies. These fields are *contract evidence*, not necessarily realizable monetary costs without leverage tiers, currency conversion, bid/ask at the actual execution timestamp, funding intervals and slippage.

## C# economic admission conditions

`FundedBrokerCostScreen` is a **necessary-condition** deterministic EUR 200 risk gate. It never assumes missing entry/exit commissions, slippage, FX conversion or account margin are zero. It requires actual bid+ask, minimum units, quote-to-EUR conversion, financing, commissions, slippage, margin and FX conversion costs **together** before calculating the all-in quote-price break-even move and checking the absolute initial account ceiling and EUR 60 maximum initial-capital drawdown budget. This is not yet the complete path-dependent max-30%-DD certificate or proof of a profitable policy.

`EconomicSourceAdmission` (same native C# core/replay) validates source timestamps and H4/M15 provenance, reports observed distinct month counts, reads broker contracts and measures **only genuinely time-aligned historical bid and ask** spreads. These are liquidity observations, not fills. **NET EUR remains null and no live/Cloud orders are authorized** until actual executable broker conditions, funded policy, full trade costs, independent 12-month chronological confirmation and HARD21 are established.

The prior H1 candidate with negative Brier skill is CLOSED, never reused, reversed or retuned. PRIMARY145 and other previous archives are not new confirmation. Even if this source returns H4 data spanning 12 months, the same historical periods may have been exposed to earlier research; it is **development evidence only**, not independent pristine confirmation. Genuine independent validation must later be frozen before observing its outcomes.

The only authorized workflow trigger is an **exact owner/main change to `ops/economic-request.txt`** with exact subject `MXM_ECONOMIC_SOURCE_ADMISSION` and prior successful secret-free CI. The existing custody-recipient, broker-collection and independent C# custody-readback jobs are reused without rebuilding infrastructure. This record freezes all thresholds and instrument/timeframe choices before viewing research results.

Source quality outcomes are real economic progress; source coverage or a profitable synthetic diagnostic is not evidence of a positive NET trading system.

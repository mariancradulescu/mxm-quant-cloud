# CAC1 — U.S. cash-close benchmark-flow pressure, ETF/index participation

Authority: docs/OWNER_SPEC.md OWNER v2.0 and OWNER 2026-11-14 post-BWR1 decision.
This protocol is frozen on its **own commit before implementation or price/outcome scoring**.
No closed BWR1, ECA1, SRO1, DLR1, RNE1, London-fix, generic momentum or other
exact rule is retuned, inverted, rerun or promoted. The entire 2026 development
calendar is globally exposed, and never independent confirmation.

## Economic mechanism, alternatives and falsification BEFORE outcome access

The original cash-close is a distinct institutional mechanism from the ECA1
09:30 ETF opening-auction disagreement. Benchmark-tracking, dealer hedging,
index futures/ETF rebalancing and market-on-close order preparation can generate
persistent price pressure into the last U.S. cash minutes. We do NOT observe
market-on-close order submissions, imbalance feeds or actual traded volume;
two completed Pepperstone CFD M5 paths are only a *falsifiable proxy*.
The competing explanations are generic intraday momentum (not close-specific),
end-of-day reversal, informative news, tracking discrepancies, CFD quote noise,
and all-in execution costs greater than the effect.

Considered, rejected without scoring: (A) another ECA1 09:30 reversal with
new thresholds; (B) changing BWR1's stopped basis sweep; (C) a generic
unscheduled M5 momentum/indicator sweep. Evaluate the **separate CASH-CLOSE
INFORMATION ARRIVAL** with an ex-ante *midday same-rule negative control* and
funded-cost benchmarks. If the closing window does not have robust incremental
NET EUR over its midday analogue, own-ETF momentum, fixed long, fixed short,
and cash on honest matched denominators, CLOSE exact CAC1. Never add event
thresholds, flip signals, adjust holding horizons, select weekdays or optimize
time clocks after this freeze.

## Frozen 26-week exposed-development experiment

On every Monday–Friday scheduled weekday 2026-05-04..2026-10-30, inclusive
(26 Monday weeks, 130 scheduled weekdays per pair; holidays remain scheduled
and missingness is counted), use the exact pairs
`US500 -> SPY.US` and `NAS100 -> QQQ.US`; EURUSD is solely a USD->EUR
conversion instrument. These five symbols are broker-observed by ECA1/PHX1,
but new intraday closing-time source is needed: prior ECA1 original bars and
ticks cover 09:25..10:40 and cannot certify 13:00 or 15:00 NY trading.
No symbols are substituted after any outcome.

For each market and day, use only 3 **consecutive completed M5 candles**
at 15:15, 15:20 and 15:25 America/New_York; the 15:30 completed information
is known before entry. Define the signed 15-minute move as sign(last
completed close - first candle open) for both ETF and corresponding CFD index.
**CAC1 intent** iff both are nonzero AND exactly the same sign. Enter only
the ETF, in that direction, on executable original ETF bid/ask mark as-of
15:35; exit on original bid/ask as-of 15:55. Never assume an executable
closing auction or use the future 15:35+ candles at decision time. No
intrabar stop or hindsight end condition.

Negative timing control is identically defined on the same instrument at
13:15, 13:20, 13:25 completed M5 and 13:30 decision, using original
13:35->13:55 ETF marks. This is a midday placebo, NOT a second strategy to
promote by inspecting which wins. Paired outcomes are on the common set of
days with all needed feature candles and valid quotes/currency/contract
for both windows; each valid day with no intent is **cash 0 EUR**, but a
missing feature, quote or tariff is UNKNOWN, never 0. Compare per-pair
cumulative and per-common-day current-contract NET EUR, including no-signal
days, by first/last 13 weeks. Do NOT choose the more favorable pair/half.

At 15:35->15:55 on the same complete-day evidence separately score:
(1) CAC1 participation, (2) ETF-only last-15m momentum without the index
agreement condition, (3) unconditional long, (4) unconditional short,
(5) cash. The ETF-only rule is a *benchmark*, NOT a replacement if CAC1
fails. Both midday and close use identical min-unit, costs, and quote
standards; zero signals are legitimate abstentions, not fabricated trips.

## Original read-only acquisition and cost treatment

Use the already installed original Pepperstone EUR LIVE account only through
the official read-only cTrader Open API and existing identity/allowlist guards.
Source original M5 for both indices and both ETFs for fixed windows
13:10..14:00 and 15:10..16:00 NY, all 130 scheduled weekdays. The first
candles must be complete and contiguous; broker trendbar truncation, missing
or wrong response identity are UNKNOWN. For *every* scheduled day (not just
event days) source independently original BID and ASK with as-of <=20 seconds
for SPY.US, QQQ.US, EURUSD at exactly 13:35, 13:55, 15:35, 15:55.
Unresolved `hasMore`, missing/asymmetric/stale/crossed quotes cannot be
substituted by M5 OHLC or historical prices from another provider.
Request time window <=60s, hard ceiling 5,000 authenticated read-only
source requests including required contracts/margins; fail closed if exceeded.

Verify current exact broker contract and quoteAsset, minVolume, step,
two-sided expected minimum margins and deposit asset, commission schedules,
commission minimum, currency conversion, financing/swap cutoffs and session.
Use already tested `current_eur` and `no_swap` finance conversion only
for supported wire format and broker asset; otherwise UNKNOWN. Use actual
original sampled bid/ask, signed EURUSD conversion at entry/exit, commission
and FX tariff plus **modeled 0.5 bps central / 2.0 bps adverse slippage**,
never call them realized fills or 2026 original historical tariffs.
Report both signal count and complete priced calendar, marginal adverse EUR
vs each comparator, all missingness, and separate earliest/latest 13-week
half-samples; current min buy/sell margin only is NOT proof of historic
€300 joint financing or continuous float/DD30.

**Before evaluating any post-entry marks or price results** save the full
original request+response protobuf tape, decoded bars and quotes, symbol
details, contract and margin replies as sealed v2 RSA/AES-GCM ciphertext;
publish SHA-256 fingerprints and aggregate-only receipt. The study uses
the existing custodian, not a new secret, broker or account. No OAuth
reauthorization, no live/demo orders, no Cloud activation.

## Economic stage gate

Reject exact CAC1 if priced adverse NET fails cash or any matched directional
and ETF-only momentum reference, or if the CLOSE-vs-MIDDAY incremental
adverse EUR is not positive and chronologically consistent in BOTH halves.
Inadequate comparable coverage => INSUFFICIENT_ECONOMIC_EVIDENCE,
never a positive admission. Even preliminary success is only exposed
conditional development: no prospectively independent confirmation, no
historical broker tariffs, real fills, native C# shared funded ablation,
12-month certification, continuous adverse DD or HARD21 from this test.
Only credible absolute AND incremental after-cost evidence can justify
further original path collection and a native shared €300 C# replay.
No false claim of qualifying the final bot.

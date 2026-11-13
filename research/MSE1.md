# MSE1 — US-session multi-class funded opportunity and capital competition

Frozen, outcome-blind OWNER v2.0 development protocol, **before this
study's original Pepperstone historical source is acquired or scored**.
No YRC1, JYP1, AEX1, ETP1, SCT1, ESP1, PRR1, OTC1, or OSA1 closed
configuration is retested, inverted, tuned or promoted.

## Why these three target markets (source/cost evidence, not outcomes)

Direction A: US2000 and SpotCrude, authentic prior contract/cost-screened
markets, now with distinct same-session mechanisms below. Direction B:
Coffee, a previously contract/spread-preflighted but not C# financially
traded agricultural CFD. Context US500 and EURUSD is NOT automatically
offered to the selector. Do not infer Coffee affordability from an
illustrative individual EUR238 minimum; its margin is large relative
to common EUR300 and its observed spread-plus-fee hurdle ~16.66 bps
(MEF1 correction, not representative of eight weeks). Do not assume
US2000 or SpotCrude are profitable because their source snapshot
friction ~1.06 / 2.55 bps was smaller. Recheck all contract/tariff,
minimum/step volume, margin, trading mode/short permission, schedule,
weekend/overnight financing and executable paired quotes.

## Original-account source and evaluation chronology

Original Pepperstone bound EUR LIVE account using exclusively allowlisted
cTrader Open API read-only methods and existing OAuth credentials; original
custody v2 encrypted with existing protected custodian public recipient.
Five symbols: mandatory US2000, SpotCrude, US500 and EURUSD; Coffee is
predeclared **optional** if absent, untradable, unaffordable or without
completed M5, with exact exclusion reason rather than substitution.
EURUSD supplies as-of original USD→EUR BID/ASK conversion.
2026-08-31 through 2026-10-26 exclusive, 40 weekdays in eight
**globally exposed development weeks**, historical M5 warmup from
2026-08-28; no independent holdout. Collect M5 bars and original
BID/ASK quote marks at each 5-minute clock +1.5s 14:00..19:55 UTC.
Each side freshness <=30s, ordered original tick history in bounded
30-minute requests, no synthetic/interpolated fills, no request
after original 7000 read-only budget. No universal time or asset blacklist:
the above bounds apply ONLY to this specific hypothesis.

## Freeze: complete entry / sizing / management / exit policies

Decision clocks every 15 minutes 15:00:01.500 through
17:15:01.500 UTC, weekdays, before any source look-ahead. Require
last eight contiguous *completed M15* candles, each of exactly 15
minutes, ending at decision clock minus 1.5s; existing native
entry ATR14 uses fifteen contiguous fully completed M5 bars.

1. **US2000 relative US500 cash-session breadth acceptance (INDEX)**:
   latest four-M15 signed close-to-close H1-equivalent US2000 and
   US500 returns agree and are both nonzero; US2000 latest M15
   close beyond the preceding three M15 high/low in that direction;
   last M15 broker tick-update count > mean of previous three.
   Forecast gross fractional continuation = 0.65 *
   min(abs(US2000 H1),abs(US500 H1)), with no fitted threshold.
   Trade US2000 in the common direction if original economic selector
   proves positive uncertainty-adjusted incremental net utility.
   At modeled fill freeze ATR14, apply entry 1.5 ATR observed-quote
   invalidation, 2 ATR completed-bar Chandelier trail, 135-minute
   protective maximum (not universal profit time). This differs
   from SCT1 prior-day range/overnight gap and PRR1 pullback geometry.

2. **SpotCrude synchronous equity-risk repricing (ENERGY)**:
   latest four-M15 SpotCrude and US500 returns agree; SpotCrude
   latest close outside preceding three M15 high/low in sign,
   and last broker tick-update count strictly exceeds previous-three
   mean. Forecast gross fractional continuation = 0.5 *
   min(abs(SpotCrude H1),abs(US500 H1)). Trade SpotCrude aligned.
   At modeled fill freeze ATR14; observed quote invalidation 1.5 ATR;
   profit lock after 1.25 ATR favorable, then at least +0.35 ATR
   lock or completed-bar 2 ATR trailing, 3 ATR profit target;
   stagnation if <0.5 ATR max favorable after 45 minutes;
   150-minute protective maximum. Reuses a deterministic EXIT
   primitive, not YRC1 market/predictor. This is contemporaneous
   acceptance, not SCT1 delayed shock, OTC1 Brent basis or other
   closed commodity entry.

3. **Coffee agricultural session failed auction (AGRICULTURE)**:
   latest M15 candle price pierces one preceding-three-M15 high/low
   then closes back *within* the violated boundary, with wick in
   failed direction >2 times absolute body and last quote-update
   count strictly > prior-three mean. If wick above, last close
   must be above mean of latest eight completed M15 closes; trade
   down to equilibrium. If wick below, last close must be below
   this mean; trade up. Forecast gross fractional movement =
   abs(last close - eight-M15 mean)/last close, without tuning.
   At modeled fill freeze ATR14 and eight-M15 equilibrium; observed
   quote invalidation 1.5 ATR, actual quote-based equilibrium
   capture, 120-minute *protective* maximum. Source-side missing
   bar/quote, margin, fee or uncertain financing => no Coffee
   position. Different instrument/session/economic premise from
   YRC1's specific NZDJPY fail-auction (no recycled YRC1 result).

No strategy is issued orders and no historical stop/TP is assumed
filled inside an OHLC candle. The model evaluates only observed
original BID/ASK marks, costs in EUR and the native causal exit
reason on each mark. Native C# joint selector sees all three
competing opportunities. Min volume/step, commission, signed FX
conversion, margin and adverse cash drawdown control shared in
ONE EUR300 initial ledger, no per-market wallets, resets or deposits.

## Prespecified comparisons and reporting

Run MSE1_JOINT, MSE1_INDEX, MSE1_OIL, MSE1_COFFEE,
MSE1_LONG, MSE1_SHORT, MSE1_FIXED (actual identical-clock
90-minute exit policy with independently financed one-wallet
ledger, no adaptive leakage) and MSE1_CASH.
Do NOT claim independent improvement from policy comparison if
cash occupancy changes funded entries; report both count and
outcome. Report absolute gross/central/adverse NET EUR and %
of full EUR300, accepted vs rejected proposals and reasons,
funded closes by ISO week, per-family marginal ablations,
true fixed comparator, net vs funded long/short/cash,
cost components, durations, open-risk and adverse sampled
drawdown, quote coverage, missing/equity unknowns, maximum and
EUR-minute margin occupancy, same-account contract provenance
and overall funding. Report annual/monthly extrapolation only
if genuinely supported; never infer material monthly NET from
small samples or artificially force HARD21.

If Coffee cannot pass a complete original economic source and
contract gate, label its family not evaluated (NOT negative) and
evaluate only the frozen source-valid remaining families, without
substituting targets. The exact 8-week MSE1 study is exploratory
development, no promotion without 12+ months relevant evaluation,
independent chronological confirmation, safe continuous floating
drawdown, system-level HARD21, and Cloud restart-equivalence proof.
No LIVE/DEMO orders, activation Cloud for trading, OAuth refresh,
new service, new repo, retuning of closed evidence or disclosure
of original encrypted plaintext.

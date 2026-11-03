# Frozen authentic M15 session-anchor NET evidence — 2026-11-03

## Execution identity / true data
- Frozen completely new `EURUSD_M15_SESSION_ANCHORED_TICK_BALANCE_V1` from [PR #30](https://github.com/mariancradulescu/mxm-quant-cloud/pull/30). Original single Pepperstone Europe LIVE cTrader OAuth SCOPE_VIEW only.
- Authenticated [Actions #41619870283](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41619870283) **SUCCESS**: separate `verify`, recipient, authenticated broker collection and independent `custody` checks SUCCESS.
- 370 calendar days of observed source, **25,132 authentic EURUSD M15 bars**, tick-count measurements (not centralized exchange volume), 778 TRAIN examples, 270 consecutive SELECTION opportunities, ten full predeclared UTC Monday–Friday weeks with zero weeks faithfully included.
- 269/270 individually reconstructed historical BID/ASK entry+exit quote pairs complete. Exactly one pair incomplete; **not imputed**, no missing-price synthetic fill.
- Original encrypted source integrity SHA256 `b45633ea60ec86bef2cf3c7483bd305b3e5ee38d5829965e5163e2b525a626ba`. Encrypted readback and identical replay **`custodyParity=true`**. Original private broker replies remain encrypted, no credentials or raw tick prices released. [Public receipt](AUTHENTIC_M15_ANCHOR_NET_VERDICT_20261103.json), [archived artifact](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41619870283/artifacts/13222304470).

## Causal / actual economics

| Authenticated selection outcome | Result |
|---|---:|
| Forecasted M15 bar-close directional mean across all 270 proposals | **+0.00046198 bps** |
| Fraction of positive directional bar-close returns | 54.0741% |
| Complete entry+exit BID/ASK quote pairs | 269 |
| Missing original event quote pairs | 1 |
| **Quote-complete proposals below frozen TRAIN-derived forecast-cost threshold** | **269/269** |
| Historical quote-funded entries under original policy | **0** |
| Modeled min-volume EUR200 round trips | **0** |
| Scenarios for 0.5x, 1x, 2x spread-based hypothetical slippage | all 0 funded entries |
| Funded modeled EUR PnL / ending balance | 0 EUR / 200 EUR, **because nothing was admitted** |
| Eligible system-level HARD21 weeks | 0/10 modeled qualifying weeks; no actual broker trading |
| DD observed/reported | 0% **for a portfolio with zero positions** — not evidence of real risk protection |
| Last20 chronological confirmation | Untouched/unscored |

**Verdict: `CLOSED_INSUFFICIENT_COST_ADMISSIBLE_EPISODES_NO_RETUNING`.** Distinguish positive-direction fraction above 50% from true economic edge: signed **average** predicted bar-close return across 270 opportunities is essentially zero. Broker quote events authentic, but one missing and all 269 complete are below the cost gate. Consequently *no legitimate funded profit/loss evaluation exists for actual open trades*. The EUR0 result cannot be called break-even trading, nor can the zero drawdown certify the <=30% risk condition. It also cannot prove all session-reversion or all M15 mechanisms fail.

Current broker minimum volume, margin, commission and EUR conversion were available as *current metadata*, not guaranteed historical tariff. The three slip scenarios derive from TRAIN quote **spread**, not observed fill-time slippage. Tick count is not exchange-aggregated trading volume. None of the controls justify LIVE/DEMO orders, Cloud trading, or independent confirmation. Do not loosen admission threshold, reverse directions, retune slots/holding periods, select hindsight survivors or score final20% to rescue this exact closed model. This is a source-supported negative **economic admission** result, not a loss from actual funded trades.

The 270 original 45-minute historical quote event pairs remain a valid **source dataset** for separately preregistered genuinely distinct hypotheses, but the previously seen selection dates and quote outcomes are not fully independent confirmation.

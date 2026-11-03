# Genuine Pepperstone six-hour M15 early-wick strategy: preliminary positive financed quote NET, NOT robust — 2026-11-03

## Source and originality

- Frozen, truly distinct `EURUSD_M15_EARLY_SESSION_WICK_REJECTION_TO_15UTC_V1`, [PR #32](https://github.com/mariancradulescu/mxm-quant-cloud/pull/32). **Causal 06–09 UTC wick-rejection asymmetry, 09–15 UTC historical quote crossing**, not the closed anchor, hourly shock or H4 FX rank.
- Original Pepperstone Europe LIVE cTrader OAuth SCOPE_VIEW original **370-day EURUSD M15 source / 25,132 genuine bars**, original encrypted authenticated quotes from [#41619870283](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41619870283) (source ciphertext SHA256 `b45633ea60ec86bef2cf3c7483bd305b3e5ee38d5829965e5163e2b525a626ba`). Independent original custody SHA/parity SUCCESS. No new broker call, new credentials, other market data or orders.
- Newly scored [#41622017603](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41622017603) **SUCCESS**, protected original custody key required, same SHA verified, double deterministic rerun matched. Public economic [JSON receipt](AUTHENTIC_M15_WICK_SESSION_NET_VERDICT_20261103.json) and [artifact](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41622017603/artifacts/13223638978). Original ciphertext and account details remain unexposed.
- 156 TRAIN examples chronological first60%; 54 predeclared SELECTION days next20%; final20% **NOT evaluated**. All 54 required authentic 09/15 UTC BID+ASK quote pairs available, **0 missing in this model**. The original anchor model had 1 missing event pair elsewhere, which is not imputed. The shared selection calendar was seen in earlier research: **do not call this independent confirmation**.

## Economic evidence — all outcomes and cost assumptions

Original 54 prospective proposals: 22 failed TRAIN-derived forecast-vs-cost admission; 32 reached the single EUR200 historical quote-funded replay at genuine minimum broker units. Zero funding/margin or training-tail stress blocks among 32. Overall directional gross M15 bar-close mean over 54 proposals +4.3293 bps, positive directional fraction 53.70%; this is not an execution profit estimate.

| Hypothetical spread-derived slippage | 0.5x | **1x central** | 2x |
|---|---:|---:|---:|
| Completed modelled round trips | 32 | **32** | 32 |
| Gross profit EUR | +13.5700 | +13.5700 | +13.5700 |
| Genuine BID/ASK spread EUR | -0.1004 | -0.1004 | -0.1004 |
| Current broker tariff commission EUR | -1.6743 | -1.6743 | -1.6743 |
| Hypothetical slippage EUR | -0.4185 | -0.8370 | -1.6740 |
| FX conversion EUR | ~-0.00003 | ~-0.00003 | ~-0.00003 |
| **Conditional modeled NET EUR** | **+11.3768** | **+10.9583** | **+10.1214** |
| Ending simulated equity EUR | 211.3768 | **210.9583** | 210.1214 |
| Sampled quote-mark DD (not continuous) | 3.452% | **3.507%** | 3.619% |
| 10-full-week 2.6-SE conservative lower NET EUR/week | -2.0546 | **-2.0893** | -2.1589 |

The model has **preliminary positive economic performance under all three hypothetical slippage multipliers**, unlike prior exact rejected mechanisms. But the OWNER's robust NET confirmation target is NOT met: the **predeclared lower confidence bound is negative in all scenarios**. In the central scenario, the ten *complete* eligible weeks sum to about **+5.4284 EUR**, with 4 positive weeks, five negative and one zero; the remaining **+5.5299 EUR** arise from the partial-calendar selection boundary excluded from the full-week robustness denominator. It is correct to include all selection trades in full-selection portfolio equity but not to promote partial-week results as additional eligible complete weeks. This calendar-boundary concentration is material. No post hoc removal or alternative week definition is allowed.

### Strict interpretation / decision

**`PRELIMINARY_QUOTE_FINANCED_NET_POSITIVE_BUT_WEEKLY_LOWER_NEGATIVE_NO_PROMOTION`**. This is genuine BID/ASK event-price historical research conditional on **current** authentic Pepperstone broker minimum volume, margin, commission and conversion settings. Commission and spread were explicitly modeled, but historical tariff continuity, historical execution slippage and actual broker fills were **NOT** proven; the 0.5x/1x/2x slippage comes from TRAIN spread, NOT observed fills. Financing 0 modeled under current observed daily swap time outside 09–15, not a certified historical swap schedule.

Historical quote events sample equity ONLY at entry and exit (64 quote marks); **sampled 3.51% DD is NOT a continuous portfolio DD or certified 30%-max drawdown guarantee**. Simulated 32 completed trips on the 10+ partial-week study window yield **0/10 weeks with >=21 modelled trades**; HARD21 remains a **system** obligation and is NOT a per-component veto. No LIVE or DEMO order, Cloud activation or actual funded trade happened. The capital is a research starting balance of **200 EUR** and no real funds were moved.

The exact new candidate has **failed its own precommitted robustness gate** and remains **FROZEN WITHOUT RETUNING, INVERSION, CLOCK/HORIZON/COST-THRESHOLD ADJUSTMENT OR HINDSIGHT HOLDOUT SCORING**. Positive preliminary findings justify prioritizing *genuinely new* systematic investigations and independent future broker evidence, not fabricating an approved tradeable edge or reviving this precise selection configuration. Neither statistical superiority nor independent 12-month profit is demonstrated.

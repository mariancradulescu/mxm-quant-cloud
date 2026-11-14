# CAC1 — authentic original US cash-close ETF price-pressure, exact closure (2026-11-14)

OWNER `docs/OWNER_SPEC.md` v2.0 including 2026-11-14 instructions.
**Verdict: REJECT_EXACT_CAC1_NO_ABSOLUTE_ADVERSE_EUR_NET_OR_EVENT_SPECIFIC_INCREMENT. NO C# PORT, NO TRADING.**
Retain original protocol/source/economic receipt unchanged. CAC1's exact
15:30 completed-bar aligned ETF/index signal, 15:35→15:55 ETF entry/exit,
13:30 midday control and all fixed comparators are CLOSED. Do not
retune clocks, invert directions, drop QQQ, select weekdays or half-periods,
relax quote tolerances or rescue with after-outcome filters. This does not
blacklist US index CFDs or ETFs or bar-based economic discovery.

## Original execution and immutable evidence

- Protocol FIRST standalone freeze commit:
  `b44cc295a707a829c34ce14c560608c1c88d7b9b`, protocol
  SHA256 `144704fe7033ec59fdf871502ab79e5897c47b815ae093e1edab5262e6665eb3`.
- Implemented by PR [#295](https://github.com/mariancradulescu/mxm-quant-cloud/pull/295),
  merge `abf9d5108edd4b8855ad04d478e735fda61cff27`.
- Original protected [run #43578629083](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43578629083):
  SUCCESS; specialized verify, custody and original Pepperstone read-only source jobs all SUCCESS.
  Separate native verify run #43578629057 SUCCESS.
- Encrypted, original captured source:
  [artifact #14108350361](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43578629083/artifacts/14108350361),
  inner `cac1-original-protected.v2.enc`, SHA256
  `7820cf0afe304daeec6387cf1387bda0aeb182faa5e6464db9add0878310cf30`.
  This matches independently downloaded ZIP inner-file bytes.
  Original decrypted plaintext SHA256 reported by protected workflow
  `ee0f2fe170a07e0022bb6312c1650a577d8d36ad3dc5c2fdb6319248f65fe7b2`;
  external reviewers cannot infer decryption proof from ciphertext hash alone.
- Public source/financial receipt:
  [artifact #14107709320](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43578629083/artifacts/14107709320),
  inner `cac1-original-public-economic.json`, exact uncompressed SHA256
  `4a2360268d6cb9747e6e4d2df4efac0c50a165ec93e1ae1745954cb7be5d0fcc`.
- Read-only authenticated original Pepperstone EUR LIVE-account binding reported
  by workflow, **4,173** post-auth original requests, ceiling 5,000.
  Zero orders, no Cloud activation or OAuth reauthorization.
- Original source 26 globally EXPOSED development weeks 2026-05-04..2026-10-30;
  130 scheduled weekdays per ETF, 121 matched financially complete,
  4 missing M5 feature days, 5 missing EURUSD quote-route days each.
  No missing item converted to a zero-return trade.
  Current-contract minimum margins: SPY.US EUR13.69 and QQQ.US EUR12.36
  each direction. These are NOT historically as-of certified margins.

## Current-contract modeled outcome on original BID/ASK + USD/EUR conversion

Figures are cumulative CONDITIONAL EUR at one original current minimum-volume
ETF leg per opportunity, using current contract tariff, original quote-side
entry/exit and FX, and hypothetical 0.5bps central / 2.0bps adverse
additional slippage; they are NOT realized broker fills, historical certified
tariffs, continuous financed book, or independent confirmation.
Policy-specific candidates are descriptive and may overlap: **sums across
the two ETFs are not one jointly funded EUR300 ledger**.

| Metric | SPY.US | QQQ.US |
|---|---:|---:|
| Matched days | 121 | 121 |
| Cash-close aligned signal intents on matched days | 115 | 121 |
| Midday aligned signal intents on matched days | 115 | 119 |
| Cash-close central conditional NET EUR | −3.633898 | −4.313737 |
| Cash-close adverse conditional NET EUR | **−4.771314** | **−5.450132** |
| Midday adverse NET EUR | −5.566424 | −5.629283 |
| ETF-only 15m momentum adverse NET EUR | −4.866401 | −5.450132 |
| Long adverse NET EUR | −6.352975 | −6.652902 |
| Short adverse NET EUR | −5.896786 | −5.519043 |
| Cash adverse NET EUR | 0.000000 | 0.000000 |
| Closing-minus-midday adverse EUR | +0.795110 | +0.179151 |
| Closing-minus-own momentum adverse EUR | +0.095087 | 0.000000 |

Both exact policies lose absolutely despite some positive differences
against *more-negative* alternatives. QQQ cash-close is **identical** to
own ETF momentum on the complete comparator sample, so index agreement
adds no observed selectivity for this measured rule.

Chronological adverse close NET:
- SPY first 13 weeks (59 matched): −2.190496 EUR; last 13 weeks
  (62 matched): −2.580818 EUR.
- QQQ first 13 weeks (59 matched): −2.727046 EUR; last 13 weeks
  (62 matched): −2.723086 EUR.
- QQQ close vs midday adverse increment first half −0.094292 EUR,
  last half +0.273443 EUR; fails chronologic mechanism-specific
  superiority even against the negative midday control.

For descriptive scale ONLY, per-ETF individual conditional central
NET summed −7.947635 EUR and adverse summed −10.221446 EUR.
Do not label those as one financed portfolio or infer real account equity.

## Decision and next economic research boundary

The proposed closing benchmark-flow feature was near-always on; no
credible scarce economic information event or executable positive
absolute NET was shown. Do not launch a variant purely by changing
clocks or signal signs. Existing ECA1, BWR1, CAC1, DLR1, SRO1, RNE1
are independent **closed exact hypotheses only**; their authentic
source archives may support genuinely distinct, prospectively
frozen economic mechanisms. Future selection should explicitly ask
which new *information arrival/market constraint* can plausibly leave
a forecastable residual after actual minimum-unit EUR costs, and
which no-trade/risk controls outperform matched-funded references.

No native C# portfolio admission, no HARD21 credited closures,
no continuous 30% floating DD certificate, no genuinely independent
12+ months, no broker trading activation. Final OWNER objectives
unchanged: EUR300 one native cBot, risk and HARD21 systemic.

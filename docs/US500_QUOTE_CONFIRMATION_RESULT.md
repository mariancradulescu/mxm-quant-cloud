# US500 two-sided quote confirmation

The frozen test used the sealed Pepperstone source from NXE1, with no new
market requests and no replay of the closed NXE1 trade rules. Verified original
ciphertext, receipt and decrypted data matched their commitments. See the
[protocol and earlier evidence comparison](../research/US500_QUOTE_CONFIRMATION.md)
and the [exact aggregate receipt](US500_QUOTE_CONFIRMATION_RESULT.json).

Across 17 exposed weeks, 675 of 680 clocks supported a common comparison.
Two lacked decision evidence and three lacked a complete held path. Two of
the latter would have triggered the two-index filter. All priced policies
use the original US500 minimum of 0.1 unit, delayed entry and a 25-minute
holding horizon, with observed BID/ASK, EUR conversion and modeled slippage.

| Policy | Priced outcomes | Gross EUR | Central EUR | Adverse EUR |
|---|---:|---:|---:|---:|
| Cash | 0 | 0 | 0 | 0 |
| Constant long | 675 | 27.9507 | -10.4743 | -87.3244 |
| Constant short | 675 | -27.9524 | -66.3775 | -143.2277 |
| Bar direction | 670 | 6.8742 | -31.2775 | -107.5809 |
| US500 BID/ASK confirms | 650 | 4.8012 | -32.2179 | -106.2559 |
| US500 and US30 BID/ASK confirm | 493 | 13.8178 | -14.3718 | -70.7510 |

Removing 157 outcomes through the US30 filter improved the common-calendar
gross by EUR9.0166 and adverse by EUR35.5049 versus US500 confirmation alone.
The paired adverse gain was EUR0.05260 per common clock, descriptive 95%
four-week block interval EUR0.03777 to EUR0.07151. The filtered absolute
adverse mean remained EUR-0.10482 per clock, interval EUR-0.14021 to EUR-0.06882,
and the two segments lost EUR25.20 and EUR45.55 adverse. Gross averaged
EUR0.02803 per priced outcome against EUR0.05718 central friction. The
adverse scenario added EUR0.11436 per outcome. The costs exceeded captured
movement even in the central scenario. The frozen screen failed.

The filter generated 24–38 priced outcomes per week (median 28). The
adverse fifth percentile was EUR-1.5385 and the worst sampled mark while
holding was EUR-5.6270 per minimum-size position. This is a position-level
markout metric. The authenticated minimum-margin observation at collection
was EUR34.29, approximately 11.4% of EUR300. This report has zero funded
round trips, no funded portfolio NET or HARD21 proof and no measurement of
continuous floating drawdown. A future candidate would need separately
supported as-of contracts, monitoring and funding, a common-ledger risk
evaluation and independent forward data. No pricing or confirmation work
is warranted for this exact policy.

The evidence advances a narrower decision. Cross-index quote agreement
identified relatively better opportunities on this tape, while the
estimated magnitude was too small to cross the spread at this horizon.
The comparator with the strongest gross was constant long, which also lost
after cost. Prioritize economic magnitude and friction attribution before
more fine-grained prediction or a new collection for this mechanism.

[Protected execution #43388603986](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43388603986) ·
[Original aggregate artifact #14019403245](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43388603986/artifacts/14019403245) ·
[Original encrypted source #14015883688](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43377275493/artifacts/14015883688).
ZIP SHA-256: `4559a2377e77dcd50c0d8a7829cec706f37fdea7c4835529bcfe20a4ea411344`.
Receipt SHA-256: `2e6bdda512825ae7f5ac4c22be7a9e7b8e3cda62d4aa70b3692f25ff9aa92127`.

# US500 opening anchor reclaim — exposed EUR result

The [frozen protocol](../research/US500_OPENING_ANCHOR_RECLAIM.md) was executed
once using the original sealed NXE1 archive. The protected run verified the
original ciphertext, plaintext and public source receipt commitments. It
published the [aggregate receipt](US500_OPENING_ANCHOR_RECLAIM_RESULT.json).

Of 255 scheduled clocks across 17 weeks, three lacked decision history.
The rule produced three intents on the remaining 252 clocks. All three
had complete five-minute holding marks and signed EUR conversion for
the 60-minute hold. Activity was one observation in each of three weeks
and zero in the other 14. Minimum US500 volume was 0.1 units. Median entry
notional was EUR677.90 on the credit conversion basis, and the archived
minimum margin observation was EUR34.29 in both directions. The margin
and contract snapshot postdates the decision clocks.

| Matched policy | Gross EUR | Central EUR | Adverse EUR |
|---|---:|---:|---:|
| Opening reclaim | -1.0200 | -1.1779 | -1.4935 |
| Own 30-minute momentum | -1.0200 | -1.1779 | -1.4935 |
| Long | -0.1229 | -0.2808 | -0.5964 |
| Short | +0.1229 | -0.0349 | -0.3506 |
| Cash | 0 | 0 | 0 |

Own momentum chose the same side at each selected clock. The observed
increment on those clocks is zero. The first eight and last nine weeks
lost EUR0.9782 and EUR0.5153 adverse respectively. Median favorable and
adverse sampled gross excursions were +EUR0.7296 and -EUR0.8237.
The worst sampled adverse liquidation markout was -EUR1.1609 on a
single position. This is a sampled conditional result under the declared
spread and slippage stress, without a certified continuous risk bound.

The exact rule failed the frozen screen and is closed. Three observations
support neither an estimate of stable edge nor a conclusion about the
whole class of opening-anchor mechanisms. The sparse rule also supplies
little candidate frequency for a common portfolio. No funded round trips
or funded EUR NET, no independent confirmation, broker calls, orders or
Cloud activation. Existing C# as-of admission remains the relevant path
for any future candidate with sufficient evidence.

[Protected run 43402500308](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43402500308) ·
[Original result artifact 14025976234](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43402500308/artifacts/14025976234) ·
[Original encrypted source 14015883688](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43377275493/artifacts/14015883688).

Original result archive SHA-256:
`818480a2062f17a1cce81b5d390a639cfe0ab6c48fb01102c68009a901108c16`.

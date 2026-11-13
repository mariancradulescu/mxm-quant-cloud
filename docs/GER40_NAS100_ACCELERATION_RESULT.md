# GER40/NAS100 acceleration transmission — result

The [frozen protocol](../research/GER40_NAS100_ACCELERATION.md) ran on
original Pepperstone data, 2026-08-17 to 2026-11-09 exclusive, in 12 exposed
weeks. The existing read-only adapter made 3,145 post-authentication requests.
It obtained 47,986 bars and 17,203 sampled paired marks across GER40, NAS100
and EURUSD. No optional symbol was excluded.

| Target / policy | Gross EUR | Central EUR | Adverse EUR |
|---|---:|---:|---:|
| GER40 / peer acceleration | +0.92 | -38.77 | -118.15 |
| GER40 / own acceleration | +45.08 | +5.39 | -73.99 |
| GER40 / own momentum | -26.96 | -66.65 | -146.03 |
| GER40 / long | -42.19 | -81.88 | -161.26 |
| GER40 / short | +42.19 | +2.50 | -76.88 |
| NAS100 / peer acceleration | -91.47 | -134.41 | -220.30 |
| NAS100 / own acceleration | +92.05 | +49.11 | -36.78 |
| NAS100 / own momentum | +15.72 | -27.22 | -113.11 |
| NAS100 / long | -37.43 | -80.37 | -166.27 |
| NAS100 / short | +37.43 | -5.52 | -91.41 |
| Cash | 0 | 0 | 0 |

From 300 scheduled clocks per target, one missed decision information.
GER40 lacked six future holding paths and priced 293 observations.
NAS100 lacked three and priced 296. Each target priced 23–25 peer
observations weekly at a 45-minute hold. First and second six-week
peer adverse totals were -130.65 and +12.50 EUR for GER40 and -124.67
and -95.64 EUR for NAS100. Descriptive 95% circular three-week block
intervals for the peer adverse increment over own acceleration were
[-0.905, +0.459] and [-1.287, +0.042] EUR per priced clock. Targets share
the same markets and dates. Both exact peer rules fail the frozen screen.

At 0.1 units, median nominal was EUR2,558.58 and EUR2,587.12. Original
minimum margin observed at collection was EUR134.00 and EUR127.70
(maximum of both directions), EUR261.70 combined. The source records
299 coincident intents, leaving EUR38.30 before floating losses and
costs at static EUR300 if both minima were reserved. Worst sampled
adverse single-position markouts were -17.58 and -37.40 EUR. These
markouts are not a joint drawdown estimate. Later contract terms price
conditional historical scenarios. Commission and conversion fee were zero
in these observations. The recorded rollover fell outside the included
holds. The adverse spread/slippage scenario is a modeled stress.

No funded positions, no joint EUR NET, no HARD21 or independent
confirmation. The positive central own-acceleration references have
negative adverse totals and do not qualify. The US500 reclaim comparison
in PR #267 established identical directions at its three selected clocks;
it did not test equivalence of the timing policies.

[Protected run 43404751751](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43404751751) ·
[Original aggregate 14027072558](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43404751751/artifacts/14027072558) ·
[Encrypted source 14026439419](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43404751751/artifacts/14026439419) ·
[Byte-identical JSON](GER40_NAS100_ACCELERATION_RESULT.json).

Aggregate ZIP SHA-256 `0a8810084d9d9946956a74d1f48eb35171a4a408a24207f207beefe85347e5ad`.
Aggregate JSON SHA-256 `fefac6217a057dd746d675eeef421ae06f78507b881ce6585c1e78c601f07e6b`.

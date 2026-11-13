# NOKJPY and oil transmission — development result

The frozen comparison used 228,061 original M5 bars for NOKJPY, SEKJPY and
WTOIL-PERP from the existing selected development bundle. Account commitment
and series checksums matched. The code trained on 777 initial slots and
scored 1,232 subsequent slots across 31 full weeks. Eight of 1,240 slots had
incomplete source. The median was 40 eligible clocks a week. These are
opportunities for observation, with a 60-minute label from the next M5
close. No funded round trips were made.

| Comparison | Without oil | With oil |
|---|---:|---:|
| Out-of-week MSE, bps² | 259.9616 | 260.5716 |
| Mean directional gross, bps per slot | -0.8321 | -0.7984 |

Matched constant long was +0.0577 bps, short -0.0577 bps, and cash zero.
Adding oil improved directional gross by 0.0336 bps versus the matched model
without oil (95% moving-block interval -0.8793 to +0.8664), while making
MSE 0.6101 bps² worse. The lower fifth percentile of modeled bar-based
outcomes was -24.0229 bps. The directional policy lost money before costs.
The frozen incremental screen failed. No additional broker collection is
justified for this exact policy.

The historical NOKJPY margin probe estimated EUR4.61. It does not establish
admission at the study clocks. The archive has no synchronized executable
BID/ASK, applicable tariff, or decision-time margin and financing trail for
this target. Central/adverse NET, common-book margin usage and floating
drawdown therefore remain unevaluated for the pilot. All dates are exposed
development. No independent confirmation, orders or Cloud activation.

## Existing evidence informing the decision

- NXE1 [original receipt](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43377275493/artifacts/14016671008)
  and [encrypted source](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43377275493/artifacts/14015883688)
  remain frozen. The native receipt logged 1,159 rejections as
  SESSION_MARGINAL_ADVERSE_LOSS_UNDERSTATED. The source separately lacks
  historical as-of schedules, which would still prevent strict admission.
  The diagnostic found 1,139 complete hypothetical labels and zero positive
  prequential NET forecasts. The reported +EUR0.1329 mean actual adverse
  value is for the scored overlapping subset; no positive forecast selected
  it. A pooled realized average cannot establish a selective policy's value.
- MSE1's quote and conversion gaps showed that observed decision clocks
  alone cannot establish a fully priced holding path. The NOKJPY pilot
  requires a contiguous bar path for each label and leaves execution and
  portfolio risk unevaluated at this stage. NXE1's existing admission gate
  is unaffected.

Protocol: [NOK_OIL_INCREMENTAL.md](../research/NOK_OIL_INCREMENTAL.md).
Reproduction (Python 3.12 with NumPy 2.3.5):

```sh
python research/nok_oil_incremental.py /path/to/original.zip /tmp/nok-oil-result.json
```

The [public aggregate receipt](NOK_OIL_INCREMENTAL_RESULT.json) includes
source hashes, the calendar and benchmark statistics.

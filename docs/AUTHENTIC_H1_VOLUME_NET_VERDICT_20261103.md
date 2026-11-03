# Frozen authentic H1 volume-dislocation quote NET — 2026-11-03

## Custody and provenance
- Frozen new hypothesis `EURUSD_H1_TICK_VOLUME_PRICE_DISLOCATION_V1`, PR #26, NOT a relaunch of any prior closed model.
- Original pinned Pepperstone Europe LIVE, SCOPE_VIEW read-only, 370 days, 6,283 true broker H1 bars and tick volume.
- GitHub Actions [#41614667957](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41614667957) **SUCCESS**, including `verify`, `custody_recipient`, `collect`, `custody`. Raw event quote data and source encrypted; public result only [artifact](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41614667957/artifacts/13220957636).
- Original source ciphertext SHA256 `7037ea5dc6e4eccc4905baf38028ecec01f22bc9c0a938425e2e6d85cc9e635a`, independently decrypted and replayed in custody: `custodyParity=true`. Public full receipt [JSON](AUTHENTIC_H1_VOLUME_NET_VERDICT_20261103.json); no account identifiers, credentials or raw prices in repository.
- Zero submitted LIVE/DEMO orders; single Cloud cBot remains observation-only.

## Empirical selection, not independent confirmation
| Quantity | Genuine result |
|---|---:|
| Original EURUSD H1 coverage | 6,283 bars / 370 days |
| Train examples, chronological first60% | 540 |
| Selection opportunities, chronological next20% | 216 |
| Entry+exit BID/ASK historical quote pairs complete | 216/216 |
| Price-only next-2H BID-close directional mean, all proposals | **-0.41765887 bps** |
| Positive price-only directional fraction | **49.074074%** |
| Rejected by TRAIN-calibrated forecast/cost condition | **207** |
| Rejected for missing event BID/ASK | **0** |
| Rejected by training-tail DD stress within 9 cost-admissible | **0** |
| Broker funding rejected at minimum volume among admitted | **0** |
| Completed modeled EUR200 round trips | **9** |
| Eligible complete Monday–Friday selection weeks | **10** |
| Weeks with >=21 modeled round trips | **0/10** |
| Independent final20 confirmation scored | **NO** |

### Cost decomposition on the SINGLE EUR200, min-volume, non-overlapping model
| Scenario | Gross EUR | Spread EUR | Commissions EUR | Slippage hypothesis EUR | FX conversion EUR | NET EUR | Ending EUR | Sampled DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 0.5x | -2.7140 | 0.0303 | 0.4689 | 0.1172 | ~0.000008 | **-3.3305** | 196.6695 | 2.6570% |
| 1x | -2.7140 | 0.0303 | 0.4689 | 0.2344 | ~0.000008 | **-3.4477** | 196.5523 | 2.7028% |
| 2x | -2.7140 | 0.0303 | 0.4689 | 0.4689 | ~0.000008 | **-3.6822** | 196.3178 | 2.7945% |

Financial results are **current authenticated broker cost metadata + authentic historical entry/exit BID/ASK + hypothetical slippage**. No REAL FILLS, no historical fee/swap/leverage schedule certification, no broker order acceptance and no continuous intra-horizon equity observation. No actual HARD21 or independently confirmed NET edge follows; `historicCostSchedulesProven=false`, `realFills=false`, `globalDrawdownCertified=false`, `economic_qualification=false`. The broker's currently observed DAILY swap schedule is outside same-weekday intended holding windows, so modeled carry=0 under **current schedule only**; historic carry is not proven. The observed-quote DD is NOT a 30% DD guarantee. System-level HARD21 is not assigned as a universal per-component quota.

**Material scientific qualification of slippage naming:** source implementation `trainSlippagePrice` was numerically derived from **one half of the maximum of eight TRAIN reconstructed quote spreads, with a broker-point floor**. Thus it is a **spread-derived hypothetical slippage proxy**, **NOT** observed same-side quote motion, actual fills or a calibrated execution-latency loss distribution. Historical spread itself is measured at the requested actual quote events. The 0.5/1/2 sensitivity comparisons are purely assumptions and should never be called measured slippage or a robust execution guarantee. This clarification changes NO evaluated parameters or figures.

## Verdict and economic interpretation
**`CLOSED_NO_GROSS_OR_FINANCED_NET_SUPPORT_NO_RETUNING`.** Both the broad 216-proposal BID-close directional mean and the 9 cost-admitted executed-side quote-proxy gross are negative. No positive economic selection survives, so the exact coefficients, features, hours, holding period and thresholds are CLOSED with no direction reversal, coefficient retune, survivor subset, re-priced holdout, or cost-scenario selection. The result does not prove that all volume-based forecasts or other economic families are unprofitable.

The 207 filter blocks are not broker funding failures: they are forecast-vs-TRAIN cost-screen decisions. Whether those 207 are economically attractive in a frozen quote-crossing counterfactual is a separate non-promotional research question, NOT permission to relax the closed policy or claim independent confirmation. Absolute 30% DD, actual financing and a 12-month qualified funded performance series remain unproven.

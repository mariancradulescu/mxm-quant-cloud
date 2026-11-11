# JRS1 · Relative rotation and commodity-specific repricing with joint stress

Freeze before opening the input for this study. Reuse the exact encrypted
Pepperstone tape archived by FCE1 run 43036474843, artifact 13863803890.
The six weeks 2026-02-09 to 2026-03-20 are exposed development. FCE1's
original strategy, results, and receipt are closed. The existing M5
history supplies contiguous M15 features. Original minute BID/ASK and
EURUSD conversion supply costs, execution and equity. No new broker
requests. One continuous EUR300 modeled ledger per policy.

## Predictions

Scan 15:30–17:30 UTC every 30 minutes, at 1.5 seconds after a closed bar.

- **AUDUSD/NZDUSD regional rotation.** Compare their latest two-hour
  returns from synchronized M15 closes. When the pairs move in opposite
  directions, relative repricing can persist beyond a shared USD shock.
  Require the absolute relative return to exceed both the mean of the
  eight prior absolute M15 return differentials and the absolute
  simultaneous EURUSD two-hour return. Select the pair with larger
  absolute two-hour return, in its own direction, with its last M15
  change confirming. Ties abstain. The projected gross return is the
  smaller of the selected pair's absolute return and half the relative
  displacement. Use M15 prediction invalidation, ATR protection, and a
  75-minute safety cap.
- **Commodity-specific repricing.** XAUUSD and SpotBrent are distinct
  markets. A target's price impulse on rising local quote activity can
  persist when the other commodity and EURUSD remain within their own
  recent hourly return ranges. Measure latest hourly return and the
  mean absolute return of the preceding two non-overlapping hours from
  contiguous M15 closes. Require target move over twice its baseline,
  each context move at most its own baseline, target final M15 aligned,
  and target recent hourly tick count greater than both prior hours.
  Use half the target absolute return as exploratory gross magnitude.
  Use M5 ATR Chandelier and initial volatility protection, with a
  75-minute safety cap. Tick volume measures broker updates.

## Joint risk and financed comparisons

For each decision, construct eight synchronized, non-overlapping
15-minute blocks of completed M5 history ending at the feature clock.
Replay each asset's same-block directional move and EURUSD conversion
shock against current holdings, open intents and candidate units.
Terminal EUR scenarios use signed price changes and credit/debit FX.
Use each block's adverse and favorable extremes with a conservative FX
bound. Portfolio loss and favorable peak add their per-leg bounds,
without assuming that the extremes occurred at the same instant. Add
a conservative execution/ATR loss floor to candidate stress. Center
candidate terminal shocks across blocks before adding the conditional
gross-cost estimate, so recent signed drift is not counted twice.
Missing or noncontiguous histories stay unknown. The blocks are
deterministic stress inputs, with equal objective weights and no
claim of statistical independence, confidence interval, or tail
calibration. Use the existing common selector, ledger and drawdown
limit. Use contract minimum volume in every book to focus this test on
prediction and joint risk.

Compare both family ablations, funded long and short on the same
opportunity definitions, cash, and a control with the same forecasts
and minimum units but legacy repeated stresses. Compare central and
adverse closed NET, capital overlap, weekly round trips, and held-minute
coverage. Compare supported adverse results against cash and the best
funded direction. Exposed results alone cannot qualify a configuration.
No orders, Cloud activation, or standalone live data access.

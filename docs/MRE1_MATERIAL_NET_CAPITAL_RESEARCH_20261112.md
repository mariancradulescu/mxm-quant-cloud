# MRE1 — EUR300 material-NET return and capital-efficiency readback

**Performed 12 November 2026.** This economic calculation was executed
locally on the **original unchanged** public SEM1/ESD1 C# benchmark correction
from [Actions run #43214539052](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43214539052),
original artifact **13943645086**; exact public JSON SHA-256
`44ca3cf8c2aeff9c46f47e7b0368af4b860ffc34c97459d3545a50655cf8309b`.
The original SEM1 account/source run is #43207629492. A source-hash-locked
fully reproducible calculation is in `research/mre1_funded_materiality.py`.
No closed research was repeated, no returns were selected as winners, and no
new original broker request, signal, ledger run or order was performed.

This is a **new economic measurement of the existing financed portfolios**,
**not** a new predictive mechanism or independent confirmation.
Causal 90-minute books and their same-start EUR300 separately funded controls
have no unresolved exits. The 30-minute causal books do.

## 90-minute complete causal common-book results

| C# policy | Closed round trips | Central NET EUR | Adverse NET EUR | Adverse return on initial EUR300 | Max sampled used margin EUR (% of initial) | Maximum sampled adverse DD | Max weekly closes in sampled calendar |
|---|---:|---:|---:|---:|---:|---:|---:|
| Filtered | 50 | -22.07398 | -42.73847 | -14.25% | 230.42 (76.81%) | 18.69% | 9 |
| Momentum | 206 | -43.67368 | -63.41558 | -21.14% | 136.11 (45.37%) | 24.85% | 23 |
| Long, independently funded control | 207 | +36.59487 | +16.79476 | +5.60% | 136.11 (45.37%) | 12.92% | 23 |
| Short, independently funded control | 126 adverse | -74.92300 central | -75.38055 | -25.13% | 136.11 (45.37%) | 29.97% | 23 |
| Cash | 0 | 0 | 0 | 0% | 0 (0%) | 0% | 0 |

Central and adverse can finance different positions; therefore the short
central count is not necessarily 126 (adverse count shown).
Peak used margin is taken from the original modeled native ledger, not a
perpetual cap. All results are modeled, not real broker fills.
**The 90m filtered book lost 59.53323 EUR more than the long funded control
and 42.73847 EUR more than cash** in the adverse case.
A baseline positive result does not permit retrospectively switching
to the long strategy or promoting it. Filtered risk-return-to-sampled-DD is
-0.76 (ratio of return to sampled maximum drawdown); long +0.43 on its own
different exposure. Neither certifies future risk.

## 30-minute source-coverage dependence

The **causal** filtered adverse scenario has eight known closed trips,
+11.49355 EUR closed NET fragments, **one open ETHEUR position** and a
fixed exit without authentic BID/ASK. Portfolio NET, total return on EUR300,
full outcome and capital efficiency must be **NULL**, not +3.83%.
The causal momentum, long and short books also contain unresolved exposure.
The separate complete-endpoint sensitivity is **post hoc conditioned** on
future availability, not a causal replacement: filtered adverse -5.74677 EUR
(-1.92% on initial EUR300) for 50 closed trips.

## Materiality and selection diagnostics

A material economic programme should demand **absolute**, costed,
capital-denominated returns and compare those to sampled/continuous equity
drawdown, peak used margin, actual opportunity coverage, independently funded
cash/long/short controls and equivalent frequency/participation baselines.
The current 90m filtered book fails even the necessary condition of positive
absolute NET, with 76.81% sampled capital tied in used margin. Its apparent
increment versus more-active momentum is not proof of independent directional
selection; the long benchmark is both profitable and differently exposed.
The filtered book reaches **only nine** closed trips in its most active sampled
week, and the 10-week panel is not a continuous calendar; HARD21 is not proved.
A long control showing a weekly maximum of 23 does not establish 21 completed
financed trades in each prospectively eligible week.

The next **new** economic mechanism must be separately frozen before
evaluation, with original-account causal source access where legitimately
available, sufficient opportunity density and C# common-ledger contribution;
neither this materiality readback nor the unresolved SEM1 exit confers
qualification. The separately blocked attempt to create a protected source
recovery workflow is not repeated or routed through another mechanism.

No claimed 12-month qualification, no continuous equity drawdown certificate,
no independent holdout, no Cloud operational parity, no orders.

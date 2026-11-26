# Verified integration, financial recovery and common-book research — 26 November 2026

PRs [520](https://github.com/mariancradulescu/mxm-quant-cloud/pull/520) and [521](https://github.com/mariancradulescu/mxm-quant-cloud/pull/521) were integrated successively without a conflict. Main after integration: `2cc617c896c8c561476878e8a54ecf16ebff41ad`.

## Frozen AAPL.US financial recovery

[Run 45870893197](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45870893197) succeeded. Artifact 15143151757 was downloaded and SHA-256 verified: `e45cfd0d6e3cee9f7327476c7b9da33b65707d5ecc62b25481a311cd70be4923`. Exact-readback authenticated two targeted requests. All 37 frozen books are conditionally reconciled; original FX was reused. The immutable receipt is conserved in `research/aapl_frozen_funding_recovery_1_verified_receipt.json`.

Original PAV1 MT25_H1_24 S0 frozen closed NET is +4.414788 EUR. The 36 paired books now have known closed NET. Together with the six already reconciled PAV1 variants, the paired study contains 15 positive and 27 negative outcomes, plus three CASH controls. These are exposed development outcomes with projected archived tariffs, not broker settlements or economic qualification.

| Family and management | S0 closed NET EUR | S1 closed NET EUR | S2 closed NET EUR |
|---|---:|---:|---:|
| EQUILIBRIUM_REVERSION__TRANSITION_VALUE | +3.043161 | -6.307131 | -13.182304 |
| EQUILIBRIUM_REVERSION__MONETARY_REDUCE | +2.335541 | -6.884533 | -12.168892 |
| INTERMARKET_DISLOCATION__TRANSITION_VALUE | -6.613898 | -12.894622 | -15.621456 |
| INTERMARKET_DISLOCATION__MONETARY_REDUCE | -11.178721 | -17.579092 | -20.120176 |
| M5_FOLLOW__TRANSITION_VALUE | -8.366005 | -9.444252 | -17.743621 |
| M5_FOLLOW__MONETARY_REDUCE | -2.976590 | -7.507696 | -19.432143 |
| M5_REVERSE__TRANSITION_VALUE | -16.009984 | -29.625631 | -37.562516 |
| M5_REVERSE__MONETARY_REDUCE | -9.393463 | -18.532717 | -36.670099 |
| PAV1_LOCAL_TRANSITION__TRANSITION_VALUE | +48.791537 | +40.759733 | +23.673479 |
| PAV1_LOCAL_TRANSITION__MONETARY_REDUCE | -10.640307 | +41.781347 | +29.130759 |
| RANGE_CONTINUATION__TRANSITION_VALUE | +10.757207 | -40.219154 | -37.917238 |
| RANGE_CONTINUATION__MONETARY_REDUCE | +4.228672 | -44.728531 | -42.194218 |
| V33_MULTISCALE_ACTIVITY__TRANSITION_VALUE | +9.950094 | +6.059485 | +4.413022 |
| V33_MULTISCALE_ACTIVITY__MONETARY_REDUCE | +23.508407 | +20.317852 | +19.964767 |

The 36 affected books had already blocked further admissions because of an unbounded AAPL liability. Settlement changes the financial interpretation of executed trades; it neither inserts absent later trades nor restores historic equity. Only PAV1 had system HARD21 in the paired study. V33's positive frozen NET merits new shared-book investigation despite its individual frequency failure. Portfolio complementarity cannot be inferred by summing separate EUR300 books or treating admission-blocked later weeks as freely available family opportunity.

## New common-book competition

[Run 45870950688](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45870950688) succeeded with 9/9 evaluations. Artifact 15144090063 was independently downloaded and verified: `5eaa9a21d286c26220233a6cbfc5f3fc93d5f109c0047000b68965aa74f03824`. New books were sealed in artifact 15144165166, GitHub archive digest `cbe1dc3ef7ad9c03a195e8e6d389661441bd35b91e7161384f86d7429209596a` (digest reported by GitHub; not independently downloaded here).

Both management variants closed six RANGE_CONTINUATION trades in S0 for +3.549007 EUR and sampled DD 1.8310%. Neither traded in S1/S2. There were no unresolved funding windows in these nine books. All variants fail system HARD21 and selection is WAIT. Hourly observers produced 3,886 / 3,783 / 3,712 matured labels per management. Minimum-volume observations yield identical results for these managers and insufficient admitted recurrence. The follow-up therefore compares affordable evidenced observation volumes and matched causal management selection without lowering risk gates or forcing entries.

## Source, exposure and confirmation

The normalized 25-market source and four authentic annual contexts were reused. Four added markets do not supply a year of monetary execution. The exact exposed source span, calendars and marks remain in the pinned receipts. No twelve-month independent common-book confirmation is certified. Expanded normalized sources and separate observer/book checkpoints are now an explicit reusable output of the next registered study, avoiding raw packet reconstruction in follow-ups.

Original data and results are unchanged. Policy reruns of closed studies, orders, Cloud activations and economic promotions remain zero.

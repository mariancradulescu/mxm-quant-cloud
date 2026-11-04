# Native open-equity integration and CCP1 financial preflight

Authority remains [OWNER_SPEC.md](OWNER_SPEC.md) v2.0. PR50 preserves PR49 and all
closed studies. No orders, Cloud activation or new runtime service occurred.

## Economic evidence actually executed

Authenticated run41774823771 made39 read-only source requests on the original
Pepperstone EUR account: nine FX contracts, queried minimum-volume grids and one
predeclared completed quote window. Raw encrypted sources were reconstructed in
the existing custody job. Source artifact13296372221 expires2027-02-02T04:42:33Z;
its envelope hash and the preregistered protocol hash are in
`CCP1_AUTHENTIC_PREFLIGHT.json`. No annual bars or return labels were collected.

The economic premise was an ordinary financing cashflow discrepancy across a
partially currency-matched three-leg FX basket. Four fixed triangles (EUR, GBP,
AUD, NZD against USD/JPY), both orientations and queried1..6 minimum-volume grids
produce86 rows. All are retained.24 rows pass the CONDITIONAL current-capital
screen (queried directional margin plus declared round-trip cost belowEUR200).
Every86 row has negative raw financing; on the24 capacity rows the range is
EUR-0.2189817687 to-0.0460328134 per ordinary unmultiplied charge before trading
costs. Adverse per-leg rounding givesEUR-0.23 to-0.07. Modeled round-trip costs
areEUR0.4068153081 to1.1383480372 and queried marginsEUR79.40 to192.62 on those rows.

The exact current-term three-leg profile is CLOSED without retuning, inversion,
favorable subset promotion or annual expansion. The observed terms do not support
its carry-only premise. This is an informative funding/capacity rejection, NOT
traded/historical/future NET, predictive alpha, marginal allocation value or a
proof of system infeasibility. No candidate is promoted and no funded replay is
fabricated.1/3/5 charge flat-basis arithmetic is explicitly counterfactual, not
calendar performance. Current terms were observed AFTER the past quote context;
they were not information available at that historical quote clock.

Do not generalize the rejection beyond the fixed profile. Cross-basket netting
could change volumes, financing and costs and was NOT evaluated; negative
standalone baskets do not prove every common allocation uneconomic. Currency lot
residuals remain reported rather than assumed hedged. Price/basis risk, changing
rates, simultaneous execution/liquidity, actual financing, joint broker margin
and independent predictive evidence remain missing. No full study is admitted.

## Native functionality actually verified

`NativeFundedSession` now owns the common monetary book AND a separate portfolio
observation state. The observation-only cBot supplies platform equity/margin,
position quantities and net PNL, checks cash+credit+PNL against equity and equity
against free+used margin, and retains the sampled observed peak in its versioned
checkpoint. The second inventory read compares immutable captured quantities,
not mutable platform position references; a detected partial-volume change
invalidates the mark. Platform decline warnings explicitly retain unknown
cashflow history; raw account equity is not certified cashflow-adjusted drawdown.
It emits suspension/reduction review, never order requests. Unknown
extra exit costs mean UNKNOWN conditional liquidation equity; no stopout threshold
is assumed. Monetary reconstruction alone cannot manufacture a floating path.

CI41774577191 passed native checks, immutable holding-mark receipt, existing money
regression and `.algo` compilation.128 observations comprise four explicit modeled
initial states and124 frozen SQP1 holding marks. Both nonempty scenarios match
original sampled drawdown within1e-18:3.4435903194% and3.5230258565%. Every mark's
checkpoint restoration and duplicate observation preserve the result. Two cases
without holding marks report null drawdown, not a measured zero. No SQP1 forecast,
allocator, exit policy, trade or NET was rerun/changed. The full technical receipt
is `NATIVE_HOLDING_OBSERVATION_RECEIPT.json`.

This verifies conditional modeled holding observations and state restoration,
not authentic nonempty broker risk recovery. The adapter is compiled, not deployed.
A sampled observed peak is not the lifetime supremum; gaps, missed intramark peaks,
unknown exit liquidity/costs and cashflow effects cannot certify continuous30%
drawdown or actual liquidation. Hash-bound local checkpoints do not prove Cloud
durability and do not replace encrypted source custody.

## Remaining acceptance gaps

No new financed NET or round trips: HARD21, marginal portfolio benefit, representative
simultaneous finance, robust economic advantage and untouched chronological
confirmation remain unproved. Twelve months of authentic relevant performance are
still absent. Current empty broker evidence cannot demonstrate recovery of filled
trades or full monetary history. Cloud persistence/runtime and Android acceptance
need separate activation authorization; orders are not requested to manufacture
missing evidence. Requirements and the singleEUR200 capital remain unchanged.

Architecture and active implementation status now distinguish the historical
Python ledger from the native monetary/risk kernels; this corrects stale status
statements without rewriting the historical studies or claiming full equivalence.

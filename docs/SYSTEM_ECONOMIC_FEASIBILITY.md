# Economic feasibility decision after PR50

Authority: [OWNER_SPEC.md](OWNER_SPEC.md), OWNER v2.0, with the explicit OWNER
continuation after PR50. Reconciled main was
`0e956c409ccacf2f36e622564b5f13a95f543145`; final verification run41775469206
has a successful verify job. No later work was present at reconciliation.

## 1. Economic findings and the next research decision

There is **no independently demonstrated NET edge**. There is also **no demonstrated
system-wide impossibility**. Do not authorize trading, promote a frozen candidate,
or implement more model/safety layers to disguise this distinction.

This change calculates system-level economic constraints from all twelve existing
BDP1/AIP1 cost contexts and the frozen CCP1 receipt. It makes no source request,
retrieves no return labels, reruns no model and changes no economic decision.
`python -m research.system_economic_feasibility` verifies source hashes and exact
reproduction of [the arithmetic receipt](SYSTEM_ECONOMIC_FEASIBILITY.json).
Its calculations are constraints/scenarios, **not new economic performance**.

The dominant observed research limitation is weak or uncertain prediction relative
to friction, rather than inability to open every minimum-volume instrument.
The frozen BDP1 review reports maximum positive pre-cost 2-SE bounds of0.234732 bps
in selection and0.208831 bps in exposed audit, versus a minimum base cost scenario
of1.039699 bps. These are cross-group descriptive extrema, not paired forecasts,
a population upper bound on alpha or a new statistical test. AIP1's maximum bounds
are already negative before costs. CCP1's24 current-capacity rows all have negative
raw ordinary funding. No recipe is rescued by changing uncertainty, cost, direction,
symbol subset or portfolio weights after seeing these results.

**Director decision:** no new annual collection or predictive module is admitted
in this continuation. No sufficiently justified distinct causal hypothesis has been
identified from the reviewed evidence. Another feature recipe on the exposed bar
calendar, another fit or a newly named module would not supply independent support.
This is a research admission decision, not closure of the project or a requirement
for another OWNER approval. Implementation/research authority remains active.

The next economic experiment must add an identifiable information channel or a
distinct economic mechanism, state why it should produce a conditional expected
move above plausible costs, and specify observability, effective temporal support
and common-capital execution before substantial collection. A different algorithm
alone is insufficient justification. Existing authorized Pepperstone sources remain
the only source boundary; no external AI, feeds, runtime service or orders are sought.

## 2. EUR200 and systemic HARD21

The following standardized scenario repeats each instrument's minimum notional21
times. It does **not** require individual instruments to satisfy HARD21 and does not
choose a winning instrument. Rows are shown in the original receipt order.

| Receipt | Instrument | Observed current minimum margin EUR | Base cost scenario bps | Friction envelope for21 minimum trips EUR | % of initial200 EUR |
|---|---|---:|---:|---:|---:|
| BDP1 | EURUSD |33.33|1.040|2.183|1.092%|
| BDP1 | GBPUSD |39.96|1.536|3.742|1.871%|
| BDP1 | USDJPY |29.79|1.565|2.860|1.430%|
| BDP1 | AUDUSD |31.13|1.834|2.341|1.171%|
| BDP1 | USDCAD |29.79|1.479|2.702|1.351%|
| BDP1 | XAUUSD |175.58|3.254|31.258|15.629%|
| AIP1 | US500 |33.89|2.194|2.741|1.370%|
| AIP1 | NAS100 |126.50|1.927|9.126|4.563%|
| AIP1 | GER40 |129.17|2.495|13.068|6.534%|
| AIP1 | UK100 |63.50|3.739|9.527|4.763%|
| AIP1 | AUS200 |27.50|6.195|7.242|3.621%|
| AIP1 | JPN225 |177.95|4.085|26.859|13.430%|

Each receipt separately reports the maximum captured cost bps and maximum captured
minimum-unit notional. Their product is an envelope of those captured friction
scenarios, not a simultaneously observed trade cost. It combines historical quote
contexts with current tariffs and margin. It is neither a future cost floor nor
a historical cost bound. Base friction includes two commissions and three spreads
(spread plus declared slippage); the receipt also reports the original2x sensitivity.
Financing, changing spreads, executable depth and adverse floating PNL are omitted
and remain unknown. Do not add costs from different receipt dates to certify a
joint portfolio. These numbers are not expected losses or a requirement to trade.

Under these static scenarios all12 single minimum units fit initially after one
friction envelope. At140 EUR equity on the **same** initial capital path, XAUUSD
and JPN225 fail that screen; the other10 still fit. Gold has only22.932 EUR initial
margin/friction headroom and JPN22520.771 EUR, before adverse price risk. This shows
capital concentration and deterioration of capacity; positive headroom does not
establish safe sizing. Actual current margin must be reobserved causally, and
historical or stressed margin can differ. EUR60 is the initial peak-to30% decline,
not a separate cost budget, fixed reserve, per-trade cap or reset permission.

Low FX minimum margins therefore do not establish capital impossibility. Likewise,
cheap margin alone does not create return. Reducing minimum units would reduce EUR
friction and exposure, but would not by itself improve directional edge in bps.
Higher volume cannot cure negative per-unit economics and consumes more capacity.

HARD21 needs21 admitted, financed, completely closed round trips in **every** ex-ante
eligible week.52 eligible weeks would need at least1,092 trips;52 weeks alone are
not12 calendar months. No existing complete financed weekly path demonstrates this.
The sparse EPA/SQP schedules cannot be annualized or used to remove unfavorable
weeks. Nor does their failure establish a universal ceiling on other mechanisms.

Occupied-time arithmetic helps distinguish frequency from profitability. With
one continuously usable financed slot and120 available hours,21 trips require
mean occupation no greater than5.714 hours, even before idle time. With40 available
hours the corresponding value is1.905 hours. More simultaneous funded slots relax
that identity but require real joint capital/risk support. These are illustrative
windows, **not** new eligibility rules or a claim that such slots/signals exist.
The JSON discloses all40/120-hour and1/2/5-slot cases. Missing source, holding
protection, variable margin, session closures and latency reduce usable capacity.

Orchestration must allocate only on causally supported NET opportunities and test
incremental contribution on the same prospective clocks/reference policy. A fixed
weighted combination of unchanged nonpositive expected-NET legs remains nonpositive
by linearity; lower variance alone cannot change that mean. Conditional selection,
execution-cost netting or changing marginal exposure could alter the problem, but
their economic contribution must be demonstrated. CCP1 did not test cross-basket
netting. No retrospective combination of frozen results is admitted here.

## 3. Product work

No native code change is economically or functionally justified by this calculation.
The single orchestrator, NativeFundedLedger, NativeFundedSession and protective
observation-only Cloud adapter remain intact. This avoids adding decorative Scout,
Analyst or Skeptic classes without an identifiable contribution.

The small Python receipt calculator is an offline development analysis, with only
the standard library. It is not part of the final cBot or a permanent dependency.
CI checks arithmetic/provenance without secrets or broker access. No fixture or
compiler success is presented as economic or operational qualification.

## 4. Independent evidence still required

A supportable new mechanism needs one preregistered learner/selection/allocation
policy, full trial/universe disclosure and causal input/label clocks. Any pilot
must check source/financial support before return inspection; it cannot select
favorable dates. Trial multiplicity and shared temporal/regime exposure matter.
No fixed sample size is invented without an effect/variance/dependence estimate.

Development, selection and terminal confirmation need a globally reconciled data
inventory. Old exposed calendars and an unused model-local holdout cannot become
independent by renaming them. Future dates are not independent if their outcomes
guide later design. A terminal block must remain untouched after the **whole system**
is frozen; the present work does not assert that such a block already exists.

Economic evaluation must cover at least12 relevant authentic months, including
complete prospectively eligible weeks, with one continuous EUR200 ledger, executable
side/FX/cost timing, holding marks and joint margin/risk evidence. All eligible weeks,
missing paths, abstention, source failures and delisted/unsupported instruments must
be retained. Compare the same frozen reference portfolio and all predeclared
incremental mechanisms on identical clocks, without favorable subset promotion.
Do not certify continuous30% drawdown, actual fills or historical broker terms from
indicative sparse quotes/current metadata. No orders are permitted to manufacture
missing execution, recovery or Cloud evidence.

## 5. What can and cannot block the final objective

Demonstrated barriers are recipe-specific: BDP1's cost gap, AIP1's uncertainty and
CCP1's negative current funding. Minimum-volume capital concentration in gold and
JPN225 is quantitatively material under the reported scenarios. None proves all
authorized mechanisms impossible. There is no universal minimum achievable holding
time, maximum aggregate NET opportunity rate or positive edge established here.

The unsolved system problem is to find a causal NET mechanism with enough genuinely
financeable opportunities **each** eligible week while controlling the joint path.
Frequency cannot be forced and independent evidence cannot be created retroactively.
There is no defensible convergence date or guarantee from the present evidence.
Changing the EUR200 capital, HARD21,30% drawdown or source boundary is not requested.
Research stops short of another unsupported experiment; requirements and all frozen
results remain unchanged, with NET unknown rather than invented EUR0 performance.

# GER40/NAS100 joint liquidation risk — exposed development

Freeze before measuring joint paths. PR #268 rejected contemporaneous cross-index
acceleration in both directions, and own acceleration lost under adverse costs.
Do not retest those signals. Gold's larger move scale and higher margin warrant
separate research, but cannot explain whether the two index positions can coexist.
Low-friction US500 improves margin headroom but does not answer the same question.
The two-index original tape, with synchronized EUR conversion, can resolve
joint liquidation risk at the observed EUR261.70 combined minimum margin.
The economic question is whether conditioning the risk estimate on already
observed same-day repricing improves reserve decisions before allocation.

Use all weekdays in the original 12-week tape and its 10–14 New York hourly
clocks. These fixed clocks carry no trading signal. The first four weeks
initialize estimates. In the last eight, compare an expanding historical
95th-percentile risk estimate with the same estimate conditional on the
two indexes' previous 60-minute moves agreeing in sign. Update only from
completed earlier weeks. Require 20 priced training labels in the conditional
cell, otherwise use the pooled estimate and count the fallback. Test agreement
as a risk feature, not a direction forecast. The simple alternative is pooled
risk on the identical clocks. Report a 95% quantile pinball loss, misses,
risk estimates and chronological halves; weekly block results are descriptive.

For both relative exposures (same and opposite sides), symmetrize risk by
taking the worse drawdown from the two mirror directions. One 0.1-unit
position per index at t+5 with a 45-minute path. Use authentic paired marks,
signed EUR conversion and the declared adverse spread/slippage convention
from the prior receipt. Require all marks on both legs and preserve missing
paths separately. Measure loss from pre-entry equity at the same quote clock,
and compare the sum of individual worst losses to synchronous joint loss.
Use the original zero-commission/zero-conversion-fee contracts and verify
known rollover falls outside the hold. Do not simulate a broker stop.
At static EUR300 and EUR210, compare stress reserve and combined observed
margin, and report individual realized stress breaches as scenario observations.
These are diagnostic equity levels, not funding approvals or cBot rules.

No predictor promotion. Advance a reserve method only if it improves quantile
loss in both halves without increasing total misses. A genuine allocation
test still needs independently supported positive after-cost signals, as-of
margin and equity, and the native common ledger. No orders, new broker
requests or independent confirmation. Preserve encrypted original and
emit aggregate data only.

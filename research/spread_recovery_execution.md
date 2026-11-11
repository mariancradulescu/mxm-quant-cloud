# Does spread recovery improve the execution of an existing intent?

OWNER v2.0. An already-admitted intent can lose a small expected edge by
crossing a transiently wide spread. Waiting for quote recovery could
preserve that edge, or the midpoint could move against the order while
waiting. Test entry implementation shortfall directly. QSR1 was a
directional reversal forecast after a one-sided shock. This protocol
generates no directional forecast and does not use any closed study's
signals, fills or returns.

The target cohort covers three available, minimum-margin-supported routes
observed in MEF1: AUDUSD (08:05 UTC), US2000 (09:35 New York), SpotCrude
(10:05 New York). The clocks represent liquid-session reference points,
not claimed event timestamps. Evaluate 26 weeks from 2026-05-04 through
2026-10-30 on weekdays, in two fixed 13-week chronological halves.
The data are exposed historical research. Audit each route separately
and retain every route and half.

At time t require fresh BID and ASK at t−90, t−60, t−30 seconds and t.
A quote is valid if both sides are observed within 20 seconds, are
positive, and are noncrossed. Equal quotes are retained. The spread at t
must be strictly wider than all three preceding sampled spreads. For a
pre-existing order, choose the first of t+30 and t+60 with spread no wider
than the median of those three baseline spreads, otherwise use t+90.
Require a fresh pair at all three prospective comparison clocks; report
incomplete selected observations separately. Compare with immediate
entry at t and a fixed wait to t+90 on those same observations. Quotes
at sampled clocks model price availability, with no fill or depth claim.
No exit, holding return, or benchmark direction is optimized.

Test hypothetical BUY and SELL separately, at ASK and BID respectively.
Express signed improvement in quote-currency bps using the same midpoint
at t for every policy. Decompose adaptive versus immediate into midpoint
movement and half-spread change; retain improvement against the fixed wait.
Restrict evaluation to explicit USD-quoted contracts with current fixed
USD-per-lot fees, fixed USD minimum fee, valid minimum grid and modeled
buy/sell margins within EUR300 individually. Such fees cancel between
entry-time alternatives at identical size in USD. Unknown cost or margin
makes the route ineligible. Additional modeled adverse friction charges
the adaptive policy alone 0.25 bps, so positive adjusted results have
room for implementation cost. This is an entry benchmark in USD bps,
without funded EUR NET, holding costs, fill probabilities or exposure.

Each half requires at least 12 fully compared events across eight weeks
and 90% completeness among selected observations. Equal-weight active
weeks. Require strictly positive improvement after 0.25 bps stress for
both directions against both alternatives in both halves. This is a
screen for a route-specific execution policy, not an independent
confirmation or predictive admission. A passing route must be tested
with an independently admitted economic signal and the common C# ledger,
including missed fills, floating equity, shared margin and ablation.
No use of this screen to reopen frozen strategies. No orders or Cloud.

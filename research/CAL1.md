# CAL1 · Chronological calibration of executable post-entry outcomes

This is a new development hypothesis. The original FCE1 Pepperstone tape is
already exposed. CAL1 leaves FCE1, JRS1 and WFG1 and their evidence unchanged.

An hour of signed price displacement may continue if the last 15 minutes
agree with it. A disagreement may signal decay or reversal. Test this with
closed M15 and M5 observations, separately in USD FX and commodities. Learn
both long and short post-entry outcomes by family, hour sign and agreement.
The signed hour and quarter-hour moves are features. They are never reused
as the predicted move. Compare directional calibration against unconditional
training base rates for the chosen side and against probability 0.5.

Freeze the learning at 2026-03-02 00:00 UTC. Only complete paired outcomes
before the boundary enter training. Give equal weight to distinct observation
days. Require five such days in the cohort. The larger of two daily standard
errors supplies the uncertainty allowance for standalone and incremental
gross. It is descriptive, without a statistical independence claim. Evaluate
the second three weeks without updating the learned distribution. Report
the frozen training hash, label coverage, probability scores and realized
gross and NET on scored post-entry outcomes, including rejected opportunities.

The source is FCE1 run 43036474843, artifact 13863803890. Authenticate the
encrypted bytes and plaintext commitments in custody. Preserve BID/ASK on
the five-minute grid by retaining the original observation in the first
minute of each slot. The two-sided universe is AUDUSD, GBPUSD, NZDUSD,
SpotBrent and XAUUSD. Sample 15:00–17:30 UTC at half-hour intervals to leave
exit coverage before the source's 19:00 UTC cutoff. Require aligned
complete bars with at most one minute of age. Wait at least one second for
an execution observation. Cancel an opening intent if the next observation
arrives ten minutes or more after the decision. Both label legs and the
capital book use the same existing prediction invalidation and volatility
protection, with a 45-minute cap and delayed exit execution.

One EUR300 model book per counterfactual. Require the minimum physical
volume, current quoted margin and fee floor, positive conservative NET
both standalone and relative to the opposite side/cash, and portfolio risk
feasibility. Use estimated adverse costs for admission. The separate
adverse ledger reprices the executed path. Repeated risk states are a
deterministic sensitivity guard, not independent simulations. The long
and short controls propose their named side at the same eligible clocks
and minimum size through the common allocator and funded ledger. Their
positive ranking token only permits consideration, with no predictive
interpretation. Compare with cash and both family ablations. No policy
choice is changed after observing results.

The C# observation-only product can run the same profile from completed
native Algo bars and its quoted contract context with an explicit UTC
cutoff. Actual price snapshots, quote time within a slot, FX and financing
inputs, cTrader history and tariff mapping may differ. No live Cloud
execution, broker orders, uncapped intrainterval drawdown, transferable
saved model or independent economic qualification is inferred.

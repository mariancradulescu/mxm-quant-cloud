# CDE1 · Conditional economics of persistent price pressure and session handoff

Freeze both hypotheses and all four cells before opening any source rows for
CDE1. This is a single exposed-development study of two new entry mechanisms
on existing original Pepperstone marks. The IPC2, CAL1, WIR1 and WFG1
configurations and original results remain closed. No IPC2 subgroup,
direction inversion, retuning, or outcome-driven selection is used.

**FX pressure persistence.** In four contiguous completed M15 bars, take the
direction of the hour displacement only if at least three closes are in the
directional halves of their own high-low ranges. Repeated directional closing
pressure is a testable proxy for persistence of intrahour repricing, not
observed order flow. Apply individually to AUDUSD and NZDUSD with Chandelier
exit and 45-minute safety limit. This is not a relative pair strategy.

**Copper session handoff.** At 08:30 or 14:30 UTC take the direction of the
opening half-hour if it opposes the displacement of the preceding hour.
The hypothesis is that fresh liquidity at the session handoff reprices
inventory and the new direction persists. Use prediction invalidation and
a 60-minute safety limit. Six contiguous completed M15 bars define
the two non-overlapping horizons.

Use the original IPC2 authenticated and encrypted tape, run 43176793567,
artifact 13925405999. Zero new broker requests. FX decisions are weekdays
08:00, 08:30, 14:00, 14:30 UTC and Copper decisions at the half-hours only.
The nominal maximum is 50 per week. Existing five-minute as-of marks and
EURUSD conversion drive execution and stress. Entry uses the next eligible
observed mark and the existing maximum age. Cost estimates and margins
are original terms at collection, conditionally applied to history.

Aluminium is excluded prospectively from these mechanisms. IPC2 contract
evidence leaves only EUR23.44 (long) or EUR24.18 (short) from the EUR300
book at minimum size before costs or drawdown. That remainder cannot
fund even the previously documented NZDUSD minimum margin of EUR25.06.
Copper remains fundable. Exclusion applies to CDE1 only. At IPC2 observed
terms the AUDUSD and NZDUSD legs would require EUR55.86 combined margin
before either leg's costs and interim incomplete-fill risk. CDE1 results
are for individual transactions and cannot certify a funded pair.

Split each mechanism into two cells using a pre-entry burden proxy:
twice the observed spread plus modeled round-trip slippage and fee in EUR,
divided by the absolute past displacement in EUR. LOW is at most 25%;
HIGH is above 25%. The Copper denominator is opening half-hour motion.
Funding and conversion are included in realized NET; the ratio itself
is a feature, not a cost-completeness or forecast claim. No alternate
cut points. Preserve both cells regardless of result. Tick-based spread
and causal bar structure are available in the existing native cBot path.

Development W28–W33 and evaluation W34–W39, 2026, cutoff 17 August UTC.
Use equal week means, minimum four matured training weeks per cell.
Freeze cell probabilities of positive adverse NET, expected own and
reverse-rule incremental adverse NET, and uncertainty as three times
the larger weekly standard error. The comparison is the pooled family
probability trained on the same past weeks, plus neutral Brier and
funded long/short/cash. Report counts of wins, losses, flats, tail
quantiles, mean win/loss, gross and friction as well as NET per cell.
Use the same selector thresholds and current cost uplift as the native
integrated research path. Control portfolios use the same opportunities,
fees, joint risk, and one EUR300 book each. Quantify contributions via
full FX/metal ablations. All four comparisons are exploratory, with no
independence assumption, inferential p-values or promotion.

Use eight synchronized recent 15-minute OHLC/FX shocks from the existing
native joint stress kernel. Held, pending and candidate positions share
the same scenario clock; different scenario values are tested explicitly.
These are sampled stress scenarios, not a joint tail calibration or
continuous equity bound. Missing coherent history blocks entry.

Reconstruct the frozen model in a fresh evaluation pass and compare
signal trace and funded result. Separately exercise synthetic funded
admission, open-position restoration and settlement in the native
checkpoint path. Restored financial state and immutable predictions
are distinct from transient diagnostic calibration counts. A digest
confirms integrity only. Actual Cloud observation parity, broker
restart continuity and economic confirmation remain unverified.
No orders, Cloud activation, OAuth changes, or new external services.

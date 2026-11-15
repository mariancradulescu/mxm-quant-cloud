# MVE1 pre-source A1 — swap/rollover cost arithmetic and censoring, 2026-11-15

This prospective TECHNICAL completion is registered after the original
MVE1 protocol commit `f5f4339a69ce16d1eb1850b7023e58af4bebe078`
and BEFORE the first source decrypt/economic result. The original model,
six observable event definitions, 32 continuous features, fixed
lambda32, 26/13/13 chronological split, 12-instrument universe,
12/48 M5 forecast horizons, multiplicity and absence-of-promotion
conditions are unchanged.

The exact historical BID-like bar close is an entry/exit price proxy,
NOT a historical fill or historical ASK. Original BID/ASK + original
as-observed current contract cost samples are reused only from the
TRAINING phase. No future financial-quote availability influences
a feature, event, direction or candidate clock.

**Costs must include financing for a holding interval that straddles
the current-contract swap time:** from predeclared entry t+5 minutes
to exit t+(h+1)*5 minutes, count the integer next UTC daily
`swapMinute` boundaries. Central and adverse transaction friction
include observed modeled spread/slippage/commission; financing
additionally deducts **3× current authenticated directional daily
debit bps** per crossing, against the current minimum-volume EUR
notional. If funding status/schedule is unknown, classify the
corresponding candidate `FINANCIAL_UNKNOWN`, never
zero-funding as a fact. For an interval objectively not crossing
swap, no financing debit arises. Current terms alone do NOT
prove historical swap, past margin, broker fills or execution.

The separately reported *gross* predictive return/MFE/MAE/regime
information remains completely independent of financing. The EUR
diagnostic for selected event intents is a **conditional nonfunded
counterfactual** and may overlap across 5-minute clocks; never
aggregate it as a spendable EUR300 book or claim HARD21 or 30%
floating DD. If no predictive selection is robust, retain all
descriptive original EUR outcomes and do not promote any favorable
event/horizon/asset selected after results.

# RDE1 pre-source technical arithmetic completion A1 — 2026-11-15

The original RDE1 protocol was committed at `dd8f9cbda06494575c1fbf274cc38e3f6cfe990a` **before any RDE1 source recovery or scoring**. This A1 records an exact technical completion before source: the fixed 120-minute entry/exit must include broker-as-observed *current-term* directional financing costs if an interval crosses the contract's UTC swap time.

For each candidate from close of the next completed M5 bar to the close after 24 additional completed M5 bars, the modeled adverse round-trip friction in bps is:

`cost.adverseBps + 3 * number_of_UTC_swap_crossings * max(0, currentDirectionalDailyDebitBps)`.

A boundary equal to the *opening* instant is excluded; a boundary equal to close is included. If `fundingKnown`, `swapMinute`, `adverseBps` or directional debit is absent or invalid, the research financial gate is **UNKNOWN / NO ENTRY**. Applying this to the TRAIN-only directional advantage test and all subsequent conditional economic accounting is mandatory. No zero-funding imputation, favorable historical tariff certification, or guessed BID/ASK fill is permissible.

No universe, times, 48/24-bar direction hypothesis, 120-minute hold, risk bin definition, shrinkage, 15 EUR risk reserve, trial selection, threshold, statistical family or exposure split changes. In particular, this does not retune MVE1 or rescue its 60-minute segment.

**Status: pre-source technical completion only; original RDE1 economic outcomes remain UNOBSERVED.** Native C# common EUR300 accounting is still required before any portfolio economic verdict. This amendment does not authorize orders, Cloud trading or independent qualification.

# GCR1 A2 — source-reuse refinement BEFORE any GCR1 original collection

This SOURCE-ONLY prospective amendment supplements the immutable original
GCR1 protocol and `GCR1_OWNER_PRESOURCE_ADDENDUM_A1.md` WITHOUT changing
the combined signal, benchmark rules, clocks, costs, exit, capital or
chronological cohorts. The A1 full-source 4,940-request plan was a bound
IF previously captured inputs could not be proven complete; this A2
tightens acquisition to avoid duplicate Gold/AUDUSD bar collection.

## Reuse authenticated BDP1 M5 bars; do not revive its predictor

The repository's original BDP1 preserved source (run
`41724643418`, encrypted artifact `#13273950911`, SHA256
`e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370`)
contains original-account fully timestamped `AUDUSD` and `XAUUSD` M5
rows across its fixed 52-week global source calendar. This is primary
original price evidence, NOT BDP1's rejected forecast or independent
holdout. Public `research/pve2_protocol.json` lists its twelve-source
universe, and `portfolio_discovery_source.audit` reconstructs BDP1
original protobuf rows against its registered protocol.

Provenance reader MUST decrypt BDP1 only in the existing protected
`mxm-r3-custody-v1` environment with the installed existing key; verify
the immutable encrypted bytes hash, exact run binding, BDP1 original
account and raw source audit before reusing a **single** bar.
No new plaintext BDP1 tape is uploaded to any public artifact, nor
copied to the read-only Pepperstone environment.

For each fixed scheduled GCR1 day and t, map the original BDP1
`AUDUSD`/`XAUUSD` M5 `[start,end,O,H,L,C,volume]` rows by exact
`end` timestamp into the 49 complete *past* M5 bar-closes required
by GCR1 A1; never interpolate, silently forward-fill or use a
postdecision timestamp. Existing source coverage, incomplete bars and
time/clock mismatches remain per-clock `DECISION_UNKNOWN`. Do not
ask Pepperstone again for these complete BDP1 M5 source partitions.

## GCR1 NEW source that is still genuinely missing

Copper is not among BDP1's original twelve: collect exactly the
predeclared 260 daily `Copper` M5 windows, 03:50–16:10 UTC.
Capture all fixed original `AUDUSD` and `EURUSD` independent BID/ASK
quote clocks 08:05, 12:05, 16:05, 20:05 UTC for every one of 260 days
regardless of GCR1 signals, holidays or later market completeness:
260 × 4 × 2 currencies × 2 sides = **4,160** requests; plus 260
Copper daily M5 requests = **4,420** planned market-data requests,
plus one current original account roster, terms, margin/currency
preflight. Maximum 4,600 post-auth read-only requests; no hidden retries,
order traffic, OAuth changes or service dependencies.

The original *new* GCR1 Copper/BID-ASK protobuf bytes and decoded
census must be sealed under the existing v2 custody BEFORE computing
profit or making any posterior selection. The subsequent protected
independent readback combines its original ciphertext (same run
binding) with hash-verified BDP1, records source lineage, and
separately seals a GCR1 composite source **before** doing any
NET EUR evaluation. A merged source row may have an original BDP1
AUDUSD/XAUUSD M5 close and a new Pepperstone source quote at an entry
clock, but those are distinct types of evidence and are never
silently reinterpreted as historical broker fills.

Economic results, when available, are **conditional current-tariff
historical EUR** and remain globally exposed. No extra broker
requests are needed for closed studies; no BDP1 forecast scoring,
retuning or promotion. Cash/intent/UNKNOWN events and the close-before-open
ledger order remain as A1.

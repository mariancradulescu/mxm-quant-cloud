# BWR1-F1 — Exact original source only correction of a technical state-label mismatch

OWNER v2.0, 2026-11-14. This protocol is frozen **BEFORE the corrected
financial readback**. BWR1 source acquisition run 43576022822 SUCCESS,
979 genuine read-only Pepperstone EUR requests, original private
artifact 14105644555 and original public artifact 14106705125.
Original raw encrypted BWR1 source, original code, frozen economic
protocol, all source events and original INCORRECT first economic
receipt must be retained unchanged. NO new broker calls, new
signal, bar clock, entry, exit, threshold, instrument,
cost/slip scenario, selection, timeframe or calendar.
No economic retroactive tuning or independent validation claim.

## Exact bug discovered from immutable original public receipt

The immutable frozen feature detector returns state
`CAUSAL_REJECTED_BASIS` on 25 original historic 2025/2026
failed grade-basis events (13 first26 weeks; 12 last26),
but the downstream finance function checked the nonexistent
string `CAUSAL_REJECTED_BASIS_SWEEP`. Thus financial
evaluation returned only the 25 feature state labels
without ever entering post-entry monitoring, actual
BID/ASK+EURUSD conversion, fee or margin calculations.
The original public receipt incorrectly displayed
`basisSweepIntents=0, pairedCompleteEurPriced=0,
NET=0`. These zero values are TECHNICALLY INVALID
as financial verdicts. This protocol corrects ONLY
the literal state-label predicate to
`CAUSAL_REJECTED_BASIS`; no other changed code
may affect the monetary input/policy.

## Source immutable custody and separate corrected receipt

Sealed original BWR1 ciphertext Actions run
`43576022822`, artifact `14105644555`,
filename `bwr1-original-encrypted-source.v2.enc`,
SHA256:
`a019aaf2131173832630863d83bfa2127fb3a3d8ed6a6c22002fc42dc2b280e7`.
Source decrypted plaintext SHA256:
`df5f7f39e24921112bf89adde9aa47dccbee00f14d2b843a97860b2eb693e042`.
Original first public receipt artifact
`14106705125`, filename
`bwr1-public-original-conditional-eur.json`,
SHA256:
`13298cd7f3fe34ff2bec865f81c66aae36e1bdedd9d73a064bca57241ab399d2`.
Verify all THREE SHA256 and original run/source fields;
decrypt original in existing `mxm-r3-custody-v1`
only, via installed `R3_CUSTODY_PRIVATE_KEY_PEM`,
`unseal_new(...,"43576022822")`. The original
private payload has all raw request/response protobuf
pairs plus decoded entire M5 and all 10:05/10:40/11:35
BID/ASK paired snapshots for all 25 causal events,
and current original contract-margin snapshots.
Reconstruct current cTrader ProtoOASymbolByIdRes
contracts from ORIGINAL sealed protobuf, mapping
exact known original roster IDs to names. No unknown
contract defaults. Reconstitute M5 time-key INTEGER
from plaintext canonical JSON, no resampling.
Verify exact original source 260 weekdays and exactly
25 unmodified 10:00 causal intents BEFORE scoring.

Run corrected same original `financial(...)` route
on decrypted original source with the one literal
predicate repaired and unchanged 0.5/2bps supplemental
modeled slippage, current actual broker commission,
EURUSD signed conversion, 2 original min broker
volume legs, finance schedule and current margins.
Report both 26-week halves, all benchmark policies
on matched priced entries, missing quote / conversion
/ tariff reasons, all 25 original causal events,
and any nonfinance signal states. The first original
zero-income receipt remains intact and superseded
ONLY for the scoped technical bug; do not replace
original ciphertext or relabel exposed study as
independently confirmed.

No new Pepperstone read-only calls, no LIVE/DEMO
orders, Cloud activation or OAuth reauthorization.
No C# funded ledger/continuous DD/HARD21/12month
independent claim follows automatically from
hypothetical conditional NET EUR.

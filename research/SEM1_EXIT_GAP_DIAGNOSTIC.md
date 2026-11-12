# SEM1 exact fixed-exit missing-observation diagnostic (2026-11-12)

Scope: OWNER postclosure technical verification on the **identical** original
SEM1 and ESD1 encrypted tapes and the already corrected native EUR300
benchmark comparison. No strategy retuning, changes of entry/exit clock,
new economic selection, replacement of original receipts, or repeat of PDR1.
Original correction: run 43214539052 / artifact 13943645086.
Original SEM1 source: run 43207629492 / artifact 13938934824.
Original ESD1 source: run 43202303802 / artifact 13935958165.

The 30-minute causal filtered joint portfolio has exactly one missing
fixed-exit observation, a still-open position and 23 subsequent
UNRESOLVED_FIXED_EXIT rejects. The +11.493551 EUR adverse closed fragment
is not the account-level NET. The 30-minute complete-endpoint cohort uses
future-known coverage and is a distinct ex-post sensitivity, not a substitute.

This diagnostic only adds a position-level observation-coverage field to
the original read-only C# ledger output: position ID, instrument, fixed
entry/exit milliseconds, direction, whether both authentic as-of BID and
ASK existed before conversion, and nearest recorded valuation clocks.
Nearest *later* data are diagnostic ONLY and never used for an exit fill.
A raw pair existing without a final costed quote requires further diagnosis;
no raw pair in the frozen tape does not prove there were no authentic broker
ticks outside the original collection windows. The exact original 30-second
as-of limit and +1500ms decision delay stay immutable.

The existing custody runner rechecks original encrypted byte SHA-256, public
receipt SHA-256 and decrypted source SHA-256 before processing. Output is an
additional nonpromotional technical artifact covering every prior
scope/horizon/policy/scenario identically. It cannot qualify any strategy.

## Prospectively handling missing cBot quotes (specification only)

The single eventual C# Cloud cBot must distinguish no paired quote,
unpriceable conversion/tariff, market closure, stale quotes, and connectivity
loss without manufacturing OHLCV execution prices. Keep the originally
scheduled exit and an auditable unresolved-position state. While equity
cannot be valued reliably, freeze new-risk admission and retain original
holding, margin and event identifiers across restart. Recovery must be
idempotent, reconcile true broker position/fill state and current authentic
BID/ASK, and apply a separately authorized, predeclared missed-exit
execution/safety policy. Do not silently act at a later or favorable price,
and never send orders under the current OWNER read-only mandate.

Any later targeted original-account read-only retrieval must distinguish
(a) as-of tick at **the original fixed exit clock**, both sides, exact
original max-age, (b) currency/conversion/fees/contract fields required for
financing, and (c) genuine unavailability. Authenticate the same original
account, store new ciphertext/source hashes separately, document the
original clock and provenance, rerun **all** affected policies with unchanged
economic method, and retain incomplete cases if no eligible quote exists.

# Session continuation benchmark correction

Original receipts and configurations remain immutable. In SEM1, NAS100,
XAGEUR and ETHEUR return the H1 momentum side whenever the filter fires.
The original comparator was valued only on fired rows. In ESD1, the LTCUSD
breakout close is above the maximum or below the minimum of the first nine
bars, which include the first hourly open, so its side is also hourly momentum.
The original same-row difference measures direction conditional on selection,
and is algebraically zero on these four configurations. This correction
evaluates the value of selection and opportunity cost across eligible clocks.

Use the exact archived SEM1 and ESD1 tapes, the original calendars, causal
features, signals, holding horizons, exits and original central/adverse
cash-flow assumptions. For SEM1 run both 30 and 90 minutes separately and
cover all three affected symbols, jointly, individually, and jointly leaving
each one out. For ESD1 cover the exact LTCUSD 60-minute rule. Momentum trades
each feature-complete eligible clock in its causal H1 direction. Long and
short use the same universe with their respective fixed sides; cash abstains.
The original filtered policy abstains if the filter does not fire.
Each policy/scenario starts once with one EUR300 model ledger and the same
minimum-size, risk and capital rules. No historical independent confirmation.

The primary chronology enters only on an eligible current mark with known
contract financing, without reading the future exit. A fixed exit with no
authentic quote is unresolved and blocks further entries for that book; it
is never priced from bars or moved to a favorable time. As a separate source
sensitivity, run every policy on the complete-endpoint cohort, acknowledging
its ex-post coverage conditioning. Apply chronological closes first, then
entries in ordinal symbol order at tied clocks. Use authentic simultaneous
held marks, actual minimum size, conservative current margin, and the same
sampled 30% retained/entry equity rule for every policy. One modeled millisecond
per request/fill delay binds to original marks with at most 2ms simulated age.
Marks between entry and exit are used where the archive provides them. No
continuous drawdown certification. Financing is from the original contract.
No market order, optimization, modified signal, shifted clock or exit.

Ledger settlement uses original side commission, signed conversion and
distinct entry/exit observed spread-derived slippage. A nullable ledger event
field carries the observed exit slippage; legacy events retain original
serialization and entry-slippage fallback. Central and adverse paths apply
the same decision rules separately, permitting stressed capital to reject
different entries. Report closures, unresolved exits, absent held marks,
abstentions, funding constraints, peak occupancy, sampled drawdown, NET by
week and symbol, and joint ablation. The existing SEM1 matched observation
diagnostic remains the separate predictive-selection analysis. Neither the
recalculation nor any positive result changes historic qualification.

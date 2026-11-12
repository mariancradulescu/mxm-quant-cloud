# SEM1 exact original as-of quote recovery — technical scope

Original target position is ETHEUR/1788073201500, long at
2026-08-30 07:00:01.500 UTC, with the original fixed 30m exit
2026-08-30 07:30:01.500 UTC (1788075001500ms). The previously signed and
verified original SEM1 tape contains no eligible paired BID/ASK at this
exit. No original or corrected economic receipt will be overwritten.

Perform only the following *new source* technical check on the **same**
original authenticated Pepperstone EUR account, under the existing
enforced read-only allowlist and OAuth state (no refresh). Query BID and
ASK tick events for ETHEUR and EURUSD in the half-open prehistory capped
at the exact original fixed exit: [clock-30000ms, clock] inclusive.
Use the original ordered historical tick decoder and last chronological
event at or before the clock. Do not modify the 30-second maximum
staleness, +1500ms decision offset, the fixed exit, signal, position size,
policy, valuation model, or historical current-contract assumptions.

Only the exact historical tick list and selected source price go into an
additional authenticated, ciphertext SHA-256-committed, run-bound custody
archive. The public receipt exposes symbol-side availability and tick
timestamps/ages, authentication status and source hashes but no broker
account identifier, tokens, private credentials, price data, or orders.
A missing tick in this narrow query does not prove the market was
globally inactive. Reject incomplete pagination or bad account identity.

This test explicitly examines possible historical source-window clipping,
not a novel strategy or economic score. If authentic paired ticks exist,
separately verify conversion and original-source invariants and apply the
same recovered observation to every affected portfolio policy and scenario
before publishing any corrected financial outcome. If no eligible pair
exists, preserve SEM1 30m as economically incomplete. There is no
retrospective rescue of favorable subsets. Current OWNER v2.0 boundaries
hold, including one C# cBot, EUR300 capital, no trade, no Cloud activation,
no new services and no independent confirmation on exposed history.

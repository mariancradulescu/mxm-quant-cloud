# Brent-led oil transmission

One exploratory configuration under OWNER v2.0. SpotCrude is the only
funded target. SpotBrent is a contextual instrument because both contracts
reflect crude fundamentals while regional liquidity can delay WTI price
adjustment. The test concerns a directional Brent lead, not OTC1's quiet
Brent/local WTI basis unwind, ESP1's WPSR response, or the prior WTI
tick-activity drift. EURUSD supplies signed FX only.

Preflight on November 2–10, 2026 on the seven specified weekdays. Use
10:05–11:00 and 12:05–13:00 New York entry/exit clocks. Require current
enabled mode, observed short permission, minimum size and both margins
within EUR300, current session and funding evidence, paired historical
WTI and EURUSD entry and exit quotes, and complete commission and conversion
attribution. Use the existing 20-second freshness and reject crossed
quotes. Equal observed BID/ASK at the same as-of clock is accepted. Gate
requires at least five of seven complete days at both clocks separately.
No extended collection if this fails.

For the historical study use May 4–October 30, 2026 and two fixed halves
of 13 weeks. On weekdays at 10:00 and 12:00 New York use complete closed M5
bars for Brent H4, Brent H1, WTI H1 and WTI M15. Exclude all Wednesday
morning decisions to avoid the ordinary WPSR release clock. Trigger only
when Brent H4 and H1 have the same nonzero sign and WTI H1 has the opposite
sign. At the corresponding entry clock take the Brent sign, exit at the
specified exit clock. Require contiguous WTI holding bars. Compare WTI
own H1, WTI own M15, long, short and cash on identical signal clocks. Zero
M15 direction is cash. One rule with two fixed session clocks, no clock
selection or optimization. Exposed exploratory dates, not confirmation.

Report model and benchmark gross on bar-complete signals and central and
adverse on identical cost-complete signals, equal weighted across active
weeks. Use current minimum volume and tariffs, actual side of target and
FX, and slippage assumptions of 0.5 and 2 bps round trip. Gate requires at
least 12 priced signals, six active weeks, 75% priced coverage, positive
adverse performance and strict adverse superiority to all benchmarks, in
each half. Passing authorizes a follow-up in the existing shared C#
ledger, with sampled floating equity, portfolio ablation and continuous
EUR300 book; passing alone is not funded evidence. No orders or Cloud
activation. Aggregate receipts only.

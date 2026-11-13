# EURJPY direct versus synthetic quote parity

Choice before measurement. Altcoin breadth had sparse synchronized
coverage and used same-market directional returns. Oil futures versus
perpetual parity needs roll, expiry and financing evidence to define
fair value. FX carry requires historical swap terms and multi-day
financing, so present tariffs would be an inadequate substitute.
For this intervention choose an algebraically linked currency cross.
EURJPY is a previously researched instrument, with indicative minimum
margin EUR33.33 in CMA1. This tests quoted cross-rate parity rather
than another cross-asset return transform. The independent new-instrument
direction remains open.

EURJPY synthetic BID is EURUSD BID times USDJPY BID, ASK the product
of the ASKs, using simultaneous as-of broker marks. At a clock, if direct
EURJPY BID exceeds synthetic ASK, predict short EURJPY. If direct ASK
is below synthetic BID, predict long. Overlapping bands abstain.
A genuine dislocation might predict dealer repricing, or already be
resolved by entry. The discrepancy may reflect stale quotes, asynchronous
sampling, spread markup, or direct-market information. The single-leg
payoff may lose even if cross-market parity improves. This is a delayed
single-leg prediction, without claims of triangular execution.

Collect original Pepperstone EURJPY, EURUSD and USDJPY bars and
BID/ASK marks for 2026-08-31 through 2026-11-09 exclusive, ten exposed
weeks. Assess weekdays every 15 minutes from 06:00 through 08:45 UTC
inclusive. Sample the 5-minute grid, with a maximum age of 2 seconds
per side at acquisition and chronological pages. Decision requires all
three model-ready pairs at t and EURJPY at t-15. No future eligibility.
Enter at t+5 and hold 15 minutes; require every target mark through
t+20 with signed JPY to EUR conversion. Verify original minimum volume,
margin and explicit USD-per-lot commission, zero minimum fee and zero
conversion fee; a known rollover must be outside each priced hold.
Central uses original BID/ASK, source per-side slippage and commission
with EUR conversion. Adverse uses the existing extra full spreads and
twice source slippage stress. Current tariffs condition this historical
test. Overlapping hypothetical holds are possible.

Compare to opposite of own last-15-minute direction, matched long,
matched short and cash. Benchmark directions only at parity-selected
clocks. Report availability, count, weekly frequency, chronological
five-week halves, minimum margin, and conditional gross/NET in EUR.
Advance only with positive adverse EUR in both halves and full-period
adverse better than all controls. Any follow-up requires adequate
sample, as-of evidence and the native common C# book. No funding,
independent confirmation, trading orders or Cloud activation in this test.

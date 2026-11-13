# Signed intrahour variation and capture after costs

Fixed before scoring. Cross-index acceleration failed against own information
and joint index minimum margin left EUR38.30 before losses. Gold and GER40
offer larger nominal payoffs but higher minimum margin. EURUSD and US500
offer observed minimum margin EUR33.33 and EUR34.29 and separate economic
exposures. Their known historical tape permits comparable exact quote costs.
US500 opening-anchor reclaim was too sparse. EURUSD's NXE1 equity-transfer
rule lost after cost; the new information is entirely within each target.
US-24 expansion is still relevant, with separate evidence required for
its legal volumes and pricing. No prior rule is called.

Test whether disproportionate squared moves in one direction inside a
completed hour identify persistent repricing beyond its endpoint. A few
large same-direction moves could convey information, or reflect a transitory
shock that has already been absorbed. Compare to own hourly endpoint
momentum, constant long/short and cash on identical available clocks.
The predictors and minimum sizes are fixed, with no fitted threshold.

Use both instruments for all 17 NXE1 exposed weeks, Monday–Friday,
10:00–16:00 UTC hourly. Require 13 five-minute original midpoint marks
through t. Signal is the sign of sum(r*abs(r)) for adjacent log returns;
endpoint uses the sign of the sum of r. Both use next 5-minute entry and
55-minute holding with all 12 marks, signed EUR conversions and no crossing
recorded UTC rollover. Ties abstain. At an hourly boundary the next entry
follows the prior exit. Historical terms observed later, model at the legal
minimum, no funded claim.

Central crosses actual paired spread with source per-side slippage and
the authenticated USD-per-lot commission schedule (round trip conversion
per side). Adverse adds full spreads at entry and exit plus twice the
modeled slippage, matching the established stress convention. Zero conversion
fee and minimum commission must be explicit. Report sampled risk, margin,
weekly opportunity counts, first 8 and last 9 weeks, and paired weekly-block
uncertainty. Advance only with positive absolute adverse EUR in both halves
and positive full-calendar adverse incremental EUR versus every control.
The two targets share exposure and have no combined funded result. A pass
would justify further as-of evidence and common C# ledger evaluation.
No broker orders, new requests, closed study replay or Cloud activation.

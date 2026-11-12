# PDR1 · Cross-market and extended-hours price discovery

Exploratory development on the original Pepperstone EUR account. Fix all
choices before accessing returns. SEM1 did not contain simultaneous WTI
and Brent bars or the extended-hours equity contracts. Original inventory
recorded current minimum margin EUR6.24 for AAPL.US-24 and EUR5.16 for
GOOG.US-24. They need fresh enabled-contract, fees, margin, session and
paired price proof. Oil and ETH are existing routes with distinct mechanisms.

Eight calendar weeks 2026-08-31 through 2026-10-25 inclusive. Each week one
weekday rotating Monday to Friday and, for ETHEUR only, one weekend day
alternating Saturday and Sunday. Entry clocks 01:00, 07:00, 13:00 and 19:00 UTC,
each with separate fixed +30 and +90 minute exit. Latest genuine two-sided
quote at nominal clock +1.5 seconds, up to 30 seconds old. Contractual
session and causal funding eligibility required. Do not infer actual fills,
market depth, historical margin or tariff continuity.

- SpotBrent: opposing H1 directions in Brent and WTI, followed by the latest
  M15 relative return (Brent minus WTI) aligning with WTI's H1 direction.
  Test an incipient normalization of divergent energy repricing; trade Brent
  in the WTI direction. WTI supplies context only.
- ETHEUR: last two completed M15 returns both oppose the full H1 direction,
  with the latest half-hour producing more broker updates than the preceding
  half-hour. Trade against H1 direction. Test late-hour redistribution
  following an inventory move; activity measures quote updates only.
- AAPL.US-24 and GOOG.US-24: each is a separate target and the other its
  synchronized context. Opposing H1 directions followed by target M15
  direction aligning with the peer H1. Trade the target in the peer direction.
  Test shared technology repricing reaching the lagging contract. Assess
  separate routes and do not treat them as independent observations.

Use contiguous completed M5 bars, aggregate H1/M15 endpoints, original
paired quotes, fees, signed conversion/financing and existing central/adverse
costs. Compare matched own H1 direction, long, short and cash. In these
hypotheses a triggered rule takes the opposite of its own H1 direction.
An incremental directional comparison is therefore meaningful on the same
entry universe. Report all windows, missed marks, comparable outcomes and
calendar-week dependency. Two halves of four weeks, with three active
weeks in each to support an exploratory screen. Apply the original SEM1
descriptive weekly lower bound for both standalone and incremental late
adverse economics, and positive early means for each. This bounded
development study is not independent confirmation or a basis for activation.
Only supported routes warrant subsequent native portfolio evaluation.

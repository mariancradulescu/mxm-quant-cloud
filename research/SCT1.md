# SCT1 · Cash-session acceptance and delayed equity-to-oil transmission

Prospectively register two economic hypotheses on the existing authenticated
Pepperstone PRR1 tape, run 43031103899 and artifact 13861254511.
The April 6–May 1, 2026 development window is exposed. Reuse the exact source
bytes and current-at-collection contracts. PRR1 decisions and results stay
closed. There are no new broker requests. All times below are UTC for this
April sample. Use causal M15 constructed from complete M5 and original
five-minute BID/ASK, EUR conversion and margin observations.

## Cash-session gap acceptance, US2000 and US500

A move outside the previous cash range can represent a revaluation if
cash-session participation accepts it. Use the previous weekday's complete
13:30–20:00 UTC range (26 contiguous M15 bars). Skip the candidate when
the previous weekday has no complete range. The window follows the
[NYSE core cash session](https://www.nyse.com/trade/trading-information). At 14:15:01.500 observe only
the current session's first three completed M15 bars. Require the current
open outside the previous range, the first three closes outside on the same
side, and the final M15 move aligned. A retest may enter the previous
range intrabar. Forecast the gap direction with the absolute distance from
the previous range boundary to the current close divided by that close.
Manage with existing M15 prediction invalidation and ATR protection,
with a 120-minute safety limit.

## Delayed equity-to-oil transmission, SpotCrude

During cross-asset risk repricing, oil can respond to an equity impulse
with a delay. At half-hour decisions 15:00–17:30 UTC plus 1.5 seconds,
compute four completed 30-minute returns for both US500 and crude ending
45 minutes before the decision. Require positive centered cross-products
over those four synchronized returns. This is a local directional regime
indicator without a statistical significance claim. The subsequent equity
move from 45 to 15 minutes before decision must exceed twice its baseline
mean absolute half-hour return. Scale that impulse by the ratio of crude
and equity baseline mean absolute returns. Require crude to have traveled
less than half this scaled move in absolute terms during the impulse, then
to move in the impulse direction on the final M15. The remaining positive
projected directional move is the gross input. Use ATR protection and a
Chandelier trail with a 105-minute safety limit.

## Common financial experiment

Use the existing native selector, differentiated aligned historical stress,
and continuous EUR300 ledger, all at contractual minimum units to isolate
the mechanism. Use the existing central/adverse modeled costs and
execution latency. US500 was context in the source study. Model its short
route conditionally because the preserved tape contains margins and terms
but no separate US500 short-permission attestation. Compare both family ablations, funded long/short on
the same opportunity definitions, cash, and a repeated-stress control.
Account for shared capital and any simultaneous exposure that arises.
Report closed EUR NET, marginal contribution, weekly complete trips,
peak common margin and sampled equity. Compare economic evidence in each
policy with the same coverage limits. Positive results on this exposed
four-week tape remain exploratory. Five-minute marks cannot establish
continuous drawdown protection. No LIVE/DEMO orders and no Cloud activation.

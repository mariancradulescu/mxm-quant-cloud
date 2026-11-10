# JRC1 · Low-margin JPY risk participation and volatility unwind

Freeze before source access. The high minimum silver margin and cost erosion
in LDP1 motivate testing lower-margin FX contracts in the same native book.
This study invokes no earlier signals and does not include RRP1 or LDP1.

EURJPY risk participation: require concurrent completed H1 moves of at least
15 bps in AUDJPY and 10 bps in EURJPY, in the same direction, with EURUSD
movement at most 4 bps. Require EURJPY's last M15 candle to agree. Forecast
EURJPY in that direction, using the AUDJPY move magnitude. This isolates
common JPY repricing from the EURUSD component. Use existing M15 prediction
invalidation with a 60-minute exposure ceiling.

USDJPY volatility unwind: require an absolute H1 movement at least 15 bps.
The last M15 range must be at least 1.5 times the average preceding four
M15 ranges, and its candle body must oppose the H1 direction. Forecast an
unwind, using absolute H1 magnitude. Use existing equilibrium exit with
60-minute ceiling. These exact configurations are new, not the closed
07:00 H4 SFX1 USDJPY rule or gold-to-yen GEP1 rule.

Original-account EURJPY, USDJPY, AUDJPY and EURUSD contracts are required.
Validate actual quote/base assets, min volume, tariffs and expected margin.
Compose original JPY->USD->EUR BID/ASK through USDJPY and EURUSD using the
existing causal conversion implementation. No JPY mid or fixed FX estimate.

Five consecutive exposed weeks, 2026-08-03 through 2026-09-07 exclusive,
warmup from 2026-07-31 08:00 UTC. Observe weekday 07:00–13:00 UTC M5 quotes;
enter only fresh M15 clocks plus 1.5 seconds, 07:00–11:00 exclusive.
Keep native economic gates, one continuous EUR300, current retrospective
contract terms and the original central/adverse execution stress.
Run shared funding, ablations and funded long/short with the same candidate
clocks and gates but their own admission and adaptive exposure.
Report matched-clock descriptive references separately.

Positive central and adverse absolute NET, incremental value over direction,
weekly frequency, marginal risk and financing coverage all matter.
Any adverse accounting failure must distinguish financing from missing data.
No confirmation is claimed from exposed history and no candidate is promoted
from this screen. No orders or trading Cloud activation.

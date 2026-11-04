# Official capabilities and conditional economic discovery

Authority: OWNER_SPEC.md v2.0 with the explicit OWNER statistical historical-cost
continuation after PR53. Official technical references checked2026-11-04:

| Information | Recoverable interface | Remaining boundary |
|---|---|---|
| Historical OHLC and tick counts | Open API GetTrendbars; Algo GetBars/LoadMoreHistory | Broker coverage, pagination and missing bars must be checked; tick counts are not exchange volume |
| Historical BID/ASK events | Open API GetTickData by side; Algo GetTicks/LoadMoreHistory | Seven days is the maximum interval per Open API request, not the full history; hasMore controls truncation |
| Current terms and finance | Symbol fields, ExpectedMargin, conversion routes; Algo Symbol/GetEstimatedMargin/NormalizeVolumeInUnits | Current terms/estimates do not establish past tariffs, margin or fills |
| Native indicators and events | Algo Indicators, Bars/Ticks/Symbol events, multiple symbols/timeframes | API availability is not product acceptance or evidence of predictive skill |
| Additional native symbol information | Algo Symbol.FuturesSettings and Symbol.Sentiment | These capabilities exist; actual per-instrument content/history has not been established by the present Open API sources |

References:
https://help.ctrader.com/open-api/ ;
https://help.ctrader.com/open-api/symbol-data/ ;
https://help.ctrader.com/open-api/messages/ ;
https://help.ctrader.com/open-api/model-messages/ ;
https://help.ctrader.com/ctrader-algo/references/MarketData/MarketData/ ;
https://help.ctrader.com/ctrader-algo/references/MarketData/Bars/Bars/ ;
https://help.ctrader.com/ctrader-algo/references/MarketData/Ticks/Ticks/ ;
https://help.ctrader.com/ctrader-algo/references/MarketData/Symbols/Symbol/ ;
https://help.ctrader.com/ctrader-algo/references/Indicators/ .

Cloud requirements are checked separately:
https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/ .
The documented Linux environment needs compatible compile-time dependencies.
The page explicitly says that files/directories are deleted on instance restart
or deletion. Existing local checkpoint checks therefore remain integrity tests,
not durable Cloud acceptance. No deployment, persistence certification or change
to the existing protective session is claimed. No external HTTP/AI service is added.

## MSP1 economic question and design

Can a causal likelihood-updated mixture distinguish persistent repricing from a
transitory price concession well enough to beat a zero-drift predictive baseline
and conservative costs across instruments/horizons? These are falsifiable latent
pricing hypotheses; dealer inventory or actual order flow is not observed.

`research/multiscale_conditional_protocol.json` fixes the entire recipe before
source readback. It reuses only the two cryptographically bound annual M5 sources
on12 FX/gold/index assets. No broker request or old model evaluation is required.
Raw protobuf/account/bar/quote reconstruction precedes the new native computation.
Four complete-bar timeframes (5/15/60/240 minutes), one/four-bar horizons and three
predeclared full/remove-persistent/remove-transitory variants are all disclosed.
No parameter search, model inversion, audit winner or restoration of a closed
forecast is permitted. Closed BDP1/AIP1/SQP1/etc remain byte-for-byte unchanged.

First report development absolute movement distributions. Amplitude exceeding
costs does not establish predictability. Then evaluate all causal forecasts and
Brier scores against the zero-drift baseline without a2-SE admission prerequisite.
Online model weights use only earlier one-step predictive likelihood, never later
profit. Missing future target prices cannot suppress an earlier forecast. An
observed exact target close may label terminal return while intermediate missing
bars remain a separately reported unknown risk path. No such path certifies DD.
Known phase deadlines and weekend exit clocks prospectively limit economic plans;
all predeclared weeks remain, including zero activity. No HARD21 activity is forced.

The same26/13/13-week calendar is globally exposed development. The final13 weeks
are an exposed chronological audit, not independent confirmation.52 weeks are not
12 calendar months. All288 group/variant combinations and three economic cost
cases remain visible. Primary selection-only adverse support can justify a
separate common-capital execution-priced followup; it is not statistical or
trading qualification. Ablations compare the same forecast opportunity calendar,
not a claimed financed marginal portfolio contribution.

## Observed and estimated costs

One causal route-local quote is reconstructed per original fixed development cost
window. Its spread is observed; contemporaneous market prices do not certify that
current commission or financing tariffs applied historically. The model uses
instrument/hour/volatility cells when sample/date support permits, otherwise
explicit hour or instrument fallback. Cell means, empirical tails and uncertainty
of date means are reported. Sparse dates do not establish independent samples,
representative annual tail coverage or a distribution-free guarantee.

Every strategy-cost calculation is CONDITIONAL_COST_MODEL. Central mean, adverse
p90/mean-plus-uncertainty and stress2x-max spread scenarios remain separate.
Current commission floors/rates, conservative conversion wedges and daily funding
are explicit. Slippage combines a declared spread multiple and a one-second
volatility/latency proxy per side; no execution slippage was measured. Stress is
a scenario, not an asserted upper bound. Missing funding units/schedule cannot
become admissible zero finance. Current directional debits are charged at3x per
current-schedule crossing; credits are not presumed persistent income.

BID-close return proxies pay ONE modeled spread (entry for a long, exit for a
short), plus separate commissions/slippage/funding/conversion. There is no extra
spread charge on a quote-side fill because no such fill is fabricated here.
Nominal bar-end availability and latency proxies are research assumptions, not
verified historical execution clocks. All economic proxy results remain unfunded
bps; they must not be summed into EUR200 profit or completed round trips.

The one existing orchestrator, funded ledger and session remain intact. New native
research components share C# but do not submit orders or enable Cloud trading.
Any promising mechanism needs common-capital sizing/FX/margin/holding-risk replay,
prospective reference-policy comparisons and genuinely untouched confirmation.

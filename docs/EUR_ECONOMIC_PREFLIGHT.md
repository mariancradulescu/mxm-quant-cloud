# EUR feasibility and PR #264 availability diagnostic

## Frozen equity result and availability

The [original PR #264 receipt](EQUITY_CLOCK_PAYOFF_RESULT.json) is immutable.
This postclosure diagnostic reconstructs the original decision ranks solely to
measure coverage. It preserves cohort, choices, timestamps, training and exit.
It introduces no policy, sizing, new outcomes, or collection for that study.

| Evidence required after decision | Clocks | Model gross bps | Pooled gross bps | Paired increment bps |
|---|---:|---:|---:|---:|
| Selected model path | 2,168 | -1.7679 | — | — |
| Both selected paths | 2,117 | -1.8456 | -1.9324 | +0.0868 |
| Both paths and every uniform candidate path, original comparison | 1,686 | -2.3274 | -2.9345 | +0.6071 |

Of 2,340 scheduled clocks, 115 lacked a decision and 57 of the 2,225 decision
clocks lacked the model's future path. Requiring all uniform paths removed
431 otherwise comparable clocks from the paired sample. A uniformly selected
name has an average 1.74% missing-path probability over the original decision
clocks. Its full-calendar gross remains unknown. The paired comparison is
conditional on two realized paths and remains a coverage diagnostic. No
missing paths were assigned a return and the exact policy remains closed.

The initial report's zero-cost inference applies to the observed
normalized-return average. Each position's signed gross depends on the
actual price change, contractual volume and the currency conversion at
valuation. The average bps sign does not determine the sign of the sum in EUR
for differing exposures. The published margin probes and price bars do not
establish matched own-contract volume, EUR conversion and execution costs
on the PR #264 opportunities. Gross and both NET figures in EUR stay unknown.

## Compare the next research routes in euros

The calculation joins the conserved 60-minute amplitude distribution and
reference minimum notionals in MSP1 to the matching BDP1/AIP1 modeled base
cost envelopes. Use one historical minimum position per row. The indicative
EUR move is the published absolute move bps times reference notional divided
by 10,000. The source's reference notional and return distribution are
summary observations at different clocks. The result measures movement scale,
with no forecast, executable payoff or matched tariff. The stress column is
twice the old modeled round-trip cost, a named scenario. The separate partial
friction calculation in the JSON gives transparent spread, commission and
slippage-multiple approximations. It excludes conversion, funding, diffusion
slippage and the adverse commission maximum.

| Route | Reference nominal EUR | Minimum margin EUR | 60m median / P90 absolute move EUR | Base / 2x cost EUR | Gross bps for 1 EUR above 2x cost |
|---|---:|---:|---:|---:|---:|
| AUS200 | 556.72 | 27.50 | 0.50 / 1.59 | 0.34 / 0.69 | 30.35 |
| US500 | 594.99 | 33.89 | 0.46 / 1.74 | 0.13 / 0.26 | 21.19 |
| GER40 | 2,494.12 | 129.17 | 2.59 / 9.19 | 0.62 / 1.24 | 9.00 |
| NAS100 | 2,254.92 | 126.50 | 2.32 / 8.64 | 0.43 / 0.87 | 8.29 |
| JPN225 | 3,130.71 | 177.95 | 4.88 / 16.62 | 1.28 / 2.56 | 11.36 |
| XAUUSD | 4,574.62 | 175.58 | 7.56 / 24.90 | 1.49 / 2.98 | 8.69 |

The 1 EUR example compares the cost and exposure scales. It is not a
promotion threshold or expected NET. All twelve routes are retained in the
[aggregate receipt](EUR_ECONOMIC_PREFLIGHT_RESULT.json). Later observed
SEM1 contractual units, steps and margin are recorded separately where
available. For example, NAS100 was 0.1 units with 126.90 EUR buy margin.
This later snapshot does not retroactively price the earlier moves.

## Research allocation

Prioritize evidence for GER40 and NAS100 over repeating a low-exposure
US500 filter. Both have a useful EUR movement scale at lower initial margin
than XAUUSD and JPN225. Concurrent minima sum to 255.67 EUR in the source
scenario, leaving only 44.33 EUR before costs and floating losses. At a
210 EUR static equity scenario they cannot be held together at those minima.
Investigate one funded leg at a time and test any peer information without
assuming a second position or diversification credit. US500 and AUS200
remain lower-margin comparisons. The 17 US-24 routes remain in the universe.
Their small margin probes alone do not rank them on EUR economics.

Before committing to a predictor in the European/US session overlap,
reconstruct aligned GER40 and NAS100 source clocks, legal volume, notional,
quote-to-EUR conversion and exact cost evidence from conserved originals.
Check whether the proposed feature adds information beyond the target's own
return and the broad index, and whether the signal clocks support funding,
price coverage and meaningful activity. Where exact quotes or contracts are
missing, recover the missing source field only if it could change the
economic decision. The movement scale in this table warrants checking that
evidence. It cannot establish the viability of a particular predictor.
No predictor was fit or selected on realized trading returns in this
intervention.

For future evaluations record decision eligibility independently from future
valuation, keep missing outcomes and their exposure visible, and report
matched and available counts by policy. Use exact physical volume, price
change, conversion, spread, commission, slippage and funding before claiming
EUR NET. Then evaluate cash, financed reference policies and funded marginal
contribution on the existing common C# ledger, with time in margin and
floating risk. This report made zero broker requests and produced zero funded
trades or independent confirmation.

Provenance and reproduction:

- [PR #264](https://github.com/mariancradulescu/mxm-quant-cloud/pull/264)
  and the original [MSP1 receipt](MSP1_AUTHENTIC_CONDITIONAL_RESULT.json.gz).
- Source runs [41724643418](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41724643418),
  [41735441128](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41735441128)
  and [41790872494](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41790872494).
- Run `python -m research.eur_economic_preflight /path/to/original.zip /tmp/eur-preflight.json`
  from repository root with Python 3.12 and NumPy 2.3.5.

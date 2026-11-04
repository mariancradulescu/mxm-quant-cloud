# RCP1 — causal delayed-entry and existing-exposure portfolio economics

OWNER authority: [OWNER v2.0](OWNER_SPEC.md). Frozen results on globally
exposed historic Pepperstone market data; **not** a broker-funded trading
certificate. The original [pre-registered protocol](../research/rcp1_protocol.json)
(SHA-256 `183d723f01556c1c8b81ec88be8a6c0126c17ccb7e65e375665b71ff6b8c1a91`)
was not changed after scoring.

## Authentic execution and distinct economic premise

[Actions #41837460057](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41837460057)
completed SUCCESS, using the original BDP1 #41724643418 and AIP1
#41735441128 sealed authentic Pepperstone LIVE read-only source. The original
836,087 genuine M5 OHLCV/tick-activity bars over 12 broker instruments and
166 development BID/ASK/current-tariff cost observations were cryptographically
reconstructed. No broker requests, historical hypotheses reexecuted, orders,
Cloud activation or new services.

RCP1 is *not* an IPF1 tuning variation. It studies three newly predeclared
event-state hypotheses with zero-prior, causally matured, discounted Bayesian
slope estimates: range compression/release; cross-market dispersion repair;
and asymmetric wick/volume pressure relaxation. Each is measured on 4-hour,
24-hour and 120-hour causal information, with 4h, 24h and 72h forward
windows. A total of 1,314 decision clocks was considered; 1,100 had
eligible matured-model candidate forecasts. The exact 35,694 proposed
historical forecast outcomes included 10,059 unknown next-bar or later
outcomes, never filled with zero.

**Prospective execution corrections**: the signal uses only completed bars
known at its decision clock. The research **model fill** is the closing
price of the independently observed M5 bar *five minutes later*, never the
signal-bar close; no next bar means no fill. Joint scenarios passed into the
*existing native C# OpportunityOrchestrator/AdaptivePortfolioRisk* account
for every currently open position, including aligned historical forward
loss, favorable peak and shared margin. During modeled holdings, equity is
sampled at available hourly marks and observed exit clocks. An absent
source cannot certify unknown equity; the common capital never resets.
These are conditional bar-market accounting assumptions, not real broker
entry/exit fills, guaranteed within-bar risk bounds or audited historic
contract tariffs.

## Predictive information versus reference

All twelve instruments and all three horizons (36 fusion cells per
chronological phase) were scored against zero-drift MSE, prior-24h momentum
MSE and neutral directional Brier 0.25. Positive cell counts:

| Phase | Better MSE than zero drift | Better MSE than prior momentum | Better Brier than neutral |
|---|---:|---:|---:|
| Development | 6 / 36 | 32 / 36 | 10 / 36 |
| Selection | 10 / 36 | 33 / 36 | 10 / 36 |
| Globally exposed audit | 12 / 36 | 34 / 36 | 12 / 36 |

These are descriptive, not independent superiority tests; prior-momentum
is an intentionally weak fixed reference and does not itself prove alpha.
Each of the last 26 weeks was previously research-exposed in other studies,
so the apparent audit skill cannot be called untouched out-of-sample
confirmation.

## Modelled shared-capital portfolio and exact ablations

The five counterfactual books each use one **separate alternative**
continuous EUR200 starting capital, not pooled deployable wallets. The
full policy is the sole intended whole-system baseline; counterfactual
differences are path dependent and **not** additive family alpha.

| Predeclared modeled EUR200 policy | Complete modeled round trips | Conditional total EUR | Sampled maximum drawdown |
|---|---:|---:|---:|
| FULL three families | 3 | **+12.239475** | 4.9831% |
| FULL_STRESS (worse cost scenario) | 2 | +7.763229 | 5.0870% |
| WITHOUT_RANGE_COMPRESSION_RELEASE | 3 | +12.239475 | 4.9831% |
| WITHOUT_RELATIVE_DISPERSION_REPAIR | 1 | +0.988275 | 5.0839% |
| WITHOUT_TAIL_VOLATILITY_UNWIND | 2 | +11.251200 | 4.0803% |
| FLAT_NEUTRAL | 0 | 0 | 0 |

The FULL modeled book begins with 200 EUR at selection and does **not**
reset for the audit phase. Two hypothetical round trips in selection
yielded +5.090493 EUR, and one in the exposed audit +7.148982 EUR,
ending flat at **212.239475 EUR**, with no unresolved model exposure.
The three modeled outcomes were NAS100/4h +4.102219 EUR, USDJPY/24h
+0.988275 EUR, and USDJPY/24h +7.148982 EUR, after the declared
adverse statistical cost and current-term financing assumptions.
The C# native selector was called **676 times** for each active policy.
Maximum simultaneously **modeled** positions was **one**, not proof of
concurrent multiasset execution; maximum modeled current-term margin
was 126.50 EUR. The modeled cash identity reconciled, and neither
holding exit-source gaps nor unpriced sampled hourly marks arose in the
three admitted FULL episodes. None of this certifies actual broker
execution.

**HARD21 system-level**: exactly 13 selection weeks plus 13 exposed
audit weeks were treated as eligible according to the predeclared
calendar, irrespective of outcomes. **0/26 weeks** recorded at least
21 complete modeled system round trips; the minimum was zero. No
family-specific quota or artificial trades were imposed.

The native marginal utility screen rejected many proposals for substantive
reasons: 60,642 estimated forecast-to-cost cases beneath adverse friction;
3,069 missing aligned joint historic states; 547 missing delayed-entry
historical paths; 61 current-minimum-margin failures; 370 nonpositive
uncertainty-adjusted native utilities. These are pre-admission counts
across overlapping candidates, not independent missed trades or P&L.

## Exact rejection of qualification

**CLOSED_EXACT_MODELED_POSITIVE_THREE_TRADES_HARD21_NOT_SUPPORTED_NO_EXECUTION_OR_INDEPENDENCE.**
Three favorable modeled outcomes cannot demonstrate statistical or
economic edge; all 26 system weeks failed HARD21. Source-exposed
confirmation, authenticated historic entry/exit BID/ASK fills, funding
terms and conversion history, continuous equity extrema and final
native Cloud recovery remain absent. The FULL_STRESS alternative
remaining conditionally positive is not an independent replication.
Neither the positive FULL scenario nor the most favorable leave-one-out
policy is a basis for promotion, margin relaxation, inverse signals or
after-the-fact model refinement.

The entire original public-only output (432 skill-group rows, native
selector/cash diagnostics and counterfactual results) is frozen in
[Actions artifact #13326782174](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41837460057/artifacts/13326782174).
Its GitHub ZIP SHA-256 is
`9c056776d363c3042adc29fe0943a88186295e55c5a67e7e87a00597c6714d34`;
original uncompressed JSON SHA-256
`e2650ca0c591b4b591be1c700c9a490470f661b1d7ad2651e95689651eaa2e29`.
The original artifact is subject to GitHub retention (90 days);
this public sanitized summary and original hash references are
conserved permanently in the repository. The user must not be
required to run GitHub operations or supply broker credentials.
No LIVE/DEMO order or Cloud activation is authorized.

The economic implication is **frequency and support**, not a mandate
to tune the exact strategy. Further work must address genuinely distinct,
causally justified sources/mechanisms and whole-system capacity.
Native nonflat monetary restart recovery is still not qualified.

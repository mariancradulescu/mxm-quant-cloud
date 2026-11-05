# IES1 — authentic exposed economic triage and native funded boundary

Authority: [OWNER_SPEC.md](OWNER_SPEC.md), OWNER v2.0. Original [GitHub Actions run #41991415344](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41991415344), original artifact `13397519721`; unchanged original `integrated-economic-surface.public.json` SHA-256 `b6c608ea8346270db3669c2d95403feaf468d1d2f1bb28b4eed592d0888f9bb1`. The [compact receipt](IES1_AUTHENTIC_EXPOSED_RECEIPT.json) is separately SHA-256-pinned in the existing global `frozenFileSha256` gate. Its values are a verbatim-subset summary of the originally exposed report; no new prediction or closed-model scoring was executed.

## Authentic original account and observability

The original encrypted, read-only Pepperstone-associated cTrader Open API BDP1 source (`41724643418`) was cryptographically reconstructed for six previously research-exposed instruments: EURUSD, GBPUSD, USDJPY, AUDUSD, USDCAD and XAUUSD. There are 441,240 complete genuine M5 source bars across 52 *already exposed* weeks, plus 18 original development spread-clock attempts for each instrument.

- **108** possible instrument–fixed-clock quote observations; **78** satisfied the paired BID/ASK, EUR conversion timing and explicit contract-term screen; **30** are unknown or unsuitable, not zero spreads or free execution.
- **8,747** completed selection-phase prior-hour-sign/next-hour-sign pairs across all six instruments. Full chronological 26/13/13 windows remain exposed. This is *not* an independent alpha experiment or a prospective selected trading signal.
- The old broker symbols include per-contract minimum volume/margin and four distinct commission calculation types. The historical bid/ask samples and captured *current-at-source* contract terms are mixed for a strictly illustrative EUR quote-side commission breakdown; historical tariff stability, minimum PnL conversion fees, funding, dynamic leverage evolution, latency, slippage and fills are **not** proved.

## All-symbol causal benchmark and cost evidence

The predetermined predictor is the sign of the prior completed hour; the target is the sign of the following complete hour. It competes with an explicit neutral 50% forecast. Brier skill is negative for each of the six, but the predictor is deterministic 0/1 and therefore poorly calibrated by construction; do not interpret this specific probabilistic comparison as impossibility of all other probabilistic forecasts. The directional gross mean in the *already exposed* selection period is negative for every instrument.

| Symbol | Causal selection pairs | Mean next-hour directional gross (bps) | Auth. paired EUR-route cost clocks | Observed spread / current commission illustration (bps) | Current minimum margin (EUR) |
|---|---:|---:|---:|---:|---:|
| EURUSD | 1,484 | -0.199 | 17 | 0.091 / 0.516 | 33.33 |
| GBPUSD | 1,464 | -0.043 | 12 | 0.187 / 0.448 | 39.96 |
| USDJPY | 1,488 | -0.396 | 12 | 0.192 / 0.600 | 29.79 |
| AUDUSD | 1,486 | -0.314 | 12 | 0.158 / 0.875 | 31.13 |
| USDCAD | 1,481 | -0.245 | 13 | 0.206 / 0.600 | 29.79 |
| XAUUSD | 1,344 | -0.223 | 12 | 0.659 / 0.150 | 175.58 |

Amounts in bps are **not realized EUR or all-in cost histories**. Gross closes are not executable entry/exit prices. Applying illustrative spread+current commissions cannot turn negative benchmark gross into demonstrated alpha. Actual total financing/FX/slippage and independently confirmed NET remain unknown.

## Common-capital economics and shared C# path

Every observed current minimum margin is below the unique EUR200 opening capital *individually*. Their additive total is EUR339.58, meaning minimums **cannot all be held simultaneously** under a naïve full-additive, no-offset margin assumption; broker netting/hedge concessions and timing have not been certified. XAUUSD EUR175.58 plus an individually cheapest FX EUR29.79 gives EUR205.37 under that same conservative simplification, before fees, floating P/L or risk reserves. These are *static capacity descriptors*, not a real funded portfolio replay.

**Economic funnel at IES1's exposed diagnostic stage:** six source-eligible instruments → six with observed current minimum margin below EUR200 → six with some usable historical quote observations and current contract fees → zero supported directional gross/neutral benchmark candidates → zero forwarded to a priced shared-financed allocation. No artificial entry is forced and no counted HARD21 trades are fabricated. Actual funded incremental NET is **uncomputed**, rather than zero-profit certified.

`NativeFundedSession.DecideResearch` now accepts optional `SpecialistEuroEvidence[]`, where present, routes a complete aligned set through `ResearchSpecialistAdmission.Estimate` *before* the **same** `OpportunityOrchestrator.Estimate`, and creates modeled ledger intents **only** for conditionally admitted opportunities. Negative gross, missing benchmark evidence, unknown costs/financing and contradictory exposure prevent new modeled requests; previously held/pending reservations still come from the **same** `NativeFundedLedger`. No second allocator, account or Cloud order capability has been added.

Legacy conditional decision input (null specialist evidence) retains its exact original hash and existing research meaning; prior frozen protocols and results are not rescored. New specialist evidence is required only for the **opt-in prospective** integrated path. Neither successful synthetic funded ledger tests nor an all-negative authentic IES1 funnel qualifies trading, demonstrates 21 *completed financed* round trips per eligible week, certifies 30% continuous liquidation-equity drawdown, or provides independent holdout NET.

**Economic next admission condition:** a genuinely new, predeclared causal information source/hypothesis on nonexposed decision outcomes, with enough complete quotes, verified EUR fee/FX/funding handling, scenario uncertainty, broker minimum volume and common-portfolio marginal NET. The IES1 52-week calendar cannot be relabeled as untouched confirmation by selecting another feature or instrument afterward.

No new broker request, LIVE/DEMO order or cTrader Cloud activation occurred. No external service, new account, or permanent Python component is introduced into the final cBot.

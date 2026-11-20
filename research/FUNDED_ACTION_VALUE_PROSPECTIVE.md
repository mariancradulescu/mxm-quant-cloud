# Funded action value research

Authority rests with `docs/OWNER_SPEC.md`, PR #415 and Issue #393. The pilot uses the existing C# observation-only architecture and a single EUR300 book per comparable policy. Research forbids broker orders, Cloud activation, retrospective tuning and replay of closed studies.

## Original W44–W45 evidence

Actions [#44776057509](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44776057509), [artifact #14649839931](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44776057509/artifacts/14649839931), marker `269573d764fae9653441364c948bae84f3f5c3b4`.

| File | SHA-256 |
| --- | --- |
| Original ZIP | `38124fd93f9aaf354723f27d2cc0d91ffbac5c61eff85b439eaec07df361768b` |
| `economic.json` | `6a222965aed89a962f29a41b14ba923ea97b1dc96b9e18ac09b36cedff7d60df` |
| `receipt.json` | `7618db36eb904225a7b63523c0ec7def7070ec65a0e07d0693abc5f5dd358016` |

Read-only verification matched all 18 cash, cost, close and weekly totals. The largest absolute decimal reconciliation residual was 6.52 × 10⁻²⁶ EUR. All 18 books were flat with no intent at the boundary. CASH led every active policy on both frictions.

| Policy | Central NET EUR | Adverse NET EUR |
| --- | ---: | ---: |
| CASH | 0 | 0 |
| FIRST | −20.2297 | −30.0496 |
| RANDOM | −21.1046 | −28.1804 |
| TREND | −10.9482 | −13.8028 |
| REJECTION | −10.5944 | −17.9959 |
| EXHAUSTION | −2.2928 | −7.9799 |
| COMBINED | −20.4560 | −33.2896 |
| COMBINED_RANDOM | −15.5162 | −29.1318 |
| COMBINED_WITHOUT_EXHAUSTION | −24.5102 | −33.0565 |

| Adverse book | ISO week | Complete closes | Gross EUR | Cost EUR | NET EUR | Target exits | Invalidation exits |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EXHAUSTION | W44 | 73 | +21.3851 | 9.0559 | +12.3292 | 16 | 40 |
| EXHAUSTION | W45 | 91 | −10.0160 | 10.2932 | −20.3091 | 5 | 55 |
| COMBINED | W44 | 161 | +26.4245 | 21.0762 | +5.3483 | 45 | 65 |
| COMBINED | W45 | 165 | −15.8892 | 22.7487 | −38.6379 | 26 | 73 |

The adverse COMBINED NET fell by 43.9863 EUR. Gross explained 42.3137 EUR of the drop and costs 1.6726 EUR. Target-close NET fell from +38.511 to +9.930 EUR, and invalidation NET moved from −30.145 to −40.040 EUR. XAUUSD moved from +14.884 to −13.734 EUR and EURUSD from +0.103 to −12.442 EUR. These are realized attribution results. The original observations cannot identify an ex ante regime filter or isolate a counterfactual management outcome at an individual exit.

COMBINED adverse recorded 597 proposals, 414 financeable offers, 371 intents, 45 pre-fill invalidations and 326 complete funded closes. The common ledger rejected 82 joint-risk, 40 same-symbol exposure, 43 unknown-mark and 3 reserved-margin cases, in addition to geometry or source failures. Forty-one clocks had funded choices on different symbols. COMBINED underperformed the fixed hash control by 4.1578 EUR and FIRST by 3.2400 EUR. The financed family ablation gave +4.0542 EUR central and −0.2331 EUR adverse. The attribution supports studying action selection and full position handling. It establishes neither the effect of retrospectively removing a week nor a causal regime boundary.

COMBINED adverse had 71 initial-risk overruns, 17 incomplete position paths, 10 unverified historical financing exposures and 14,527 held clocks with unknown equity. Maximum observed margin was 201.5375 EUR and the sampled drawdown was about 13.11%. Continuous floating drawdown and broker-certified NET remain unverified.

## Prospective hypotheses

- **Continuation.** A confirmed release may sustain directional travel when closed-bar structure, activity and relative motion agree. Target geometry and conditioning on available margin alone cannot demonstrate a positive net payoff distribution.
- **Failed auction.** Rejection and impulse exhaustion may signal repricing after a failed boundary attempt. The benefit should survive complete executable lifecycle costs, a delayed-entry alternative and an adverse full-book comparison.
- **Management.** Once a new witnessed M15 close arrives during a position, the state of the book and the change in price behavior can identify when releasing capital via an exit is worth more than keeping the position under ordinary protection. Compare the two complete funded continuations.

The detectors are the existing three families. Rule parameters, directions and costs are frozen. A market observation may furnish no actionable entry. The policy can choose any funded offered LONG or SHORT, or wait. The existing mandatory stop, target, invalidation, margin and drawdown controls and ordinary protection/reduction continue to run. The learned management action compares CLOSE with KEEP. A learned partial reduction or atomic position replacement requires additional paired evidence.

## Calendar and source admissibility

| Use | UTC interval, end exclusive |
| --- | --- |
| Fit | 2026-11-23 to 2027-01-04 |
| Embargo | 2027-01-04 to 2027-01-11 |
| Calibrate | 2027-01-11 to 2027-01-25 |
| Embargo | 2027-01-25 to 2027-02-01 |
| Evaluate | 2027-02-01 to 2027-03-01 |

All four evaluation ISO weeks are predeclared. The roster is EURUSD, GBPUSD, XAUUSD, SpotBrent, US500 and AAPL.US, the previously source-qualified multi-class roster. Every policy sees the same available subset. The historical adapter requires an authentic original custody receipt, witnessed closed M1/M5/M15/M30/H1, as-of paired BID/ASK and EURUSD conversion, known legal minimum margin/commission terms and causal timestamps. A term snapshot observed after a decision cannot supply its funding. Warmup may include prior causally published bars. Complete path evidence and historical financing are explicit checks. H4/D1 require separate authentic session and publication evidence. The runner records source/protocol SHA-256 and observed coverage. Custody receipts must attest actual provenance and whether test dates were exposed in another study. The Replay CLI checks the preregistered calendar and chronology and cannot attest external custody by itself.

Acquire this cohort read-only under the existing source custody controls when the relevant observations exist. Secure prospective terms before they are needed. Snapshot data alone does not attest historical fees or financing continuity. W44–W46 and all exposed prior outcomes are excluded from the fit, calibration and evaluation intervals above.

## Paired action labels and model

Each label starts from two copies of the very same pre-action C# ledger and orders. The pilot builds an intraday common-book state on FIRST from EUR300. Probe at the fixed first management offset after each UTC hour. Choose at most one funded entry and one eligible held alternative by a fixed hash, independently of their eventual outcomes. A forced research action still requires the normal funding and price gates.

- Entry labels compare admitting the available offer against waiting at that observation. Both branches follow FIRST on subsequent observations. The book can take other funded offers and the two trajectories can compete differently for capital.
- Management labels compare an optional native close intent after established protection decisions against keeping the position with the ordinary handling rules. Other positions remain in the common book.

Label the difference in total cash at the first later observed clock when both books have closed positions and intents. Both branches include later entry opportunities, fill rechecks, cash, sizing, protective exits and costs. A day boundary censors an unsettled pair. Missing held or pending path evidence and unverified financing prevent training on that pair. The day boundary places no timed exits. These local policy comparisons condition on the pilot continuation. Policy shift is checked in the separate continuous funded evaluation.

The model groups actions by kind, family and offered side. Features use signed normalized M5/M15/M30/H1 displacement, recent versus earlier M1 activity, other symbols' observed H1 state and its availability flag, UTC time, booked margin/positions/intents, allocated risk and the action's actual resource demand. Entry features also describe executable spread, planned target NET per stressed risk and the count of contemporaneous alternatives. Holding features include liquidation, excursion and age. There are no future bars or outcome-dependent feature transformations.

The existing C# nearest-neighbor distribution estimates paired returns scaled by reserved risk. It requires at least 12 samples on at least four fit days, caps at eight per day and 48 in total, and uses inverse squared-distance-plus-one weights. Separate calibration uses equal-weight daily residuals to apply a mean correction and an empirical lower decision value based on the tenth percentile of daily residuals. At least four calibration days are required per action group. This bound is a decision rule. Coverage, mean error, Brier, probability bins and matched-cohort forecast error test its quality.

A calibrated positive lower value admits a candidate, ranking competing positive candidates on the mean incremental EUR estimate and fixed hash for ties. Close-versus-keep uses the same criterion on a newly observed M15 holding state. The allocator maintains the existing capital and fills. A missing or nonpositive estimate makes WAIT/KEEP available.

## Funded controls and interpretation

Run complete continuous EUR300 books under central and adverse frictions for CASH, FIRST, the deterministic hash, the pooled no-context model, a training-week feature reassignment placebo, entry valuation alone, full contextual valuation and full contextual valuation without exhaustion offers. Both placebo and pooled scores pass the same calibration machinery. Hold out all labels settled at or after the relevant boundary. Compute forecast metrics overall, on common scored labels, and separately by action group and M15/H1 alignment. Only the full-book difference measures incremental economics.

Prespecified primary comparisons are adverse contextual valuation versus CASH and FIRST. Report the complete modeled NET deltas when both terminal books have resolved obligations. The paired weekly sign-flip check is descriptive and assumes exchangeable signs. It requires all four weekly cash endpoints to be flat and financing/path evidence for intervening settlements. Report one-sided probabilities and Holm at 5% for the two tests. The minimum attainable p-value with four weeks is 1/16. The pilot therefore determines direction, effect size and sources of failure, with at least 12 independent months required for qualification.

Report sampled floating drawdown, unknown exposure marks, weekly complete funded HARD21, margins, risk, concentration, realized NET and censure for every portfolio. A positive modeled pilot alone cannot authorize deployment. CASH remains an economic alternative. Missing support remains a reported diagnostic even when the evaluator can run the financed controls.

## Common Replay and observation adapter

`Mxm.Replay --funded-action-value` reconstructs chronological Ucp1Frames from the authorized source. `Mxm.Cloud` uses the existing structural observation mode and an optional frozen action model snapshot to call `NativeUnifiedPortfolioEngine.Advance` through `NativeUnifiedCloudParityAdapter`. The observation adapter reads the available current inputs with the official [per-symbol GetBars](https://help.ctrader.com/ctrader-algo/references/MarketData/MarketData/GetBars/) and [GetTicks](https://help.ctrader.com/ctrader-algo/references/MarketData/MarketData/GetTicks/) APIs. Native bar events attest the previous bar at the next bar opening. Read [Spotware bar events](https://help.ctrader.com/ctrader-algo/documentation/cbots/cbot-bar-events/) for the publication convention and [Cloud requirements](https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/) for the supported compilation model.

Feature computation, forecast, admission, management and settlement run in Core for both adapters. Identical-frame tests verify modeled fills, exits, receipts and ledger hashes. Comparison of the actual historical and current platform feed observations remains separate and requires matched read-only source evidence.

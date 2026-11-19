# UCP1 original unified C# complete-policy economics — immutable readback 19 Nov 2026

## Authority and custody
OWNER after independent SIR1 audit Issue #393 #7006732174. **Original new** complete portfolio policy UCP1 distinct from closed SIR1/NPI1/MVO1/SPE1; all older study results unchanged. Prospectively frozen protocol-only ancestor **e67163959208982aceb1bf98e6f7296b460eb3ae**, before new policy code and original results. Product Core/Replay/Cloud PR **#399** merged **c09c09b2db3ae8150b3709190360d67dee457163**, OWNER one-shot main trigger **fca2b93465a28798f98d55beeaa8ee8a281ce938**. Same-input Core↔Replay↔compiled Cloud adapter native verification Actions **#44511053080 SUCCESS**, official cTrader CLI **#44511052941 SUCCESS**. New source original protected Actions **#44511373341 SUCCESS**, both verify and original C# financial job. **Original artifact #14524124345**, `ucp1-original-complete-unified-economic-public`.

Original ZIP members and SHA-256 independently checked:
- `native-economic.json` **141,176,144 bytes**, SHA-256 **a934d4c978e7b1979cc7df57500546124908dd2413b1f006eb97b2ec8b788e6e** — matches `receipt.json.NativeReportSha256`.
- `receipt.json` **1,270 bytes**, SHA-256 **7d6c998c4e647854e13867e54fa41c18ac3facb12554da88e56620d3c67a2fcb**.
- Genuine original OEI1 encrypted source run #44247979857, verified plaintext SHA-256 **32f3401cfede314a7a3b110c0636166a2680b2f440e3428dd5c1b70f12acaf1b** and ciphertext SHA-256 **c28a69c2ee738f209cfd025a7424377629c9ac59f695c2b87422c2577c4d4c86**. Python only original read-only custody/as-of observation serialization. One C# engine `NativeUnifiedPortfolioEngine.Advance` is economic authority; no Python trading decision. ZERO original broker requests/new collection, ZERO orders, ZERO Cloud activation, ZERO original closed-study relaunch.
- Original source span 2026-08-17 00:00 through **2026-11-09 00:00 UTC**, 60 recorded daily windows, **7,142 distinct observed minute clocks**, 7,140–7,141 genuinely paired BID/ASK as-of minute marks *per* EURUSD, ETHUSD, SpotBrent and US500 (28,562 total), but only within restricted 13:30–15:29 UTC sampling windows, not full sessions. C# generated completed **sampled midpoint M5 proxies** (1,380–1,381 per symbol) and M15 proxies (420–421 per symbol). The proxy highs/lows are extrema of sampled as-of MID observations, NOT original full tick/OHLC high/lows. Only SpotBrent, US500 and ETHUSD contributed completed selected trades; EURUSD served cross conversion/support, no completed trades. All timestamps/stages are historically **GLOBALLY EXPOSED**, NOT independent.

## CRITICAL ORIGINAL SOFTWARE CONFORMANCE DEFECT (not post-hoc profit tuning)

The EXACT original first SOURCE run was made on commit fca2b934 and cannot be silently reclassified as a faithful **max TWO funded concurrent position** book:

| Original policy | Observed MAX simultaneous positions | Observed sampled clocks with 3 positions |
|---|---:|---:|
| JOINT | **3** | **247** |
| TRANSITION_ONLY | **3** | **155** |
| REPAIR_ONLY | **3** | **24** |
| LONG | **3** | **264** |
| SHORT | **3** | **258** |

This conflicts with prospectively frozen UCP1 **maximum two** slots, even though the capital and modeled margin might have financed three. Therefore the original conditional EUR P&L and model trips are FACTUAL outcomes **under a violated position-cap assumption**, NOT a compliant 2-slot policy or qualified HARD21. No edits to, re-tuning of, or re-running of the original economic results occurred.

Separate pre-original-outcome correctness issue: `REQUEST_CLOSE` originally double-counted an already-held capacity slot. It was disclosed **before** original run outcomes were available in Issue #393 comment **#7007379126**, fixed prospectively in PR #400 merged **b6bedea314b73bfcf3e1bdebd510c2f90347e4be**, verified UCP1 CI #44512434832, official cTrader CLI #44512434591. Original run still used older exact code.

The newly observed overcapacity defect above was discovered by independent programmatic inspection **after** receiving the original artifact. Prospectively froze protection in **b748e4d6be31b8d5dfab433fcf21479c5cb56ee4**, implemented a strictly optional `MaximumFundedOpenSlots=2` common NativeFundedSession allocator cap after full causal ranking, before ANY modeled REQUEST_OPEN, with explicitly declined overflow; old uncapped receipt hash unchanged. PR **#401** merged **9ebeb73b0ad769314b6d8165e1e9919800b70e5f**, CI UCP1 #44514928658 SUCCESS, official cTrader CLI #44514928734 SUCCESS. **This prospective code fix DOES NOT replace or certify the original results**. No new original SOURCE evaluation on post-fix logic authorized or executed.

## Original conditional native EUR300 economic outcomes

Each named policy is a SEPARATE EUR300 hypothetical financed model account, never an independent symbol pocket, and NEVER aggregated across policies. Broker actual historical fills/commission/swap/FX margin continuity and intragap equity missing; all outcomes quote-bound model P&L BEFORE unverified historical financing, NOT certified NET broker/adverse NET.

| Policy | Model completed trips | Conditional realized closed model P&L EUR | Final modeled cash EUR | Final sampled model equity EUR | Win rate | PF | Mean net/trip EUR | Payoff | Mean R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| JOINT | 445 | **−12.51076286** | 287.48923714 | 287.48923714 | 25.62% | 0.9012 | −0.02811 | 2.6087 | −0.17894 |
| TRANSITION_ONLY | 249 | **+1.56793787** | 301.56793787 | 301.56793787 | 32.13% | 1.0146 | +0.00630 | 2.1434 | −0.13084 |
| REPAIR_ONLY | 466 | **−38.46746249** | 261.53253751 | 261.53253751 | 18.24% | 0.204 | −0.08255 | 0.909 | −0.25 |
| LONG | 586 | **−72.99276021** | 227.00723979 | **226.04025528** (2 still held) | 26.28% | 0.513 | −0.12456 | 1.431 | −0.270 |
| SHORT | 769 | **−44.37614590** | 255.62385410 | 255.62385410 | 19.64% | 0.657 | −0.05771 | 2.677 | −0.229 |
| CASH | 0 | 0 | 300 | 300 | N/A | N/A | N/A | N/A | N/A |

The original native event chains were independently reapplied by C# `NativeFundedLedger` and matched exact cash, pending, position inventory, completed trips and `EventChainHash`; secondary Python analysis of the untouched public original archive recomputed P&L sums directly from all individual `IndividualTrips` for every policy to numerical serialization precision. **There is no broker execution certificate.**

| Original policy | Sampled peak drawdown (NOT continuous) | Maximum sampled margin EUR | Model trips >=21 / observed 12 weeks | Sampled mean MFE / MAE EUR | Net worst / median / best trip EUR |
|---|---:|---:|---:|---:|---:|
| JOINT | 15.436% | 50.32 | 12/12 | +0.3726 / −0.3519 | −6.1501 / −0.0784 / +24.0282 |
| TRANSITION_ONLY | 12.461% | 50.32 | **5/12** | +0.6418 / −0.5347 | −6.1501 / −0.0916 / +24.0282 |
| REPAIR_ONLY | 12.837% | 50.32 | 12/12 | +0.0260 / −0.1246 | −0.8622 / −0.0710 / +1.0582 |
| LONG | 25.957% | 50.32 | 12/12 | +0.1974 / −0.3123 | −8.4195 / −0.0732 / +7.8171 |
| SHORT | 23.250% | 50.32 | 12/12 | +0.1528 / −0.2072 | −6.1501 / −0.0749 / +16.1266 |
| CASH | 0 | 0 | 0/12 | N/A | N/A |

These are model complete trips under current terms and violated max-two slot cap; **NO certified broker-funded HARD21**. The 12 observed weeks W34–W45 of 2026 are NOT 12 months, not calendar-complete authenticated price and account sessions, and not independent confirmation. The original LONG counterfactual retains **two open positions** at last source boundary, so final marked equity is below cash and cannot be treated as all-realized outcome. No broker order/cancel/confirmations were generated.

### Frozen chronological stage results: conditional modeled closed P&L EUR

| Policy | Development (through Sep 27) | Calibration (Sep 28–Oct 18) | Exposed evaluation (Oct 19–Nov 08) |
|---|---:|---:|---:|
| JOINT | −16.5180 (233) | −4.5668 (109) | +8.5740 (103) |
| TRANSITION_ONLY | −7.9569 (130) | −1.6956 (60) | +11.2205 (59) |
| REPAIR_ONLY | −19.8271 (245) | −9.6738 (119) | −8.9666 (102) |
| LONG | −17.1723 (292) | −19.0178 (159) | −36.8027 (135) |
| SHORT | −36.7345 (395) | −9.6454 (183) | +2.0038 (191) |
| CASH | 0 | 0 | 0 |

This is a descriptive split of an already-globally-exposed source, not a blind test. Do not promote positive exposed evaluation JOINT or transition in isolation.

### Critical price-gap and extreme-tail diagnostics, NOT retrospective filters
- JOINT's **84** completed episodes crossing unobserved source windows sum **+23.53712603 EUR**; other **361** no-gap episodes sum **−36.04788888 EUR**. Therefore JOINT aggregate **−12.51076286 EUR** even before historical funding uncertainty.
- TRANSITION_ONLY's **84** gap-crossing episodes sum **+23.53712603 EUR**; its **165** no-gap episodes sum **−21.96918815 EUR**. Its entire apparent positive total **+1.56793787 EUR** is dependent on gap-crossing outcomes: its single largest profit **+24.02823048 EUR** exceeds whole-policy profit, top five wins total **+45.11026314 EUR**. Merely excluding gaps post hoc would be invalid re-tuning. No independent alpha claim.
- REPAIR_ONLY produced **466 / −38.4675 EUR**, all without flagged observed source gaps and negative in **all three** chronological phases, before historical cost uncertainty. Exact policy fails even in its conditional current-cost model.
- LONG no-gap **516 trades / −47.7806 EUR**, gap **70 / −25.2121 EUR**, plus two still held; SHORT no-gap **721 / −68.7316 EUR**, gap **48 / +24.3554 EUR**.
- JOINT contributes exact **249 RANGE_TRANSITION / +1.56793787 EUR** and **196 EQUILIBRIUM_REPAIR / −14.07870073 EUR** under this precise (defective max-three) book. RANGE_TRANSITION separately predeclared, but its tiny positive in-sample model P&L is not a robust cash/broker NET qualification; never reinterpret as a retrospectively fitted winning selector.
- Original JOINT complete modeled exit reasons: **254** `CLOSED_BAR_REGIME_INVALIDATION`, **187** `OBSERVED_PATH_STOP_ADAPT`, **2** `OBSERVED_PATH_STOP_STRUCT`, **2** `OBSERVED_PATH_EQUILIBRIUM`; **zero normal timeout** exits, no fictional intragap stop execution. Simulated local close expiries occurred (2 JOINT; 2 transition; etc.) without position/capital release.

### Scope and unresolved truth
- Exact original event chain hashes: JOINT **3722021690b9fea07d19c76a2227b26514b99366bd641d168ca550876568c7bc** (14,513 native events), TRANSITION_ONLY **050ff4448470e2de1940b3b5f1782c566c7c483ce0ea08b806963b14fb4bca5a** (13,337), REPAIR_ONLY **ad60e5f02469047404ea261d8c2e6b0ba0fdd71a0dfc3173fad6efe29aa6c5c2** (9,938), LONG **0379d7ca9a835676ed7d3e801365f238b2a09c932209daa86e1bad9b42f739ba** (14,601), SHORT **52f2785827b85e2e3ab8c229ff8860fdbbcb6b047016458ebd805446e97d1a07** (14,615), CASH **f6a7bf5bdf1fd4e91860165d45b1e62a4654cf7bd133b378d835d58af9e446dc** (7,142). Total **74,146** event facts across six separate books, plus per-trip receipts and entire sampled equity curve in public artifact.
- Positive output remains **CONDITIONAL MODEL ONLY**, affected by current-as-observed tariff/financing/margin assumptions, original source-window discontinuities, sampled M5/M15 high/low proxies, one model account per policy rather than an actual historical funded Pepperstone cBot, and now-proven max-two concurrent position rule failure. Do not call quote-priced pre-funding model net **broker NET**. Historical financing over gap, full real equity/trade conversion, all real broker fills, adverse true NET, **continuous intra-position floating DD**, and 12 genuinely independent months remain UNKNOWN/UNCERTIFIED.
- cTrader Cloud observation-only build and actual common C# method wiring are shown by CI, but no runtime Cloud has been activated, no real submitted orders/real callback persistence, and Cloud restart historical state continuity is not certified. The current observation-only Bot links one C# Core engine and keeps real broker order/position identity separately; further broker semantic verification cannot be inferred from model-only source.

## Verdict and independent audit handoff
**Accept original UCP1 SOURCE/evidence custody, actual completed modeled C# outcomes and the meaningful integrated economic diagnosis. REJECT UCP1 as a max-two compliant, economically promotable portfolio.** No robust adversarial positive NET vs CASH, no genuine financed HARD21, no continuous DD certificate or 12-month independent confirmation. The observed smallest positive transition is not promotion and its gap dependency is adverse. No historical re-tuning, no second original UCP1 run.

Architect-Coordinator: independently download original artifact #14524124345 / Actions #44511373341 and recompute original SHA and per-trip/cash/weekly aggregates, all 74,146 native events including modeled SIR1 close reissue/expiry, source interval/M5-M15 proxy evidence, exact 3-slot violations and missing real funding, isolation of six EUR300 policy books. Inspect PR400/PR401 prospective capacity guards **without attributing them retrospectively to original run**. Review cTrader real broker/account/position semantics as a separate uncovered authority requiring future authenticated facts. OWNER final decision; DIRECTOR executes and does not trade.

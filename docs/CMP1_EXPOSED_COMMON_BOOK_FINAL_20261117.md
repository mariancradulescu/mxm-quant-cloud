# CMP1 — original executed exposed development result (2026-11-17)

**Exact fixed-policy verdict:** `CMP1_EXPOSED_SHARED_CASH_PROXY_NEGATIVE_NO_NATIVE_NET_NO_PROMOTION`.

This document **records the first original CMP1 economic shadow receipt** and does not change the frozen protocol or the algorithm. The new original study is CMP1 shared policy only. This is NOT a repeat execution of closed AIP1, even though its authenticated **public source observations** are reused. No user trading permissions or Cloud changes are implied.

## Immutable order and custody

- Frozen protocol `research/CMP1_COMMON_CAPITAL_PROTOCOL_20261117.md` first committed at [667e3bd0](https://github.com/mariancradulescu/mxm-quant-cloud/commit/667e3bd001b6c3932cfa5e5775adc24dba90eb09), **before CMP1 code, tests or outcome scoring**. Protocol SHA-256: `706afb898189fe4447eaf9c722b19cf4cc40be35bdea42b189f77e1e93a4ddcd`.
- Original PR [#349](https://github.com/mariancradulescu/mxm-quant-cloud/pull/349); original job [Actions #44026677712](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44026677712), attempt **1**, SUCCESS (six causal and portfolio margin tests PASS).
- Original full public report artifact **14302734363** `cmp1-exposed-new-common-capital-conditional-original`. Original downloaded Actions ZIP SHA-256 **`8c4d1290b00739e43c674a009f54f105e08be35c98ff1e30e6d55ee1eae5bdd6`**, containing `cmp1-common-capital.public.json` SHA-256 **`0006d2e33707fac7be9f90df694b099aab64377d1a0590560a7d5bc0279d70bb`**.
- Original CMP1 Python code SHA-256 `b6ed1693d12fb8efd40e474da6157889446876f1e94934b4abf2e9f9f6f67164`.
- Reused unchanged publicly committed AIP1 authenticated-source rows SHA-256 `ed23b6d7ce289ce1eeede6626ef8d9bce09d2cfbdb59fd6fe4b4493a75a4bd3c`; original source Actions run `41735441128`, encrypted artifact `13278617985`; original ciphertext hash `fa684ca1de58c6d1e8bdee410834855d05389af0c0ae4523b095367dce0e5331`. **Zero new broker reads, zero source recollections, zero orders and zero Cloud activation.**

## Full original observed (not independent) calendar

646 source-complete original future price-return rows, 360 distinct decision UTC timestamps, six whole-source instruments `AUS200, GER40, JPN225, NAS100, UK100, US500`, fixed source-supported 120-minute endpoint; 2026-05-04 through 2026-10-30 (26 ISO weeks represented). Forecast information is calculated causally only from previously matured source outcomes; earlier closed AIP1 modeled forecasts, side/direction and favorable selection flags are **not imported as policy signals**.

At each clock the policy compared all source-visible names within shared reserved minimum margin; the single conditional initial cash was EUR300, without resets or deposits. This model is **NOT** the native funded EUR ledger because bid/ask-side executable prices, actual fills, fully historical fees, swap and floating marks are missing.

## Original same-calendar counterfactuals

| Counterfactual policy | Conditional terminal cash EUR | Conditional closed proxy NET EUR | Conditional completed positions | Maximum *closed-only* drawdown | Maximum simultaneous reserved minimum margin EUR |
|---|---:|---:|---:|---:|---:|
| CASH | 300.000000 | 0.000000 | 0 | 0% | 0 |
| CMP1 JOINT primary | **165.858123** | **−134.141877** | **18** | **46.6649%** | **177.95** |
| OWN prior-price only | 169.582247 | −130.417753 | 23 | 43.4726% | 177.95 |
| PEER prior intermarket only | 186.699387 | −113.300613 | 29 | 37.7669% | 160.39 |
| JOINT_UNRANKED | 165.858123 | −134.141877 | 18 | 46.6649% | 177.95 |
| JOINT_NO_ABSTENTION | 198.438688 | −101.561312 | 41 | 34.3744% | 177.95 |
| JOINT_ONE_SLOT | 168.215900 | −131.784100 | 17 | 45.9067% | 177.95 |

All numbers above are **conditional own-price proxy values**, not certified executable EUR NET. Original full precision and all decision/settlement rows remain in artifact `14302734363`; rounded display values here are not a replacement receipt.

- Increment versus CASH: **−134.141877 EUR**.
- Increment versus OWN: **−3.724124 EUR**. Peer information **did not** improve this policy's observed conditional economic outcome.
- Increment versus PEER: **−20.841264 EUR**.
- Increment from ranking versus unranked: **0 EUR** in this fixed observed path, not universal proof.
- Increment from abstention versus no abstention: **−32.580565 EUR** in this fixed path; never revise threshold opportunistically.
- Increment from allowing simultaneous entries versus one slot: **−2.357777 EUR**.

Original JOINT recorded 471 abstentions, 175 eligible offered conditional candidates, 157 margin/active-symbol rejections and 18 completed conditional trades. All 18 occurred by **2026-06-09**, when conditional closed-only capital fell below EUR210; no later capital replenishment/reset was used. NAS100 accounted for 6 conditional trades and approximately −107.03 EUR conditional proxy, but **no retrospective symbol exclusion or reverse trade is permitted**.

Complete conditional roundtrips by original source ISO week: 2026-W20 **8**, W21 **4**, W22 **3**, W23 **2**, W24 **1**; **0 in the other 21 weeks** of the 26 observed source weeks. Source-calendar availability and prospective HARD21 eligibility have not been independently established. No week provides 21 financed complete native roundtrips; **HARD21 remains unproven and is not rescued by counting signals**.

## Exact financial impossibilities and stop

All `nativeFundedNetEur`, `adverseExecutableNetEur`, `brokerExecutionNetEur`, `financingEur` remain **null / UNKNOWN**, not zero. The original source row is a BID-bar endpoint return; a `MinimumNotionalEur` from current source cost snapshots is not a historical legal fill. The existing `NativeFundedSession.DecideResearch` and `NativeFundedLedger` cannot legitimately process real CMP1 `OPEN_FILL`/`CLOSE_FILL` without fresh original synchronized quote-side, currency conversion, financing and mark events for selected capital-book events; no invented quotes were fed to them. Thus the exact native path was **not executed** in this stage.

Source-specific missing proof: original-account historical entry and close BID/ASK and timestamps for all policy/ablation decision clocks, actual legal volume and margin state on those clocks, complete commission and conversion accounting in EUR, rollover/swap where relevant, original holding marks to estimate adverse floating equity and variation of available common free margin. A separately preregistered read-only pricing protocol would be necessary, covering **the whole fixed policy and all controls**, not only the favorable subset. This stage did not silently claim completion.

Even the *less strict* **closed-only** conditional drawdown 46.66% is over the 30% system objective; real floating DD may be greater, never certified. All variants have negative conditional cash-versus-CASH economic returns. This **falsifies the exact CMP1 shadow policy's attractive economic premise on the exposed calendar**, not all future genuinely new predictive mechanisms.

No independent chronological confirmation, no actual broker executions, no valid capital-certification or Cloud readiness. **Do not promote, retune, invert, resample, repeat or rename this exact negative CMP1 policy.** Preserve the original run/artifact/hashes and the unchanged frozen source.
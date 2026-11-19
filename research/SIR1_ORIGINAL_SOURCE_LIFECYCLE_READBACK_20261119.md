# SIR1 original fixed-clock C# model-close recovery witness — original readback 2026-11-19

## Immutable continuation / authority
OWNER after independent NPI1 audit Issue #393 #7005263564. Closed NPI1 #44494972731, MVO1/SPE1/OEI1 are NOT rerun, altered or rescored. Prospective SIR1 product close-intent protocol freeze **988aeff88ca95cb9c06c9645fc5b28b8d5386cbd**, original-source witness subprotocol freeze **0c0de1b7f1d819f4180f549eeba34d9862818ea9**. Both separate from and before scoring the new source witness. PR **#398**, merged **4e02ded2dea41821035424ad20602d40f3ac7010**. Original once-only trigger **ffb09d33423d71cbc26e9b57f8ff8aa950d45acc**. No broker orders/Cloud activation, no new broker data.

Tests:
- Core lifecycle/restart and SAME-event observation-only Cloud adapter parity: GitHub Actions **#44504014386 SUCCESS**. Source witness technical preflight **#44504014037 SUCCESS**. Official cTrader CLI Cloud compile **#44504014022 SUCCESS**. These tests contain SYNTHETIC observations, not original financial results.
- **New** immutable ORIGINAL source witness GitHub Actions **#44504584833 SUCCESS** (both verify and protected source jobs), original public artifact **#14518587491** `sir1-original-quote-bound-model-intent-recovery-public`.

## Original source custody & receipts
Read only sealed original OEI1 source, original run **#44247979857**; original plaintext SHA-256 **32f3401cfede314a7a3b110c0636166a2680b2f440e3428dd5c1b70f12acaf1b**, ciphertext SHA-256 **c28a69c2ee738f209cfd025a7424377629c9ac59f695c2b87422c2577c4d4c86**, independently matched bridge receipt and public original source hashes in protected job. No score or economic execution of OEI1/NPI1 called; Python is strictly decrypt/verify/as-of custody. Full trading/funding status never inferred from this market-source tape.

The original archived fixed source witness is **21 August 2026 15:27, 15:28, 15:29 UTC** (Friday) and **24 August 2026 13:30, 13:31, 13:32 UTC** (Monday). USD-conversion instrument EURUSD and ETHUSD, SpotBrent, US500 covered. Exactly **5 genuine paired BID/ASK as-of minute observations per instrument** (20 original paired marks); **24 August 13:30 UTC lacked fresh eligible BID/ASK for all four instruments** and remained UNKNOWN, not synthesized. All valid recorded quote sides are at or before clock and <=30 seconds old. Source collection window end is NOT official session closure. 70+ hours between local close request and first resumed observation does not imply broker execution failure.

Original ZIP includes:
- `native-original-lifecycle.json`, **68,271 bytes**, SHA-256 **123edba6640a21221193ef195e37ecddba17d3f19af15b86e89ce9a8693054dd**; matches `receipt.json.NativeEconomicTraceSha256`.
- `receipt.json`, **973 bytes**, SHA-256 **e13629c7ca996fe8d735f282e904e4f0da424e272d6aa7363f0dc3e7262a9990**.
- Source-bound native ledger event arrays FULLY public and redacted for account identity: LONG **38 events**, SHORT **34 events**, include `MARK`, `REQUEST_OPEN`, `OPEN_FILL`, `REQUEST_CLOSE`, `MODEL_CLOSE_INTENT_EXPIRED`, `CLOSE_FILL`. Existing `NativeFundedLedger.ReceiveFacts` replays the event stream and verifies restart/idempotence; an independent programmatic structural readback verified every model expiry matched a pending close, no model expiry removed position, every CLOSE_FILL followed a later REQUEST_CLOSE, the number of positions and pending intents matches the final ledger.

## One common EUR300 model account per policy, CASH and matched LONG/SHORT controls
This is **NOT** an alpha evaluation. The Friday 15:29 untransmitted close requests are expressly INJECTED product-lifecycle test stimuli, not normally signal-selected exits. Later reissues are driven by existing `NativeCausalExitResearch.AssessLifecycle` on the first actual postgap quote. Therefore financial figures below cannot be interpreted as ex-ante strategy returns or used to optimize NPI1.

| Evidence | CASH | LONG min-volume source model | SHORT min-volume source model |
|---|---:|---:|---:|
| Model initial capital | 300 EUR | 300 EUR | 300 EUR |
| Observed quote/margin financed OPEN_FILL | 0 | 4 | 4 |
| Original untransmitted close requests explicitly expired, only pending removed | 0 | 4 | 4 |
| Fresh source-quote-bound causal signal CLOSE_FILL on 2026-08-24 13:32 UTC | 0 | 3 | 1 |
| Terminal held position count | 0 | 1 | 3 |
| Terminal pending simulated close | 0 | 1 | 1 |
| Closed conditional quoted net **before unverified historical funding** | 0 | **−2.484823816941837 EUR** | **−0.9233300202214073 EUR** |
| Remaining modeled cash (includes fees on still-held inventory) | 300 | **297.51517618305814 EUR** | **299.0509749286454 EUR** |
| Last sampled modeled liquidation equity (NOT broker account equity) | 300 | **298.33568548833284 EUR** | **301.0542651915237 EUR** |
| Last sampled model margin (NOT historically certified requirement) | 0 | **8.24 EUR** | **75.41 EUR** |
| Sampled maximum drawdown (NOT continuous risk certification) | 0 | 0.63627% | 0.16312% |

The LONG/SHORT values are two separate, equally initially-funded counterfactual EUR300 books and must NEVER be combined, neither are they matched forecasts with adequate evaluation support. All original-account contractual tariffs and min margins are *as observed for source*, with no certificate of historical rate continuity, no full weekend financing or intragap prices; **real/adverse broker NET = UNKNOWN**. The SHORT marked equity above 300 is NOT realizable settled cash. The mechanical 'model adverse' price/slippage is conditional and not a certified adverse execution price. Systemic HARD21, continuous <=30% floating DD and >=12 independent months are NOT established.

### Original real quote observation causality
At Friday 15:29, 4 LONG + 4 SHORT model-only closing intents exist with held positions and booked margin. No genuine quote within modeled 2-minute response window resolves them. At Monday 13:30 missing paired as-of quotes, all 8 expire as `MODEL_CLOSE_INTENT_EXPIRED` WITHOUT a close, cash/margin release, or broker cancellation claim. Monday 13:31 first genuine as-of samples permit native causal thesis re-assessment. Subsequently only where a true native price/structure/risk invalidation remains does a new untransmitted close request form; **3 LONG and 1 SHORT** close on genuinely later Monday 13:32 original quotes. Other held exposures remain. Model sampled historic path is incomplete and marked accordingly.

Original Core C# `NativeSimulatedCloseLifecycle.Advance` changes only new prospective model events; all historic NPI1 outputs preserved. `NativeCloudResearchParityAdapter.ObserveModelCloseOnly` is compiled into Cloud and linked to Replay tests and invokes identical pure Core class. **No proof of activated Cloud runtime or actual broker order pipeline** follows.

## Verdict / next product requirement
**Technical model-deadlock repaired and independently inspectable ORIGINAL source-bound model event traces published.** This does not show a production trading strategy, broker-order reconciliation, accurate historical financing or positive adverse incremental funded NET. The SIR1 original source witness is now closed and must not be retuned or rerun to engineer favorable economics. The next product programme should source-bind *new* predecision integrated multi-timeframe opportunities and legal-cost contemporaneous financed CASH, LONG/SHORT controls to full source periods using this now-recoverable shared Core lifecycle, with a broker-authentic session/FX/margin/funding route where actually available; never prefilter previously observed winners.

Architect-Coordinator should independently download original artifact **#14518587491**, match hashes, recompute 38/34-event invariants, compare source clocks and same-book cost/volume, assess new `MODEL_CLOSE_INTENT_EXPIRED` separation, and verify Replay/Cloud adapter same-event parity without declaring Cloud deployment or NET qualification. OWNER final authority; director did not activate live/demo/cloud.

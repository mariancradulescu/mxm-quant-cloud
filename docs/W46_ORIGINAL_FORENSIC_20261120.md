# W46 — forensic original, attribution and limits (2026-11-20)

**Read-only audit; no W46 rerun or retuning.** Parent main `e2f463c07458af359c93febbee733c08c84657a0`; original [Actions #44735700353](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44735700353), original commit `90568cfe38e0d7cd6ff31aebea3fb7e401ffe839`, artifact #14627239908. The original ZIP digest is `0f1828ba201db4dca6c021e36bc0724b04253c3cadd849c78c949398a973cc98`; `economic.json` SHA-256 `d77603ad36b989b4aa2c3a53dfa3c4323401c4553cb9ecc43793f541f17c45c9`. Reproduced independently by `python research/W46_original_forensic_readonly.py original.zip`. The tool consumes only original public JSON bytes and creates no orders or broker requests.

## One modeled EUR300 book per policy, original W46

| Policy | Central trips / net EUR | Adverse trips / net EUR |
|---|---|---|
| CASH | 0 / 0.000000 | 0 / 0.000000 |
| FIRST | 88 / +4.031624 | 86 / +1.278718 |
| RANDOM | 88 / +3.908072 | 86 / +1.169437 |
| TREND (compression) | 34 / +0.784310 | 35 / −0.431019 |
| REJECTION | 56 / +7.659608 | 53 / +5.920631 |
| POOLED | 88 / +4.004790 | 86 / +1.718788 |
| RANK | 88 / +8.844372 | 86 / +5.966592 |
| SELECT | 0 / 0.000000 | 0 / 0.000000 |

For each scenario/policy the individual modeled close NET agrees with gross minus commissions, spread, slippage and conversion, with closed-ledger NET, and with cash minus initial EUR300. Original event counts reconcile to modeled fills and closes; all positions are closed. These are **simulated conditional** receipts before unknown historical financing, NOT broker-certified real returns.

## Dominance and prediction

- RANK adverse: **6 XAUUSD trades +11.014180 EUR**; remaining 80 trades **−5.047588 EUR**; total +5.966592 EUR. One-symbol arithmetic attribution is **184.6% of net**, not a financed ablation.
- RANK−FIRST **+4.687875 EUR**. XAUUSD contributes **+4.604004 EUR** of this delta: its six RANK executions include one SHORT on **2026-11-10 20:35:45–20:39:15 UTC** with modeled +4.604004 NET, absent from FIRST/POOLED. The same trade had a **negative ex-ante mean prediction −0.195815 EUR**, lower bound −0.377228 EUR, stressed modeled risk 5.723345 EUR, legal modeled min volume 1 and snapshot margin 161.745 EUR. Its gross +4.962290, commission 0.062699, spread 0.098529, slippage 0.197058, conversion 0. The remaining difference after *arithmetically subtracting this one trade only* is **+0.083871 EUR**. A real exclusion changes subsequent portfolio cash/margin/opportunity competition; DO NOT label this counterfactual.
- Largest single trade overall was another XAUUSD SHORT closed **2026-11-12 11:16:15 UTC**, modeled +5.273031 EUR. It also appears in FIRST, so does not explain RANK's incremental performance.
- RANK adverse had **86/86 negative mean predictions** (central 87/88); even XAUUSD outcomes selected in RANK had negative means. Contextual adverse **Brier 0.291107** versus POOLED **0.280528** (worse), though context MAE 0.477983 versus POOLED 0.496656 (slightly better). Relative ranking of negative estimates is NOT demonstrated positive prospective economic value.
- Adverse training: **126 usable labels**, calibration **101**, evaluation **92**, with only **5 calibration days per family**. `NativeStructuralResearch.Fit` trains on independently settled simulated trade labels, **not** funded marginal outcomes of the common book; `NativeCompleteDistribution.Predict` ranks nearest settled samples, uses at most 48 with up to 8 per day, and needs at least 12 across 4 days. Negative means could reflect negative sample expectancy, representation, cost, limited calibration, label/portfolio mismatch or nonstationarity. **Cause unresolved.** No sign inversion, no threshold adjustment based on W46.
- SELECT advers made **one open request** for XAUUSD LONG, **2026-11-09 06:50:15 UTC**, but it expired 30 seconds later (`MODEL_UNTRANSMITTED_OPEN_FUNDED_FILL_REJECTED`). It therefore completed **0 trades**, not necessarily zero selection attempts. Precise fill rejection mechanism is not identifiable from these shortened facts alone.

## Risk, source and native-platform limits

RANK adverse finished at cash **305.966592 EUR**, maximum sampled DD **2.0176%**, maximum observed margin **201.5375 EUR**, two simultaneous positions, **86 W46 completed** (one-week modeled HARD21). Yet there are **122 held-but-unknown liquidation equity clocks**, **3 trades with incomplete observed price path**, **1 with unverified historical financing**, **11 stop-risk overruns**. Thus no continuous floating-DD certificate, future weekly robustness, broker NET or 12-month independent proof.

The original `context.json` found H4 readiness for five markets, **no H4 ready for AAPL.US**, and **zero D1 Ready windows across all six** under current consecutive-wall-clock validation. For example EURUSD D1 has 8,445 `LatestBarMissing` and 34,314 `MissingInterval` observations. Weekend/holiday/session gaps and native daily bar anchor MUST be checked against actual calendar before treating gaps as missing source rows; **no interpolation or silent recovery**. No D1 predictive claims are justified.

`NativeClosedMarketContext.History/Platform` and the adapter share C# interfaces, with synthetic replay/Cloud checks, but **no actual live cTrader `MarketData.GetBars` feed parity** proven. Same synthetic frame hashes cannot certify platform publication clocks. No Cloud activation or real order is authorized.

## Verdict

**VERIFIED**: original hashes, original modeled closing arithmetic and exposed W46 conditional concentration.

**NOT VERIFIED**: positive causal/marginal predictive edge; robust financed ablation; continuous floating risk; historical tariffs/funding and actual fills; cTrader real-feed parity; ≥12 months independent confirmation.

**NOT PROMOTED**: RANK, SELECT, or any order-capable cBot. Further work must use the separate prospective registration, with W44–W46 permanently exposed. No retrospective winner choice.

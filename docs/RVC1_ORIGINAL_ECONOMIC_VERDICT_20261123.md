# RVC1 — original economic evidence and terminal integrity verdict (2026-11-23)

**OWNER-authorized ONE original invocation, no economic rerun.**
- Repository: `mariancradulescu/mxm-quant-cloud`.
- Original protocol freeze BEFORE code: `d43b49c46163b9f634f7c42d3c790e516df41762`, `research/RVC1_FROZEN_JOINT_FX_RESIDUAL_ECONOMICS_20261123.md`. No formula/threshold retune.
- RVC1 native PR [#441](https://github.com/mariancradulescu/mxm-quant-cloud/pull/441) merged, squash `bea16bebb6462b22ca8174bc599588620583b22a`, technical C# CI [#45259341146](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45259341146) SUCCESS.
- Exact one-time source-bound OWNER marker commit `5426c8ebf42bd4463b4931ec43f7035b6a1eb184`.
- Original full workflow [GitHub Actions #45259630338](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45259630338): **SUCCESS, run_attempt=1**. Both `verify` and protected `one-authentic-original-economic` jobs SUCCESS. There were **zero broker orders, zero Cloud activation, zero secret modifications and zero new data-acquisition requests**.
- Sole public economic [artifact #14858829991](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45259630338/artifacts/14858829991), `rvc1-original-public.json`. Original ZIP SHA-256 `1176630082c51eeb28fb1b07748bce9540e0e912a2338fe09605ad0173c85d60`; enclosed JSON SHA-256 `fb4a83ec5d542886f607600647d70f45d951b505793395db143b4398b87dd44e`. Native complete PRIVATE digest is conserved inside the public receipt, without exporting raw broker prices. Source authentic only to original account, `original` historically exposed.

## Exact original financial summary

**Modeled realized CLOSED fragments only, EUR; NOT full-book terminal NET**. Currency/volume/fees are conditional original-account-as-of values; **no historical executable fill certification**. Initial capital EUR300 independently for each of the four comparators and each stress; do not pool capital or count both pair legs as two trades.

| Policy | Costs ×1: closed NET / completed whole pairs | Costs ×1.5: closed NET / completed | Costs ×2: closed NET / completed |
|---|---:|---:|---:|
| **JOINT_RESIDUAL** | **−5.790853 / 18** | **−7.452247 / 18** | **−10.064008 / 18** |
| PAIRED_NO_CONVERGENCE | −5.790853 / 18 | −7.452247 / 18 | −10.064008 / 18 |
| SINGLE_EURUSD | +5.2686 / 6 **single-leg**, NOT pair | +5.0600 / 6 single-leg | +4.8514 / 6 single-leg |
| CASH | 0 / 0 | 0 / 0 | 0 / 0 |

**Difference of paired-policy CLOSED NET vs paired no-convergence: exactly ZERO at all 3 stress levels.** This is NOT proof of any incremental relative-inventory convergence advantage. The SINGLE EURUSD positive subcohort is not a validated alternative, cannot be selected after seeing the results and cannot be called an economic discovery: it is an unqualified, terminally open one-leg comparator.

Primary adverse ×1.5 C# full-event receipt:
- CLOSED GROSS **−2.3378992865362167 EUR**.
- Modeled accrued spread **1.151137802519718 EUR**; slippage **1.1512980841032134 EUR**; commissions **2.803843576039831 EUR**; conversion charge **0.008068084934087106 EUR**; historically chargeable overnight financing **unknown** (no zero-cost certification).
- Net for already CLOSED fragments: **−7.452246834133066 EUR**. Cash held at end **292.46975 EUR** (after `0.078003120124805 EUR` remaining open-entry-fee liability); terminal quoted liquidation equity ~**355.5463 EUR** is **NOT certified, potentially very misleading** because swap was not chargeable/proven for the long-running Held exposures.
- 19 modeled financed pair openings, **18 completely CLOSED joint pairs** (36 closed legs) and **one still open two-leg pair**, with two **pending CLOSE intents**; zero pending OPEN at terminal state. The two close intents do not themselves release the Held margin or permit counting a completed pair.
- **52 genuine source-calendar ISO weeks, 74,212 union M5 clocks**, 65 eligible causal source decision clocks in 2025-W47, 18 complete pairs **only in 2025-W47**. **0/52 calendar weeks** meet modeled HARD21; 51 weeks have ZERO completed pair cycles. This is NOT certified broker eligibility for 52 weeks.
- Maximum sampled model equity DD **7.401%**; neither intrabar DD nor subsequent unobserved financing is certified. Peak simultaneous Held + Pending-open modeled margin **73.29 EUR**; peak reserved stop risk **2.043649087424872 EUR**. No sampled 30% breach was observed; that does NOT prove global DD compliance.
- Source/finance evidence flags: `Incomplete=true`, `UnknownFunding=true`, `FinalOpenPositions=2`, `FinalPendingIntents=2`; 102 unknown price-mark clocks and 103 temporary source suspensions; `MARKED_EQUITY_FUNDING_UNKNOWN` event counter **140,782**, `ROLLOVER_CONTRACT_UNKNOWN` **70,390** (counts are recorded evaluation clocks, **not** independent missing trades).
- Historic cost schedules are CURRENT broker terms only and may not equal tariff on historical 2025–26 dates. A sampled terminal equity value cannot substitute for realized NET after all actual holding charges.

## Independent forensic reconciliation, without a single additional model execution

Recomputed from original public receipt with decimal arithmetic:
1. For each of ALL 12 books, `gross - spread - slippage - commissions - conversion + financing = closed NET` to max absolute residual **7.27×10⁻¹⁶ EUR**.
2. For each book, `sum(all 52 weekly model closed NET)=sum(closed fragments NET)`, **exact to serialized decimals**.
3. For all books, `cash = initial300 + closed NET - remaining open-entry-fee debt + remaining open financing`, max absolute residual **3.55×10⁻¹⁴ EUR**.
4. Authentic original source receipt reconfirmed 74,195 EURUSD M5, 74,126 GBPUSD M5, 6,190 original H1 for each; 48-source P05 [original artifact #14799363946](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45134137836/artifacts/14799363946) was independently inspected. Its public `marketCoverage` has **48 instruments but excludes both EURUSD and GBPUSD**. Original P05 ZIP SHA-256 `8536052ab5782e107c63caa67a63ddfdec9923efb54a72f44e7925707e9fec3c`; `receipt.json` SHA-256 `939715d03f903979ef63df645a6fcffcdcd663c74d185d4849b27649d9a2faf5`.
5. RVC1 source bridge `recovered_official_funding()` tried to match original P05 `ProtoOASymbolByIdRes` to EURUSD/GBPUSD original contract provenance. Its authenticated collection returned **`RecoveredSwapScheduleSymbols=[]`**. Consequently, the present model could NOT charge historical financing on its retained positions. Repeated unknown-financing marks kept that pair Held for the rest of the 52-week modeled history; many later weeks are mechanically inactive. The total portfolio equity therefore has **UNKNOWN financing**, not a proven +55 EUR profit. This is a concrete **technical/source-matching defect**, NOT evidence that future valid contracts or sources cannot be collected. The original older BDP1 raw read-only broker contract packet may be relevant to a *separate future custody-source audit*, not to a silent retrofit of this protected original.

## OWNER decision: original RVC1 exact configuration closed WITHOUT promotion or relaunch

**Classify `RVC1_UNQUALIFIED_HARD21_FAILURE_TERMINAL_CENSORED`.** The original has genuine, reproducible **negative CLOSED NET for paired primary at all 3 cost levels**, **zero paired incremental closed NET**, **0/52 modeled source-calendar HARD21 weeks**, and critically **one unsettled paired position with long-lasting unknown financing**. These facts conclusively prevent approval; they do **NOT** establish a completed full-book economic NET loss/profit, continuous DD certificate or 12-month independent confirmation. The requested complete **certified** economic verdict is unavailable from this one original; do not falsely certify it.

Do NOT rerun or retune RVC1 to repair its performance after results exposure. Do NOT recompute a changed-source variant into artifact #14858829991. Keep `main` source, workflow, original hashes, protocol, original artifacts, issue receipts and unclosed liability evidence. Any future research would require a separately justified mandate, frozen before its own economically independent evidence. Existing closed studies and PEL1 Draft untouched; no trades or Cloud action.

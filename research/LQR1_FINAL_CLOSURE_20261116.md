# MXM Quant Cloud — LQR1 final exact economic closure (2026-11-16)

**OWNER decision:** `LQR1_CLOSED_EXACT_NEGATIVE_VS_CASH_NO_PROMOTION`

**Scope:** Documentation and cryptographic preservation of the closed exact LQR1 study only. No new score, source collection, execution, policy change, retuning, reversal, automatic LQR2, Cloud activation or LIVE/DEMO orders. This document records already executed authentic work and does not authorize fresh study activity.

## 1. Original research chronology, frozen identities

- Repository: [mariancradulescu/mxm-quant-cloud](https://github.com/mariancradulescu/mxm-quant-cloud). Pre-closure audited `main` HEAD: [d9c43cd0d4078c52e3c102f3632ece32ac3ff487](https://github.com/mariancradulescu/mxm-quant-cloud/commit/d9c43cd0d4078c52e3c102f3632ece32ac3ff487).
- Presource frozen protocol: [PR #333](https://github.com/mariancradulescu/mxm-quant-cloud/pull/333), [research/LQR1_ASYNC_BIDASK_REFRESH_PRESOURCE_20261116.md](LQR1_ASYNC_BIDASK_REFRESH_PRESOURCE_20261116.md). The protocol was frozen **before** reading/scoring the new LQR1 outcome.
- Source-only causal implementation: [PR #334](https://github.com/mariancradulescu/mxm-quant-cloud/pull/334); original economic implementation: [PR #335](https://github.com/mariancradulescu/mxm-quant-cloud/pull/335); original primary policy unchanged, exactly matched 42-intent comparators: [PR #336](https://github.com/mariancradulescu/mxm-quant-cloud/pull/336).
- Source variation proof: [Actions #43897788990](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43897788990), artifact `14240121272`.
- Original native financed EUR economic result: [Actions #43900286858](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43900286858), artifact `14240978134`.
- Mandatory paired native-financed comparators with immutable original policy: [Actions #43902249066](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43902249066), artifact `14242615402`.
- All three listed original Actions completed `SUCCESS`; none constitutes broker fills or independently held-out validation.

### Preserved artifact hashes (SHA-256)

| Original artifact | GitHub ZIP SHA-256 | Internal JSON SHA-256 |
|---|---|---|
| Source evidence `14240121272` | `7ef61add0f997bce9cb656ce316b36b45d57b2ff979e643a21a92b7e587fe5a8` | `c29d66f2a1d6b9edb1c1ff91707e466db376eadd6c3ed2a841772e9c56ec1e4b` |
| Original EUR300 economic `14240978134` | `4aba35e133bdc8e66d35f8046fe48cd137e66069e6d736ba291dea29c35f624a` | `a6f539d37fa7d541ec60434efc66bd8d0adec936f31e144b90cf154072df5033` |
| Matched 42-clock controls `14242615402` | `0bb878378888004ef1bddc2fcde223441ed99111731df49485364c9786790bca` | `7435e538236bbea30dc979a5fa6de149eaa5bc614150ec80978c1d071e43145f` |

These hashes were independently calculated from the recovered original ZIP files and their internal original JSON bytes. The final comparator receipt identifies the original run, artifact, and exact original financial JSON SHA-256; it does **not** replay the primary LQR1 policy.

## 2. Prespecified economic mechanism and source

LQR1 tested whether the **side and signed price change of the last independently updated BID/ASK quote before the decision** conveys causal information absent from simple own midpoint momentum. It does not assert order flow, executions, Level II liquidity, broker queue priority or latency arbitrage.

Frozen development-only 8-week period: **2026-09-14 through 2026-11-08**. Fixed pairs **USDCHF and EURGBP**; 80 prescheduled times per pair, 160 symbol decisions. Original 42 side-specific predictive intents: **32 USDCHF and 10 EURGBP**. Exactly **21** LQR1 directions differ from own same-clock momentum. This demonstrates **information variation**, not a profitable signal. Historical EUR conversion and current-account broker contract cost evidence used **328 new read-only requests** in the original financial run and **zero** further market/broker requests in the matched-control completion.

The native C# counterfactual uses a single prospective-equivalent starting capital of **EUR300** per alternative policy, not simultaneous funded real portfolios. Slippage assumptions are **0.5 bps central / 2 bps adverse / 4 bps stress roundtrip**. The compared policies are original LQR1, own momentum on exactly those same 42 predecision intents, fixed long, fixed short and cash. The original full-calendar 160-clock comparator participation differs; it **must not** be represented as a 42-intent paired benchmark.

## 3. Financial original results: identical 42-intent mask

Conditional modeled complete funded roundtrips for every noncash policy in this table: **42**.

| Policy | Central NET EUR | Adverse NET EUR | Stress NET EUR |
|---|---:|---:|---:|
| CASH | +0.000000 | +0.000000 | +0.000000 |
| **LQR1 original** | **-3.437637** | **-9.195484** | **-16.872629** |
| Own momentum, matched | -9.302776 | -15.060633 | -22.737792 |
| Fixed LONG, matched | -6.043430 | -11.801278 | -19.478423 |
| Fixed SHORT, matched | -3.474885 | -9.232736 | -16.909884 |

Original receipt uses more precision internally; shown values are rounded to six decimals. The original LQR1 numbers and hashes are unchanged.

**Incremental matched central NET (LQR1 minus benchmark):**
- Versus CASH: **-3.437637 EUR**, absolute negative.
- Versus matched own momentum: **+5.865139 EUR**, relative positive only.
- Versus matched fixed LONG: **+2.605792 EUR**, relative positive only.
- Versus matched fixed SHORT: **+0.037247 EUR**, economically negligible and not robust.

The original LQR1 policy remains negative in central, adverse, and stress models. Better than a losing comparator is **not** a profitable advantage versus cash. Same-clock relative outperformance cannot rehabilitate the predeclared negative absolute economic gate.

## 4. Exact falsification, unknowns, and no-promotion

**Final OWNER verdict: `LQR1_CLOSED_EXACT_NEGATIVE_VS_CASH_NO_PROMOTION`.**

The exact frozen policy is closed without inversion, resampling, retuning, replay, cherry-picked symbol/side/clock/period, or a renamed LQR2. The result does not rule out unrelated future causal sources or mechanisms.

Unresolved claims MUST remain unresolved:
- Broker tariffs observed currently applied to historical quotes are **conditional**, not certified historical effective costs.
- `actualBrokerExecutionNetEur` and real broker fills **unknown**; these are modeled native C# counterfactuals.
- Continuous between-tick floating DD <=30% **not certified** by sampled marks or slippage stresses.
- System-wide HARD21 **not certified**; it is a portfolio objective, not a per-family gate.
- Eight globally exposed development weeks are not >=12 months or genuinely independent chronological confirmation.
- Exact final native cTrader Cloud cold-start parity not certified; no Cloud activation or LIVE/DEMO orders.

## 5. Custody and continuation of mandate B–E

Keep all frozen source/protocol/code, raw encrypted and protobuf custody, Actions, ZIP/JSON bytes and SHA-256 identities intact. **No LQR1 reexecution or new data collection is needed or permitted for this closure.** No new research is authorized by this document alone; any economically distinct future study must start with prospective causal reasoning, prespecified falsification and controls, then use legitimately authorized read-only capabilities.

OWNER v2.0 remains fully binding: initial capital **EUR300 without resets/deposits**, system-wide financed **HARD21** (at least 21 complete roundtrips in every eligible week), maximum targeted **30% floating-equity drawdown**, genuine independent confirmation, and final single **C# native cTrader Cloud cBot** compatible with the owner's Android workflow, without LIVE/DEMO orders or Cloud activation before a separate OWNER decision.

**Closure is documentation only; operational pipeline activity must not be confused with economic edge.**

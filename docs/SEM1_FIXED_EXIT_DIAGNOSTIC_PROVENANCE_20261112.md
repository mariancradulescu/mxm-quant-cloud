# SEM1 fixed-exit observation provenance — authentic postclosure diagnostic, 2026-11-12

**Classification:** exposed-history technical diagnosis, not new price source, not
independent validation, not an economic retuning or portfolio promotion.

## Immutable evidence

- Original SEM1: run [43207629492](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43207629492), encrypted source artifact **13938934824**.
- Original SEM1 plaintext SHA-256: `6c2605e7f23133c5e2a728f9190be87d54ff080de5c1d7bba8300916c24f8354`.
- Existing correction: run [43214539052](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43214539052), artifact **13943645086**; old correction public JSON SHA-256 `44ca3cf8c2aeff9c46f47e7b0368af4b860ffc34c97459d3545a50655cf8309b`.
- Technical diagnostic: run [43219156619](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43219156619) **SUCCESS**, original-custody-diagnostic **SUCCESS**, artifact **13944951490**, retained 90 days.
- Diagnostic public JSON SHA-256: `2c9c668e405c82404ab2fc625ed4324c4ff240f364ce2d182088b768a37eecad`.
- Enhanced full matched correction JSON SHA-256: `762ed73c0170ed32607670ae74ff059268045f0cd85686c09b9bcca073c25afa`.
- New artifact ZIP SHA-256: `269290dbb421a7026fef26ebed76d5d73aa7abd222b705fb0e8cbc2c77a88ea5`.
- PR [#244](https://github.com/mariancradulescu/mxm-quant-cloud/pull/244), merged HEAD `f1356ad1b5c1dc1bb2e1e2f5e4e7375d3d0f14fe`.

## Exact unresolved exposure

- Instrument: **ETHEUR**; position `ETHEUR/1788073201500`; causal filtered entry side **long (+1)**.
- Original entry: **2026-08-30 07:00:01.500 UTC**, 1788073201500 milliseconds.
- Frozen fixed exit: **2026-08-30 07:30:01.500 UTC**, 1788075001500 milliseconds.
- Original archived **RawPairClocks does not contain a paired BID/ASK at this fixed exit**.
- Nearest *costed* observation earlier: **07:00:01.500 UTC**; later: **10:00:01.500 UTC**. Neither may substitute for the fixed exit. Future quotes are diagnostic only.
- The same missing fixed exit appears in the affected causal SEM1 policies (central/adverse and joint/individual/ablation paths); 90m joint causal exit was observed.
- In the 30m adverse filtered joint replay, exactly **8 closed round trips** total **+11.493551272864416 EUR** NET closed fragments, plus **1 unresolved open position** and **23 UNRESOLVED_FIXED_EXIT admissions rejected**. These closed fragments are **not** final portfolio NET.
- Complete-endpoint 30m adverse scenario: **50 closed round trips, -5.746768312820001 EUR**, but this is post hoc selection on observable future endpoints and not an unbiased causal replacement.
- The 90m joint causal filtered adverse scenario: **50 closed round trips, -42.73847495775693 EUR**; comparator momentum **-63.42 EUR**, funded long **+16.79 EUR**. No portfolio promoted.

**Scope of inference:** The original tape lacks an eligible raw pair; this does not
establish whether a recoverable tick exists in Pepperstone history. A possible
five-minute collector-window clipping mechanism is a hypothesis, not a proven cause.
The authenticated supplementary source request was **not executed**. Until a separate
legitimate original-account read-only query at the fixed clock under the original
30-second as-of limit demonstrates complete valuation, classify SEM1 causal 30m
as **ECONOMICALLY_INCOMPLETE**. No OHLCV proxy, later quote, guessed fill,
retrospective winning subset or altered exit rule is permitted.

All original receipts remain immutable, no trading orders, Cloud activation,
OAuth reauthorization, source substitution, new ledger or retroactive qualification.

> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# Evidence-gated economic convergence — 2026-11-02

## Material defect corrected

`PortfolioEconomics.Evaluate` previously returned `Pass=true` when caller-supplied `EconomicProof` booleans were all set to true. These booleans are *assertions*, not authentic receipts. An adversarial or accidental caller could combine a fabricated annual window and profitable synthetic settlements with all-true booleans, obtaining `ALL_EVIDENCE_GATES_PASSED` without a single authenticated Pepperstone event.

The pure C# evaluator now calculates research **diagnostics only** and **never returns Pass=true**. An otherwise successful declared-proof call returns `EVIDENCE_CHAIN_NOT_VERIFIED`. Its exact NET, week counts and sampled/certified-as-claimed drawdown are descriptive, not authoritative source or execution verification. Before an eventual admission API is created, it must validate, under protected custody:
- authenticated Pepperstone account identity, every required original source asset SHA256 and decrypted plaintext identity, and actual week-level time coverage;
- same-input input-source digest, frozen causal program/parameter digest and chronological train/selection/untouched-confirmation authorization;
- each completed broker position, partial-fill and recovery identity, observed executable bid/ask, tick/lot, margin, actual commissions/financing/conversion, cashflows, true floating equity extrema and a *conservative verified* drawdown envelope;
- prior objective eligible-week registry and the closed-round-trip portfolio counts;
- parity between a trusted protected source replay and identical shared C# logic. Input booleans, unsigned hash strings, private development archives and unit tests cannot mint this admission.

This is a deliberate security boundary, **not a claim that a qualified strategy exists**.

## Native risk capacity without legacy limits

`PortfolioRiskBudget.Assess` accepts a reconciled current broker account, a certified upper bound on the historical equity peak, complete existing open-position worst-loss and margin bounds, and a candidate's verified worst stop/gap cost and margin. It sums losses conservatively (no unproven diversification benefit), requires available margin and strictly positive drawdown headroom below 30%, and permits *any number of simultaneous positions* when warranted by actual broker capacity. It rejects missing history, ambiguous order outcomes, invalid identities and unbounded costs; it issues **observation-only** decisions. No 2 EUR per-entry, 80 EUR margin, 120 EUR reserve or one-position restriction has been added.

`CausalSourceCalendar.Assess` supports arbitrary authenticated-data timeframes via an explicit bar duration, not H1 only. It calculates observed real calendar weeks, detects exact overlaps and gaps separately per symbol/timeframe and never labels source-clock support as ex-ante HARD21 eligible weeks or broker executable fills. `Mxm.Replay` now includes the H1 source's observed calendar support and discontinuities as *source-only receipts*.

## Original archive cold reception (no strategy evaluation)

A private, pre-existing derived PRIMARY145 native C# tape was read in this ChatGPT execution from the OWNER's Library, after exact SHA256 verification against its frozen historic authority: `7157db48811ed1f1e4583ab567c6e04c876a4c4738c4bd242f182632fff54ebb`. Exactly 32,607 complete, availability-dated H1 events across eight fixed historic forex instruments passed timestamp checks; 36 distinct observed UTC ISO weeks with 535 successive hourly discontinuities, date range 2025-09-28 through 2026-05-31. The results were recorded as **only privacy-safe aggregate clock metadata** in `PRIMARY145_H1_CLOCK_ONLY_COLD_RECEIPT_20261102.json`.

The tape is a pre-existing, development-exposed derivative of original PRIMARY145 M5 archives, *not* the full 145-series year, a fresh holdout, genuine broker fill evidence or economic qualification. No original source prices, positions, per-event targets or private keys were published, no rejected model rerun. The private tape was read from the OWNER Library in this chat's isolated execution, **not** in GitHub Actions; GitHub CI checks the actual new C# implementation and the existing public 100-archive identity source only.

## Operational continuity

The final cBot remains observation-only with no trading/order modification path. Historic account/custody secret inconsistencies remain unresolved until the two exact original values are replaced in existing environments; this change intentionally does not launch a protected source run. No external provider messages are sent. `main` GitHub rule administration is not exposed by the current connector; PR+CI+expected-head merge remains the supported safeguard, not a substitute for formal protection.

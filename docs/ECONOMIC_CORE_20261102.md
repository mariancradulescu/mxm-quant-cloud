> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# Economic and native causal core — November 2, 2026

## Material implementation (not an acceptance claim)

`src/Mxm.Core/PortfolioEconomics.cs` introduces a C# EUR200 funded, portfolio-wide NET evaluator, with explicit gross, both commissions, executable slippage, financing and currency conversion charges. Any missing charge or incomplete opening/closing history **rejects** the evaluated round trip; duplicate/conflicting position identities are not counted twice. Multiple simultaneous positions are permitted. Development, selection and independent confirmation have strictly increasing UTC boundaries. The full study requires at least 12 calendar months, not the annualization of a shorter capture.

HARD21 counts all complete system-level round trips by **position ID** in each predeclared full UTC confirmation week, never partial exits as separate trades. An empty eligibility roster or any eligible week with fewer than 21 complete closures blocks admission. Nothing generates trades to meet the minimum.

Observed liquidation-equity sample drawdown is reported separately from a conservative upper bound derived from **independently certified** all-time liquidation-equity floor and peak upper bound. A sampled observed drawdown is not accepted in place of intra-mark extrema. The certified bound must be strictly below 30%, including floating risk and costs. Underlying proof must independently establish authentic Pepperstone history, ongoing account/funding, executable prices/fill size/margin/slippage, full EUR costs and FX, pre-outcome eligibility, chronological selection discipline, independent NET advantage and equity/balance reconciliation at flat boundaries. Boolean proof declarations themselves are not independent evidence and do not qualify a dataset.

`src/Mxm.Core/CausalRangePressureResearch.cs` is a **distinct, not-yet-evaluated** online next-H1 direction hypothesis. The shared C# state processes only completed, time-stamped bars; updates its coefficients only after the predicted target bar closes; resets on missing H1 intervals; prevents cross-symbol adaptation and refuses malformed input. It emits bounded observational probabilities but no order intent or executable trade policy. The source-admission `Mxm.Replay` C# program now counts these experimental forecasts only, labeling the output `UNQUALIFIED_OBSERVATION_NO_TRADING`. Neither probabilities nor forecast counts constitute after-cost advantage.

`research/legacy_manifest_remote.py` verifies the real original release **metadata**, pinned to old source commit `0e5349115de72f9824986acb00cdb410a3097dcf`: complete manifest, 100 original encrypted shard names and SHA-256 digests against 100 live GitHub Release asset digests, original 3,355,389 declared rows and exact identity. CI uploads only a sanitized public receipt. **No encrypted shard is downloaded or decrypted by this verifier.** The coverage is 2026-08-20 through 2026-09-16 (four seven-day segments), and this cannot establish 12 calendar months. Old Annual157 and other rejected economic candidates are not imported or relaunched.

## Security and boundaries

The same workflow retains environment isolation, owner/main event gating, strict SCOPE_VIEW, exact LIVE Pepperstone account binding and original RSA public key. A source-admission request must now modify **only** the explicit marker file; mixing executable-code changes with a secret-enabled request is rejected. Normal PR and push verification never receives the environment secrets. The source-provenance checks above are independent of the incorrect destination private key and account-binding secret; they cannot and do not bypass either.

The C# observation-only .algo continues to stop on startup. No new order entry, order close, order cancel, Cloud activation, live/demo order, broker correspondence, credential, keypair or external service has been added. Native Cloud restart reconciliation and the final portfolio execution controller remain **open**, not certified.

## Remaining scientific work

After correcting the two existing secrets strictly from their historic originals, read-only custody can decrypt and reconcile authentic archived and/or newly admitted source on the protected runner. Complete broker costs, execution constraints and at least twelve months of source must still be established before the native portfolio evaluator is permitted to produce an independently supported NET/HARD21/drawdown verdict. The existing 28-day archive and present H1 admission are insufficient. No synthetic test or successful CI run changes this status.

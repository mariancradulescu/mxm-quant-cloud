# Frozen new-source causal C# score — 2026-11-02

## Scientific question / fixed before scoring target outcomes

One single historical **new-data** read-only execution has successfully authenticated the original LIVE Pepperstone account and sealed its H1 integration sample under the newly derived v2 custody recipient: GitHub Actions run **41467047520**. That run also independently passed the original C# source-receipt parity and is preserved as the new source for this cold study. Nothing from the older PRIMARY145 or MASTER1576 economic screens is selected or replayed.

This study evaluates the **already-implemented** causal H1 range-pressure hypothesis in `Mxm.Core/CausalRangePressureResearch.cs` (PR #4), without parameter modification or candidate cherry-picking. The hypothesis existed before the new read-only sample was collected. It remains a developmental *candidate*, not a restriction on final multi-timeframe research.

The **prequential** assessment reports:
- For each fixed source symbol, the forecast must exist before the NEXT complete H1 bar arrives; no future outcome at prediction time
- A gap cannot be filled or scored; the underlying predictor resets its warmup/adaptation after missing H1 intervals
- The realized label is up/down/tie of the next completed source close versus the prior close, not an assumed executable entry or exit
- Mean Brier score `mean((probabilityUp - realizedUp)^2)` versus the frozen unconditional 0.5 probability baseline
- `1 - (modelBrier / neutralBrier)` skill where neutralBrier is positive
- Entire pooled scoring output is suppressed if fewer than 100 causally scored targets

No trading sign, threshold, return/stop/TP/SL, transaction frequency, portfolio selection, funding, fees, currency conversion, margin or position sizing is inferred from this score. Even a positive Brier skill is **not** proof of economic NET advantage, 21 completed executable trades/week, drawdown <=30%, a full year of authentic source or untouched confirmation. Negative/non-positive skill closes this particular exact H1 candidate without post-hoc inversion or retuning. Other independent hypotheses and timeframes remain unrestricted.

## Exact protected source reuse — no broker recollection

The normal GitHub Actions workflow introduces one mutually independent **cold-source** job, guarded by an exact owner/main push with the exact `ops/cold-score-request.txt` file-only commit and subject `MXM_COLD_SOURCE_SCORE`. The secret-free verify job must pass before the protected `mxm-r3-custody-v1` job runs. It downloads the existing **sealed-source artifact** from **run 41467047520** using read-only GitHub Actions permissions. No request is made to cTrader/Pepperstone. The installed existing private key unseals v2 after validating the original run binding and ciphertext hash.

The machine first replays the **unchanged default** two-argument native C# source receipt and requires exact parity with the original protected run's frozen native result. Only after this independent original parity, the `--score-causal` C# mode computes its separate score. Only privacy-safe pooled aggregates are uploaded in `causal-cold-score-public-only`. Raw bars, broker account identifiers, source keys, private signal/label rows or decryptions never leave the protected job.

No original annual archives are decrypted; no new keys, account identities, external services, orders or Cloud activity are created. The final cBot remains observation-only and all economic admission gates remain blocked pending authentic executable fills, NET fees/slippage/financing, EUR200 funding, HARD21, certified risk, complete >=12-month history and independent chronological confirmation.

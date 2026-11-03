> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# MXM — EUR 200 genuine NET gap and selective Cloud recovery (2026-11-02)

## Economic finding boundary, fixed before accessing sealed broker contracts

Prior completed authentic Pepperstone Europe LIVE `SCOPE_VIEW` collection **41476636915** contains 15,113 real market H4/M15 bars, 13 observed H4 month buckets for each of six account-enabled instruments, original symbol contracts and a *single one-minute historical BID/ASK snapshot*, all sealed with the installed RSA custody recipient. PR #9–#12's fixed 819 OHLC gross-price proxy episodes **are CLOSED for retrospective optimization**, and are NOT rerun here.

The new core `ExecutableNet` supports true source-linked, single-position **EUR quote-side economic arithmetic** with direction-correct BID/ASK, minimum/step volume, account balance EUR200 / no additional deposits evidence, source SHA, genuine entry/exit time verification, quote->EUR conversion at settlement, entry and exit commissions, *conservative upper bounds* for financing/slippage/FX, and verified broker margin/free margin. It reports price gross, adverse net lower bound and fundability as **diagnostics** and always leaves `EconomicQualified=false` because supplied data alone cannot prove a real fill or complete policy/portfolio confirmation. Missing inputs stop computation; synthetic test values never count as observations.

`AuthenticatedNetCoverage` reports **only source-derived availability** of broker minimum lot/step, commission metadata, swap metadata, conversion fee metadata and bid/ask tape presence. It flags no event-specific executable fills, FX conversion, upper-bound slippage, broker minimum margin and no funded EUR200 portfolio history. Its final NET EUR is **null**, not zero; historical reported 21 weekly proxies are not broker round trips.

One protected *read-only cold audit*, gated by exact OWNER main marker `ops/net-coverage-request.txt` / commit message `MXM_AUTHENTIC_NET_COVERAGE`, reuses precisely the original encrypted source artifact from run **41476636915**. It first repeats the original native C# source reception **bit-for-bit equivalent JSON** and then calls a separate `--economic-net-coverage` mode, publishing only small contract and availability aggregates. No new Pepperstone request, credential, key, historical strategy rerun or market account data exposure. All computations use the existing .NET 6 core shared with a single C# cBot.

This is a **material funding/NET feasibility audit**, not a NET economic success. A 13-month observed H4 span is development-only; it is not pristine chronological independent confirmation.

## Cloud: autonomous selective recovery instead of permanent Stop()

`SelectiveRecovery` defines native account-wide and per-symbol observation/reconciliation admission states. A transient broken market-data snapshot on one symbol is automatically reevaluated on the next healthy native snapshot; healthy independent symbols can remain **eligible for further risk review** only if global account, funding, certified peak and *all worst-case unresolved exposures* are bounded. The coordinator has **max one verified in-flight request** and reserves unknown-order *worst possible margin and loss* against remaining free margin and 30% drawdown headroom.

An ambiguous submission is never automatically resent. **Absence from history, positions or pending orders is not definitive proof of absence**. It only clears after affirmative broker-terminal evidence and full account reconciliation. Unbounded uncertainty or uncertified historical intents after restart denies *new risk globally*, while account monitoring and automatic reconciliation remain active. One transient local fault does not globally stop observation.

The single cBot `MxmCloud.cs` now uses native `Timer.Start(15)`, `OnTimer`, `OnException` and protected native snapshot retries, without calling `Stop()` on every startup/recoverable exception. **It contains no order submission, modification or closing APIs whatsoever**. The delivered .algo is still **OBSERVATION-ONLY**; it does not claim it has proven cashflow completeness, historic in-flight request nonexistence, equity lifetime peak or safe autonomous trading. Consequently, actual cBot execution remains restricted until these provenance gaps can be certified natively. It has no external Python/GitHub/Desktop dependencies at runtime.

Synthetic C# tests cover: transient symbol recovery while another lane remains eligible; unbounded ambiguity globally blocking new risk; missing historical in-flight provenance after restart; explicit positive broker terminal resolution restoring a quarantined symbol; total concurrent request limit; 30% headroom; and strict EUR200 cost arithmetic. They prove kernel behavior **only**, not actual broker recoverability in cTrader Cloud.

No LIVE/DEMO orders, Cloud activation, or emailing brokers is authorized or performed.

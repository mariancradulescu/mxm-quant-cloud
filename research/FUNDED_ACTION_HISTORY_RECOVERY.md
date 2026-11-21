# Original funded history: custody-only partial recovery

## Unaltered provenance
The 20–21 November 2026 original [Actions #44824462289](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44824462289) is `FAILURE`, not a successful complete historical source. The original public receipt is `SOURCE_FAILED_CLOSED`, `INTEGRATED_HISTORICAL_REQUEST_REJECTED`, NAS100 `TICKS` `ASK` 2026-10-09 01:00–02:00 UTC, provider `UNKNOWN_ERROR`. The original ZIP #14681352119 is 869032678 bytes; GitHub reported its SHA-256 `5f6b232d2e8b892da3e9488399f65c72fe1bb2ff8c908dfff3e9f2661d81dec8`. This is an archive-level report, **not** yet independent on-run unseal/readback evidence. The original public receipt artifact is #14681397091. Original request count is 30473; original public shard inventory has 606 entries. The original readback was skipped, not passed.

All original artifacts, the original receipt and its failed status remain immutable.

## New recovery: no broker access
`research/funded_history_recovery.py` executes exclusively in the existing protected **custody** environment with the original source run ID fixed at `44824462289`. It downloads the two untouched original artifacts from that run and reads no live account or history source. It verifies:
- original run, protocol digest, funding-universe scope, custody inventory, all ciphertext SHA-256 and compressed-plaintext SHA-256, Pepperstone/EUR provenance, account and instrument bindings;
- every stored original read-only Protobuf request and response, native period and timeframe windows;
- the binary preorder `hasMore` page tree, side, interval, terminal page and genuine `NO_QUOTES` response;
- full BID and ASK evidence for each active hour, and original counters for an instrument only when its whole source is complete;
- exact missing or provider-rejected *leaves*, rather than recollecting completed siblings, roots, days or complete instruments.

If any binding, hash, counter or unexpected response fails, the recovery fails closed with a separate public `recovery-failure.json`. It never changes `source.json`. Successful recovery publishes three **new** artifacts: `coverage-manifest.json`, `gap-requests.json` and `recovery-receipt.json`; they contain counts, hashes, timestamps and query statuses, never raw decoded quotes, private keys or account identifiers. A missing page, `UNKNOWN_ERROR` or partial tree is never a terminal `NO_QUOTES` or a complete trading hour.

Original public counters that must not be mistaken for verified completion: EURUSD 1560, GBPUSD 1560, XAUUSD 1493, SpotBrent 1388, US500 1491, AAPL.US 448 and AUDUSD 1560 accounted source-tick hours matching their reported active hours. NAS100 reports 1238/1491, a 253-hour difference. All these numbers await independent shard readback.

## Readback trigger and permission boundary
`.github/workflows/funded-history-partial-recovery.yml` allows tests on PRs; its protected job is authorized **only** by a new, exact, first-addition marker-only commit to main authored by the OWNER, on first workflow attempt, with subject/content:

`OWNER_FUNDED_HISTORY_ORIGINAL_PARTIAL_CUSTODY_READBACK_ONCE_44824462289`

Marker path: `ops/funded-history-original-readback-once.txt`. This marker authorizes **only existing-artifact custody readback**, explicitly authorized by the OWNER on 21 Nov 2026. It is not an Open API collection marker. The original one-time marker and `run_attempt == 1` restriction remain untouched.

## Separate future backfill: NOT authorized
The `gap-requests.json` artifact is an *unsigned candidate manifest*, not execution authority. Every proposed interval must be validated as genuinely missing after fully unsealing the original, deduplicated per (instrument,timeframe,side,start,end) and bound to the original source and SHA-256. Any future protected Pepperstone read-only job must have a separate new immutable marker, workflow, request budget, rate limit, finite retries and an explicit **new OWNER approval of the exact marker** before launching. Never reuse the consumed original marker, never rerun the original workflow and never overwrite original shards. The future marker has **not been issued** here.

The documented cTrader Open API limit is 5 historical requests/second/connection, not a license to issue requests. `NO_QUOTES` is an actual provider error code; `UNKNOWN_ERROR` is not market data. See [Open API documentation](https://help.ctrader.com/open-api/), [error handling](https://help.ctrader.com/open-api/error-handling/) and [ProtoOAErrorCode](https://help.ctrader.com/open-api/model-messages/). Recovery retries must have finite backoff and preserve all responses and request provenance. Failed transport is not terminal history evidence.

## Economic / C# boundary
The existing `NativeFundedActionValue` and common funded C# portfolio engine remain the authority for ENTER/WAIT and CLOSE/KEEP. Seven fully verified instruments may be enabled for **development**, once private verified replay inputs are available, without declaring any historical independent economic success. NAS100 remains partial until a protected readback and authorized gap-only collection prove otherwise. No historical scope or instrument selection is chosen ex post based on P&L. CASH, FIRST, hash, pooled, placebo, entry-only, contextual and ablation comparators and a single 300 EUR funded ledger per policy remain required for a separate protected evaluation, which is **not** authorized by this recovery. No orders LIVE/DEMO; no Cloud activation; Issue #393 remains open.

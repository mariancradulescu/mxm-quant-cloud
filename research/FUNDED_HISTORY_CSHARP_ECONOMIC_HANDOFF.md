# FAV authentic 13-week C# development — executable handoff (2026-11-21)

Authority remains `docs/OWNER_SPEC.md` and Issue #393. This is the next phase of the existing project, **not a restart or new economic study retrospectively retuned from P&L**.

## Original evidence and source lock

- Original read-only source Actions #44824462289 stays **FAILURE**. It contains original encrypted artifact #14681352119, original public #14681397091 and original `SOURCE_FAILED_CLOSED` status.
- Already executed custody readback Actions #44910122403 **SUCCESS**, artifact #14709905618 (archive SHA-256 `de2b998117180e9e364be5d9e7d81851449db4ab0a8dc8dee3e94244fa885f64`). Original source `source.json` SHA-256 `35172df63e3e9c147139b836dea5eac989fad3ab8f267d42677c9de5162cf952`, recovered manifest `e35cfc1d9988f6dc166a7f27349fefedb64fc1f251358761a69dd44e72ae8dbd`, gap plan `03ea1a9d06bdcb7e028c77fa9e360ab36e1dae2b451dc8cc76c16c57091af8b0`, recovery receipt `877955b29edf208210ea04748422ea18a00e40723b2759366e45078ea02389dd`.
- Original 606 sealed shards and 30,473 requests already verified. **Do not rerun that completed recovery.** The next protected development runner independently rechecks the entire original source against its recovery manifest before materializing only complete instruments. Incomplete NAS100 does not constrain those seven genuine complete rosters.

## Single protected authentic-source-to-economic path

`research/funded_history_economic_development.py` and `.github/workflows/funded-history-economic-development.yml`:

1. Securely acquire original ciphertext, original failed source receipt and previously verified public recovery receipt/manifest from their pinned run IDs. Match fixed SHA-256 of the original public source, manifest, gap plan and recovery receipt.
2. Verify original status and read-only source scope, recalculate all shard hashes, decryption, raw request identities and BID/ASK terminal trees via existing `funded_history_recovery.scan`. Reconcile the **exact** recovered manifest and 263 gap-leaf records.
3. Reuse `integrated_market_readback.readback(..., include_markets=...)` for only the independent **response-complete** EURUSD, GBPUSD, AUDUSD, XAUUSD, SpotBrent, US500 and AAPL.US. The unselected original NAS100 stays sealed and partial, and any malformed selected shard fails closed.
4. Materialize genuine as-of paired BID/ASK with M1/M5/M15/M30/H1 in an ephemeral permission-restricted directory. Reconcile accepted complete 30-second paths with the recovery report, emit a hash of **private** Replay input (not private input). Do not reset cash between days or temporal chunks.
5. Execute **existing native C#** `Mxm.Replay --funded-action-value-historical-conditional` on the source from **2026-07-27 through 2026-10-26, end-exclusive**, with causal fits and calibrations and all eight preregistered competing policies from `NativeFundedActionResearch`. Each policy has an independent continuous EUR300 common portfolio (not pooled profits). Native `RunHistorical` carries its book and updates training only from settled labels.
6. Keep full C# input and full detailed ledger privately temporary. Publish **whitelisted** policy-level central/adverse after-cost NET, CASH/FIRST deltas, weekly completed funded closes/HARD21, gross and costs, exposure/margin/risk, censure, model calibration and cohort support, per-family/per-symbol **aggregates**, sampled floating-equity drawdown with explicit `ContinuousFloatingDrawdownCertified=false` and SHA-256 receipt. No raw quotes, account identifiers, private key, OAuth token, ledger event traces or model snapshots enter the public artifact.

**Financial epistemics:** capture-date broker terms are a historical *conditional cost assumption*, NOT contemporaneous fee/margin/financing observations. Raw historical BID/ASK and bars are authentic as acquired. The result is development with possible censure, NOT 12-month independent proof, executable broker NET, or a live/cloud trading authorization. A CI SUCCESS only verifies code and fixtures; the economic result requires the distinct one-time protected run.

### Future economic marker — OWNER approval still required

File to be added **only after independent PR audit and a new distinct OWNER approval**:
`ops/funded-authentic-13w-csharp-economic-once.txt`

Commit **subject and exact file content with trailing LF**:
`OWNER_FUNDED_AUTHENTIC_13W_CSHARP_ECONOMIC_CONDITIONAL_ONCE_44824462289_44910122403`

The workflow requires one first-addition commit touching **only** that file, `main`, `GITHUB_ACTOR=mariancradulescu`, `GITHUB_RUN_ATTEMPT=1`, and exclusive `mxm-r3-custody-v1`; no Pepperstone secrets, no orders and no Cloud activation. **No marker created in this PR.**

## NAS100 parallel — exact gaps only, not run

`research/funded_nas100_gap_collection.py` with `.github/workflows/funded-nas100-gap-only.yml` accepts exactly 263 originally verified NAS100 TICKS gaps (131 BID missing, 131 ASK missing, one ASK original `UNKNOWN_ERROR`). All seven other instruments and already verified NAS100 leaves are out of scope. Current Open API historical limit is [5 requests/s/connection](https://help.ctrader.com/open-api/); collector is limited to 1 start every 250ms, 2048 market requests total, max 24 split levels, 3 retries per leaf and 50-minute wall time. No unlimited retry or synthetic `NO_QUOTES`. Every new provider attempt is separately encrypted with the existing custody recipient. Separate protected custody step checks the original encrypted account identity, hashes and exact leaf parent-child response pages before declaring any new source gap resolved. It never overwrites the original #14681352119. This new collector and protected readback have **not** been exercised against Pepperstone.

Future marker **proposal only**, `ops/funded-history-nas100-gap-only-once.txt`:
`OWNER_FUNDED_HISTORY_NAS100_GAP_ONLY_READ_ONLY_BACKFILL_ONCE_44824462289_44910122403`

No such marker is added or approved; workflow broker stage requires explicit **separate** OWNER decision.

## Durable private retention prepared, not authorized

Original GitHub Actions artifacts expire in February 2027; a 90-day GitHub upload is not indefinite archival. `research/funded_history_archive_verify.py` verifies original encrypted ZIP SHA-256 `5f6b232d2e8b892da3e9488399f65c72fe1bb2ff8c908dfff3e9f2661d81dec8`, the entire 606-member cipher inventory, and the public source and recovery ZIP SHA-256s. `.github/workflows/funded-history-archive-encrypted-private.yml` is a separately owner-gated option to copy **already encrypted original ZIP and safe receipts only** into a private, versioned, S3 Object Lock-enabled bucket with KMS encryption and 2030 retention, and check remote SHA-256. No plaintext, private RSA key or tokens are uploaded.

This requires explicit approval of the storage provider/cost and provisioning five scoped environment secrets: `R3_ARCHIVE_AWS_ACCESS_KEY_ID`, `R3_ARCHIVE_AWS_SECRET_ACCESS_KEY`, `R3_ARCHIVE_AWS_REGION`, `R3_ARCHIVE_BUCKET`, `R3_ARCHIVE_KMS_KEY_ID`. Provision a private versioned S3 Object Lock bucket and narrow IAM rights for these three immutable objects only. Do not execute before storage controls and budget are accepted.

Archive marker **proposal only**: `ops/funded-original-encrypted-s3-archive-once.txt`, subject/content:
`OWNER_FUNDED_ORIGINAL_ENCRYPTED_S3_ARCHIVE_ONCE_44824462289_44910122403`

## Acceptance and independent audit before protected execution

- Verify Python synthetic integrity/replay subset/missing-censor/gap plans and C# Replay/Cloud Release builds. Inspect CI and PR head exactly.
- Confirm no marker files in this PR and zero protected runs or Open API requests.
- Inspect original `NativeFundedActionResearch.RunHistorical` training chronology and true single funded book per policy. Do not promote fitted model without authentic financed NET and risk.
- Audit output fields to ensure raw ticks/prices and account secrets never leave protected custody.
- Approve economics marker separately (next OWNER decision); NAS100 and archive markers have different authorization boundaries. Issue #393 stays open.

All older original studies, results, parameters and SHA-256 artifacts remain unmodified. Zero LIVE/DEMO broker orders, zero Cloud activation.

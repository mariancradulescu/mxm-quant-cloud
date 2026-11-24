# Funding provenance DEVELOPMENT after PR #447 — 2026-11-24

No new economic evaluation, no change to original CPE1, no trade, no Cloud. Source artifacts are not a qualified economic result.

## Official source investigation

- [Spotware Open API messages](https://help.ctrader.com/open-api/messages/): SymbolByIdReq returns a contract by ID, not a tariff as-of date. Historical deals are executions, not the tariff series for hypothetical positions. No historical swap tariff series request is documented.
- [Spotware Open API models](https://help.ctrader.com/open-api/model-messages/): percentage is annual; swap time is a UTC minute; period, triple day, weekend and skip fields are distinct.
- [Spotware public server model](https://help.ctrader.com/plugins/developers/all-apps/sdk-references/public-server-model/): percentage formula uses volume, bid, annual percent, 365, day multiplier and quote-to-deposit conversion, HALF_UP.
- [Pepperstone index fees](https://pepperstone.com/en/markets/indices/index-fees): general index formula instead uses market closing price and 360. Not account/date-specific and no historical rate table.
- [Spotware conversion](https://help.ctrader.com/open-api/symbol-rate-conversion/): conversion chain is not itself the dated execution conversion or a price bound. SymbolsForConversionReq is not in the existing 11-request allowlist; no expansion or bypass here.

The five archived authenticated 2026 sources in #45376822819 do not attest 2025 tariff continuity. IDs NAS100=126, US500=127, USD. Snapshot -6.41/+1.41 or -6.42/+1.42 annual percentage, 24h, 1320 UTC minute, triple Friday, no weekends, no skipped periods are only observed 2026 values. Do not apply to 17/24 Nov 2025. No authenticated effective window, confirmed applicable 360/365 formula, dated rollover price, conversion/rounding, or enforceable debit maximum has been recovered. Do not create a numerical maximum from observations or add an arbitrary cushion. Broker archive availability outside the documented API is unconfirmed, not asserted impossible. A broker statement of executed swap is not a tariff for a hypothetical trade.

## Implementation and remaining gate

The new point collector uses original account authentication, P05 socket guard, existing sealed custody, roster name/ID and EUR identity checks, per-request sent/received UTC times and original request/response protobuf. It does not infer validity intervals or emit NativeFundingOfferEvidence/NativeAccruedFundingEvidence. It is a bounded source-only entrypoint; collection is wired into the existing P05 workflow under a distinct first-addition marker and reuses the existing protected recipient and read-only environments. Offline tests are not authentic observations. No marker or economic authorization added by this change.

Required before a point may become funding evidence:
1. Original sealed packet readback under custody; hash actual bytes, parse protobuf; reconcile account commitment, exact symbol, clocks and trusted source identity. Reject substituted packet, wrong account, side/volume, stale/future/missing clock and unsupported interval. Public receipt alone is not evidence.
2. Obtain broker-attested applicable tariff effective interval or enforceable cap, price basis, rollover/calendar, FX conversion and rounding. Polling alone cannot prove uninterrupted tariff validity or finite cap between polls.
3. Convert to exact signed EUR or a supported exposure-specific maximum, then bind to the position ID, direction, volume, actual accrual window and availability clock in the common C# engine. No adapter output if evidence incomplete. Reconcile FINANCING, Held + Pending, CLOSE_FILL, closed outstanding liabilities and capital, including checkpoint and post-close cases.
4. NativePortfolioFunding currently validates only hash format, not source/account. Further, Observe retains a nonzero late exact delta for a closed window as a debit ceiling; NativeFundedLedger FINANCING requires an existing held position. This needs an auditable closed-position reconciliation path, not a claim of complete NET on the basis of a known bound. Never rewrite old CLOSE_FILL or erase unresolved debt.

Prospective collection can extend this same read-only entrypoint under a separately audited source-only cadence, but must preserve gaps as gaps. No need to wait 53 weeks for DEVELOPMENT work. Confirmation remains separate.

## Immutable episode readback

Downloaded ZIP #14909305890 SHA256 f23fb4616f044086b130343cc8a52adeb20bdbe82c9976020208d71e7d1e8318 verified; separate reproducible readback script checks both ZIP and original result hash. ECONOMIC 1.5x, NAS100 LONG 0.1 units, EQUILIBRIUM_REPAIR, decision 1763338800000, fill 1763339100000, close 1763343600000 (epoch milliseconds, see readback). Admission risk EUR 0.5877143941; fill risk EUR 0.1480538494; admission reward EUR 2.3411216392; fill reward EUR 2.7798723521. Gross EUR 9.6734458313, conditional net EUR 9.2535112810, MFE 10.0297821750, sampled MAE 0, margin EUR 126.5, residual USD notional 2505.2212097871, duration 75 minutes. Net/fill risk 62.500984, net/admission risk approximately 15.74. Cost EUR 0.41993455 exceeds fill risk. Absolute stop and target price levels and intrabar path are not included in the episode. Frozen engine fill rechecks geometry against prior stop/target; do not infer missing absolute levels from rounded ratios. No retuning.

Matched original conditional-net pairs by instrument/family/direction/decision clock/fill clock/volume: 8 each. ECONOMIC minus SIMPLE: -1.6800312240 (1x), -1.7060658620 (1.5x), -1.7062291360 (2x). US500 SHORT target exit in SIMPLE vs later structural stop in ECONOMIC explains -1.6800/-1.6802/-1.6803. AUDUSD SHORT later continuation failure versus target adds -0.0259 at 1.5x and 2x. Different portfolio selection and truncation mean unmatched totals do not isolate management value. No demonstrated repeatable advantage over SIMPLE or CASH; positive provisional results are not complete NET. Original remains closed.

Next full evaluation: NOT AUTHORIZED until authentic funding provenance, native ledger settlement including late exact delta, source parity and floating-equity coverage demonstrated. Continue DEVELOPMENT only, original unchanged.

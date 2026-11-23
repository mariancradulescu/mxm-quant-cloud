# PAV1 integrated corrective forensic: original FPE1 margin and immutable evidence

**Read-only investigation, not an FPE1 rerun.** Existing original run #45184613202, artifact #14823775829, SHA/ledger chain and failed economic verdict unchanged.

## Exact source-code defect

In the immutable FPE1 Core `NativeFpe1CompletePositionEconomic.Fundable()`, capital admission computes `reserved` and `usedMargin` by summing `book.Held.Values` only, while `book.Pending.Values` may already contain accepted `Kind=="OPEN"` at the SAME economic clock. Every additional `REQUEST_OPEN` therefore sees already accepted pending reservations as zero available-credit usage; `NativeFundedLedger` correctly checks actual equity versus total margin at later modeled `OPEN_FILL`, but is not itself configured to apply the separate 70% research admission cap. Thus same-clock legally sized concurrent requests can accumulate above the intended research margin envelope without violating the broker funding-only check.

The original public FPE1 artifact reports:
- COMPLETE_VALUE x1 peak sampled modeled margin **291.50 EUR**.
- NO_VOLUME x2 peak sampled modeled margin **300.86 EUR**.
- Initial simulated account **300 EUR**, internal admission margin intended at most **70% of contemporaneous equity** (210 EUR at founding equity). The peak values alone cannot prove the *contemporaneous* equity fraction without matching marks. The code defect is independently visible.

## Precisely reconstructable original position overlap (NOT the margin-peak timestamp)

Based solely on immutable `NativeCompleteResult.Results[].AllCompletedPositionLifecycles` and the corresponding closed fragments (timestamps/position IDs/units), the maximum **completed lifecycle overlap** is:

- COMPLETE_VALUE x1: **five** open positions at **2025-11-03 05:30:00.200 UTC**: EURUSD LONG 1,000 units; US500 SHORT 0.5 units; GBPUSD LONG 1,000; AUS200 LONG 0.2; USDJPY SHORT 1,000.
- NO_VOLUME x2: **three** open positions at **2025-11-03 04:35:00.201 UTC**: AUS200 LONG 0.4; USDJPY SHORT 3,000; EURUSD LONG 3,000.
- The FPE1 receipt contains no timestamped peak-margin equity/contract quote nor full original REQUEST_OPEN / OPEN_FILL intent journal. The above overlap timestamps are **NOT asserted to equal the maximum-margin timestamp**. Exact instrument-by-instrument contribution to 291.50/300.86 EUR cannot be reconstructed from this public economic package alone. Re-running closed FPE1 to manufacture it is explicitly forbidden. This is a bounded original-evidence limit, not a source-impossibility claim.

## Forward correction within the *single* new PAV1 programme

- Every candidate proposal is checked by common native C# `NativePendingCapitalGate.Assess()` against *Held + PendingOpen* at **current observed liquidation equity** with 70% margin reserve, 1.5% per proposed legal volume stop risk and 5% aggregate stop risk.
- Pending OPEN commitments persist through all simultaneous candidate decisions and are released only at modeled OPEN_FILL (replaced, not duplicated by HELD) or explicit failed/unfilled expiration.
- A REQUEST_CLOSE or partial REDUCE does not free held margin/risk before actual CLOSE_FILL; no phantom capital.
- Prior to next-bar OPEN_FILL, quote-side margin and risk are revalidated together with every other Held + Pending; insufficient equity cancels that particular untransmitted model open, preserving the other commitments.
- Exact **new** eventwise capital witnesses (request/real fill/reject/close/partial reduction/expiry), equity, Held, Pending, risk, limits and the event-ledger chain are part of the PAV1 economic receipt. Trade counts are legal completions only and do not include requests or shadow labels.
- Synthetic tests include two simultaneous OPENs, rejected third 70%-excess request, pending expiry release, unfilled CLOSE preservation, risk budget, legal broker volume grid, missing marks, reduced equity at fill. These tests are safety checks, not positive economic outcomes.

All original FPE1 code, values and cryptographic receipts remain intact. PAV1 outcome will use a completely newly preregistered action-value mechanism and will not be described as independent from historically exposed 2025–2026 data.
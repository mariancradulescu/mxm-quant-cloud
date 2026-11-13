# MSE1 Coffee — postclosure technical diagnosis; ORIGINAL UNCHANGED

**Status:** forensic reconstruction, **not** a replay, performance restatement,
independent confirmation, broker execution evidence or a new admitted strategy.
OWNER v2.0 after PR #254. Original run [#43366399346](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43366399346)
and original financial artifact `#14010653603` and encrypted source `#14010693489`
are immutable. Original main SHA: `39055893248a250fc129c353c91b00f83c3c3613`.

## Original custody / proof boundary

- Public receipt content SHA-256: `53db93ff14866b703ea77051e9859033df39e17401991d485e2323f13feb3535`.
- Original public artifact ZIP GitHub digest: `404e9aa67e5498edf50a2abd570968798ba958cc0adafa92c14fcd07896f9a78`.
- Original encrypted source artifact ZIP GitHub digest: `3538ecca5d03e376c6446e6aa66754e532766f18ef4e9a0cfac866c184f620ea`.
- Original input plaintext hash as **reported by the original receipt**, not independently decrypted here: `068cf7a396d0cddfc59b856f95f930b7bff83eddef4c8beae556243e168c4f7e`.
- Original encrypted payload SHA-256 reported by receipt: `e10bec88a954d11d7a68d8079dcf382084aecf6a7cdc474e76f37db93fd1cf29`.
- Original protocol SHA-256 reported by receipt: `df5260278403f56cc2f9cd7f9d9d1d285f44f2bba7e9e99bb89bfcaf5ef4539e`.
- Original evaluation: nine funded modeled closes; central NET -63.42292174446085 EUR; adverse NET -70.2639699197088 EUR; initial 300 EUR, final modeled central 236.57707825553916 EUR. Coffee-only one close, -60.74581404553355 EUR central, -67.26618024126242 EUR adverse; maximum observed margin 249.315 EUR, or 83.105% of 300. Overall sampled adverse drawdown 28.57350579035443%; **32 sampled equity clocks unknown**, so continuous max drawdown is NOT certified.

## Exact-clock reconstruction from the unchanged public financial receipt

The native replay uses quote clocks ending in **01.500 UTC** and `MSE1`
reports its longest completed holding of **1,350 minutes**. Its sampled
joint book shows the high-margin Coffee position first at **2026-09-02
15:35:01.500 UTC**, continuing through **2026-09-03 14:00:01.500 UTC**.
The only consistent close under the reported 1,350-minute duration is
**2026-09-03 14:05:01.500 UTC**. This is a reconstruction from the
original public receipt, **not independently inspected trade-by-trade
encrypted plaintext**.

- Entry: **2026-09-02 15:35:01.500 UTC** (inferred from first held margin).
- Declared 120-minute protective expiration: **2026-09-02 17:35:01.500 UTC**.
- Broker weekly Coffee schedule *retrieved in November 2026*:
  `America/New_York`, Monday–Friday `04:15:00–13:29:00` ET, end exclusive.
  On September 2–3 under US daylight time this maps to **08:15:00–17:29:00 UTC**,
  with the next session beginning **2026-09-03 08:15:00 UTC**.
- Internal request-to-close is inferred to occur on the next observed
  quote at **2026-09-03 14:00:01.500 UTC**, after which the original
  simulator fills on the next 5-minute quote at **14:05:01.500 UTC**.
  Original exit reason: `ENTRY_VOLATILITY_INVALIDATION`, not confirmed
  executable time-stop. No broker closing order is evidenced.

**Crucial historical caveat:** November's current-contract weekly schedule
does **not** certify that all historical September holidays or session
exceptions were identical. This is a source-backed *current schedule*
comparison, not a proof of 2026-09-02 historical broker execution terms.
Even assuming this normal weekly schedule applied unchanged, the declared
deadline falls **6 minutes 1.5 seconds after the exclusive session end**.
There is no ordinary market-open close at 17:35. The underlying replay
does not create a protective server-side broker order.

## Why 249 of 371 held quote clocks are missing

For the Coffee holding, the inclusive 5-minute sequence
15:35:01.500 Sep 2 through 14:05:01.500 Sep 3 has 271 clocks.
The other eight modeled positions account for the remaining 100 required
clocks (371 total). The original receipt has 21 occupied-margin Coffee
observations and necessarily a 14:05 close mark (22 observed).
The missing 249 reconcile as follows **under November's weekly schedule
applied provisionally to September**, with the original collector's
14:00–20:00 UTC sampling policy:

| Cause | 5-minute clocks | Evidence boundary |
|---|---:|---|
| Market contractually closed: Sep 2 17:30 through Sep 3 08:10 | **177** | Inferable from current weekly schedule; historical exceptions not certified |
| Market nominally open, but outside MSE1's 14:00–20:00 source request window: Sep 3 08:15–13:55 | **69** | Collection design omission, not evidence that the market had no ticks |
| Nominally open and inside request window, but no qualifying paired fresh quote: Sep 2 17:00, 17:10, 17:15 | **3** | Cannot distinguish source gaps, sparse ticks and strict 30s freshness from public receipt alone |
| **Total missing** | **249** | Matches original receipt |
| Observed including closing fill | 22 | 21 held-margin snapshots + closing quote |

The diagnostic script `research/mse1_coffee_postclosure_diagnostic.py`
asserts the public-receipt totals without downloading or decrypting source,
without running MSE1 and without accessing broker credentials. For exact
classification of the three in-window missing observations by source
status or historical exceptions, **the encrypted original tick tape must
be examined in the protected custody environment**, with read-only
redacted diagnostic output, not guessed fills or price interpolation.

## Execution / protection distinctions

A. The internal `Assess` result is only a modeled **request**.
B. The research engine journals `REQUEST_CLOSE` and sends **zero orders**.
C. `CLOSE_FILL` is a subsequent synthetic BID/ASK-clock journal fact;
   **no original broker execution acknowledgement** exists.
D. Broker-side SL/TP/GSL requires separate proof of actual supported
   order type, broker acceptance, order identity and modification status.
   Even a broker-side ordinary stop is not a guaranteed gap fill.
E. The gap to the next available executable BID/ASK and the entry-to-exit
   intrabar path are unobserved in the original constrained sample;
   no historical server stop behavior can be certified.

## Prospective response (not a revision to MSE1)

`NativeProspectiveSessionAdmission` is a pure native C# underwriting
gate opt-in **only for newly specified mechanisms** via
`NativeProductResearchLoop(requireProspectiveExitFeasibility:true)`,
with broker schedule as of the decision, supported holiday calendar,
complete prior monitoring evidence, current common free margin/equity,
marginal adverse loss and same-book floating-drawdown budget. A protective
deadline crossing an official session end is refused **unless explicit
cross-session carry and a separately priced gap-loss reserve are supplied**.
No universal position duration limit is introduced; 30% system drawdown
includes floating loss. This gate does not generate orders, stop fills,
broker acknowledgements, gap prices or new economic evidence. Legacy MSE1
and other closed modes keep their original behavior; future mechanisms
must consciously enable the gate and supply authentic, causal inputs.
Synthetic tests are **structural** safety checks, not live execution proof.

**Further required before a new strategy is financially qualified:**
historically as-of holiday/session evidence, sufficient original BID/ASK
and tick path, empirical gap and slippage stress, quote completeness,
independent chronological NET confirmation against financed benchmarks,
12+ relevant months, HARD21 weekly systemic, continuous 30% drawdown
including floating equity, native Cloud behavior and no LIVE/DEMO orders.
No new authentic historical data or fresh financial evaluation is claimed
by this *technical* PR.

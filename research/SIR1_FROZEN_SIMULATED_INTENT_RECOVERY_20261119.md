# SIR1 — prospective repair of UNTRANSMITTED simulated closing intents (2026-11-19)

OWNER after independent NPI1 audit Issue #393 comment #7005263564. NPI1 #44494972731 and PR #397, MVO1/SPE1 and all closed experiments are immutable. This is a **new technical product-lifecycle validation**, NOT a NPI1 historical re-run, retuning, rescue or validation of CROSS +EUR1.82. New C# code is frozen as design before any run.

## Required invariant

For every position, the original-account broker execution history is unrelated to research-only UNTRANSMITTED model intents, and must never be inferred from them. Add a **new event kind** in existing NativeFundedLedger ONLY for `MODEL_CLOSE_INTENT_EXPIRED`, accepted in MODEL_REPLAY monetary domain for an already-held position with an outstanding MODEL-SOURCED `REQUEST_CLOSE`. It removes **ONLY** the pending close request; it does not remove held exposure, change units, funds, cash, fees, entry basis or margin. Never use `CONFIRMED_CANCEL` to represent a broker-confirmed fact for this model-only event. Old ledger events keep their exact semantics and hash representation; no modifications of NPI1 original execution code.

Create one reusable **Core** recovery state machine invoked from Replay and the existing observation-only Cloud parity adapter, with the same evidence/clock and no external broker calls. The state machine must:
1. Process a wall-clock timestamp even without a quote. An aged model close intent expires explicitly after the **2-minute modeled order response window**; this window is for intended execution validity, NOT a normal holding-time exit.
2. Preserve position/margin on stale/missing quote; record UNKNOWN mark and do not fill or classify an official session close from a source-window end.
3. On the first authentic fresh observed quote after expiry, recompute existing NativeCausalExitResearch.AssessLifecycle using entry-frozen seed, last protected extreme and the actual quote. Request a **new** conditional model close only if the observed thesis still requires it. No future observation can determine an earlier intent, and no quote at request time is a fill.
4. On a subsequent causally observed quote within the validity interval after modeled latency, generate existing quote-cost-bound CLOSE_FILL into the SAME NativeFundedSession/NativeFundedLedger. If this quote does not arrive, expire and repeat on the next observed quote. No broker orders, no broker cancellation status, no Cloud activation.
5. Support duplicate event idempotence, conflicting duplicates rejection, checkpoint restore and reject stale/as-of/future quotes. Protective state must be explicit and serialized or re-supplied causally on restore.
6. Do not place an unconditional global admissions pause merely because some other *model-only* close request exists. Existing one EUR300 native allocator and real fresh-mark/held exposure risk checks remain authoritative.

## Verification scope

Deterministic fixtures: missed quote, model expiry with no quote, source collection window ending, overnight and weekend, restored session and protective state, repeated step, conflicting repeated event, exit signal invalidation vs continued hold, new request/next quote close and distinct instrument admission while an unrelated close request exists. Test that no cash/margin/position freed until **genuine modeled CLOSE_FILL**. Output full synthetic event trace with SHA-256 and receipt, labeled strictly SYNTHETIC. Compare exact same per-event Core behavior vs Cloud adapter in Replay; Cloud adapter is pure observation-only and cannot send orders.

Financial target unchanged: €300 common initial capital, independent positive adverse incremental NET, systemically financed HARD21 (>=21 completed per eligible week), <=30% continuous floating DD and >=12 months truly independent confirmation. No synthetic fixture qualifies economic performance. Preserve NPI1 outcomes and their missing LONG/SHORT comparators as reported audit deficiencies, do not retrofit old result. New economic discovery, when pursued, must freeze distinct hypotheses and use authentic source-bound C# decision+finance against CASH and legal funded matched controls; no result-promotion without original evidence.

NO broker calls, no LIVE/DEMO, no Cloud runtime activation, no new infrastructure or Android duties.

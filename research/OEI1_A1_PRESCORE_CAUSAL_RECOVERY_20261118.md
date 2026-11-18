# OEI1 technical causality correction A1 — before scoring recovery

Recorded 2026-11-18 during original source Actions 44247979857.
Base original merged OEI1 protocol 018af64f3fe2836fa6efe77665a8d3e0655af415,
source code c3bd18651e3a5495a0cf782802e60699083ceb04.
OWNER v2.0 explicitly permits bounded technical verification/re-execution to correct material
source, valuation or causal bugs, without changing closed research outcomes and without
substituting old receipt or claiming independent confirmation.

**Two exact defects identified by source inspection BEFORE receiving any OEI1
original financial outcome:**
1. Candidate risk and funding admit uses a risk number partly derived from
exit-time commissions and realized PnL conversion fee. Such prices/fees are not
known at decision time; a causal admission must use a conservative initial
stop+current spread/slippage+current estimated round-trip fee+conversion allowance
based only on the quote observed by the decision clock.
2. Original outcome sample construction included only candidate clocks with
both central and adverse future paths settled, silently dropping causal offers
whose future outcomes were censored by missing exit path. A live decision cannot
know future path completeness. All causally available offers must remain in the
population; missing later path turns a selected book into UNKNOWN, not CASH.

**Boundaries:** NO parameter retuning, side inversion, new feature, alternative
selection, training split changes, instrument/timeframe/session changes,
instruments replaced, enhanced model weights, new cost assumptions or
relabeling of exposed development dates. Exact same three Bayesian/Markov/tree
models, placebo, controls, barriers and MAX_RISK=90, probability threshold .55,
portfolio 300, 2-slot cap. Only data-leakage repairs and recording truthful
unknowns. Original OEI1 run/ZIP/encrypted source remain immutable and may have
an invalid economic receipt, which must remain separately conserved. A
different corrected result is a **postsource technical recovery**, not blind
confirmation nor a novel scientific test.

**Recovery source:** Only *same* untouched original OEI1 native plaintext
tape, sealed by the 2026-11-18 run-bound RSA/AES-GCM envelope for original run
44247979857, with published original native SHA256 verified. Existing custody
private key may decrypt in existing protected mxm-r3-custody-v1 environment
ephemerally. No Pepperstone request, no token/refresh, no broker order, no
Cloud or new external service. The decrypted tape must never be published; the
corrected public report contains only aggregate results, source hash and
original run identity. If the original run fails before the tape exists, mark
SOURCE_UNAVAILABLE and do not invent a recovery.
No historical tariff, original fills, continuous DD or 12-month independent
confirmation claims. Auditor independently verifies post-recovery math.

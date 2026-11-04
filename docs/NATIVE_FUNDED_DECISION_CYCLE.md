# Native funded decision cycle — development implementation, 2026-11-04

Authority: [OWNER v2.0](OWNER_SPEC.md). Continues the existing native session,
selector, adaptive risk and ledger; no second allocator, accounting book or cBot.

`NativeFundedSession.DecideResearch` obtains cash, liquidation equity, free margin
and sampled peak from its own ledger. Caller-supplied account balances cannot size
entries. Every held position AND pending opening intent must supply aligned joint
EUR scenarios with matching identity, side and remaining physical volume. Scenario
margin cannot be below current observed margin. Close intents retain held risk.
Pending opening margin is reserved before selecting further opportunities. No
unjustified diversification or zero-risk baseline for existing exposures is created.

The existing `OpportunityOrchestrator.Estimate` selects conditional allocations.
They become native `REQUEST_OPEN` intents, with no fill price at decision time.
Subsequent explicit quote/fill facts pass through `NativeFundedLedger`: latency,
current margin, price, spread, requested slippage, fees, FX, financing, partial closes
and sampled floating equity remain its responsibility. `ApplyResearchFacts` adopts
an event batch atomically; an invalid later event cannot leave an earlier cash
mutation. Rejected decisions likewise cannot adopt partially generated intents.

Decision receipts and their input hashes survive session checkpoint version 3;
versions 1 and 2 still restore. A repeated identical decision cannot create new
orders or reservations; a conflicting decision identity is rejected. Checkpoints
are technical development state, not Cloud durability or broker recovery evidence.

A missing historical model mark remains disclosed as `HistoryEvidenceIncomplete`.
It pauses entry while current held marks are absent, but no longer blocks conditional
research forever after current quotes return. Previously observed drawdown and peak
remain retained; a sampled 30% breach continues to restrict new decisions. This
change confers neither complete historical risk knowledge nor actual trading rights.
The observation-only Cloud adapter is unchanged and has no order path.

The CLI `--native-funded-decision-cycle` takes chronological fact/decision frames
and uses this same session throughout, restoring after each frame. It is available
for future prospectively registered research. It does not rerun, replace or reprice
IPF1/RCP1 or any other closed experiment. Existing Python studies remain frozen;
this implementation does NOT establish their full native economic parity.

Focused contracts cover two simultaneous allocations on one EUR200 book, receipt
restart/idempotence/conflict, pending risk, atomic rejected fills, occupied-symbol
exclusion, missing-mark recovery, final settlement and no qualification. All are
synthetic software checks. There is no new market hypothesis scored, independent
confirmation, funded economic performance, HARD21 proof or broker/Cloud acceptance.

Official contracts checked on 2026-11-04:
- https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/
- https://help.ctrader.com/ctrader-algo/references/General/Algo/
- https://help.ctrader.com/ctrader-algo/guides/local-storage/

Cloud uses Linux and compile-time dependencies; its HTTP requests are not sent.
The native cycle introduces no network access or external runtime dependency.
Native nonempty broker recovery, predictive warmup, independent economic discovery
and authorized Cloud/Android runtime acceptance remain outstanding.

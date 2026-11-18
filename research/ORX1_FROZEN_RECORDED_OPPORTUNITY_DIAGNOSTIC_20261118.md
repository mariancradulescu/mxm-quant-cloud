# ORX1 — prespecified recorded-opportunity retrospective diagnostic

Date: 2026-11-18. Starting main: cdf712939a172e565cc1a9bcb5463269924ee8d5.
Authority: docs/OWNER_SPEC.md OWNER v2.0 and 2026-11-18 OWNER methodological mandate.

## Role and nonclaims

Phase-1 **restricted diagnostic**, not the full market-path oracle requested by OWNER.
Read the *unchanged* public CVP1 original ZIP SHA-256
a5125582a1cf4690871ad4d7640090c376ea8e85196228bf235d4a25ee7bc569,
stored at docs/CVP1_ORIGINAL_PUBLIC_44162043538.zip.
No invocation of CVP1 policies, broker, ciphertext, previous jobs, learning,
fit, threshold tuning or trading requests. The three FX instruments, calendar,
existing SIMPLE trades and their fills are already globally exposed development.
Original CVP1 outcome/receipt/verdict remain frozen; this is a new
*secondary measurement* on their published trade rows, not independent market evidence.

The narrow question is: among completed **recorded** SIMPLE entries, how much
positive post-cost value did perfect future knowledge of their already-recorded
outcomes leave available? This is not a bound on all price trajectories, entries,
exits, strategies, asset classes or weeks. It cannot answer whether new
information permits causal forecasting.

## Locked population / honest restriction

Use SIMPLE_adverse (primary, 170 previously settled trades) and SIMPLE_central
(secondary, 171 previously settled trades) as **separate** counterfactual books,
never mix their trades. Read the records in each original book only.
All sourced rows remain counted even if uncertainty disqualifies them from the
restricted known-path candidate set. Reject incomplete round trips, missing
matching entry, duplicate ID, nonpositive ex-ante risk and contradictory
NET=GROSS-cost arithmetic. Do not rewrite original records.

A recorded trade is only eligible for the hindsight subset if complete, its
matching entry has Uncertain=false, NET>0, and initial ex-ante risk is <=EUR90.
This uses one original minimum-volume funded trade; never scale below legal
minimum or increase its volume. EUR90 is *only* a conservative one-position
30%-of-initial-equity initial-stop-risk screening threshold, not a continuous
drawdown certificate. Original SIMPLE peak reported margin <=EUR300; each
recorded individual trade was originally funded, and selecting a disjoint
positive-only subset starting at EUR300 cannot decrease cash at recorded close.
This *conditional fixed-outcome* statement is not a rerun of the native ledger,
does not verify entry-time expenses, intraposition floating DD, or altered
fills under a different book. Flag that explicitly.

## Locked mathematical calculations

1. CASH NET=EUR0; report original SIMPLE adverse/central NET, trades, costs,
   known-mark drawdown, unknown holding marks and uncertain-trade counts.
2. Naive optimistic relaxed envelope = sum of all eligible positive NET values,
   ignoring overlap/concurrency. It is only an upper bound for **this recorded
   eligible candidate set with unchanged outcomes**.
3. More restrictive **one-at-a-time** perfect-hindsight schedule: sort by
   (ClosedAt, OpenedAt, PositionId), then weighted-interval dynamic programming
   with predecessor ClosedAt<=OpenedAt. Choose largest NET; equal-value ties
   prefer skipping. This is exact for the selected immutable interval model;
   selecting it requires future outcomes and is not executable.
4. Also calculate maximal count of completed eligible positives under one
   concurrent slot (earliest-finish greedy), and per-week counts of all
   positive/known-path eligible recorded opportunities and the max-NET
   one-slot schedule. Report how many of each originally recorded ISO
   evaluation week achieve 21, and whether any week has a strict recorded
   candidate-count upper bound below 21. Weekly HARD21 remains a *systemic*
   goal and this recorded subset must not be generalized to the whole market.
5. Cost break-even capture: for the chosen positive hindsight subset, report
   positive gross, recorded spread/slippage/commission/conversion/financing,
   and costs/gross if gross>0, interpreted only as the fraction of this
   hindsight-selected gross needed to cover *its* captured cost structure.
   No inference about predictability of selected trades or their gross.
6. Report per-recorded-policy diagnostics against original CASH and other
   published CVP1 comparators without selecting or promoting favorable
   post-exposure policies. NO_PEER +EUR1.39 advers on four trades is not alpha.

All metrics are explicitly labeled restricted, retrospective, conditional,
nonindependent, fixed-outcome, and neither native validated common-portfolio
counterfactual nor risk-certified. Uncertain fills/holding marks are not
reclassified as known. A result >EUR0 from hindsight is not a trading edge.
Use 3 evaluated CVP1 weeks, not an invented 12 months. No claim that historical
commission/slippage are actual broker fills or that last-known tariffs bind history.

## Program boundary after ORX1

The OWNER-mandated **full Phase 1** still needs prospective explicit collection
of authentic market paths and contract/cost/margin evidence across eligible
instrument classes, a true feasible capital/risk-aware hindsight oracle and
matched simple causal controls. This deliberately restricted public-data
measurement cannot replace it. No Phase 2 predictive model is selected or
promoted from ORX1 outcomes. Future methodology comparison requires a separate
ex-ante frozen protocol and genuinely isolated chronology; exposed dates stay
exposed. No LIVE/DEMO order, Cloud activation, or external services.

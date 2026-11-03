# Superseded risk authority correction — 2026-11-03

The fixed 1%/40%/60% directive recorded below is SUPERSEDED by the latest explicit
OWNER mandate in this continuation. It must not control future admission.
See WIDE_ADAPTIVE_RESEARCH_20261103.md for the controlling adaptive mandate.
The intervening main commit 07497fc was reconciled without rewriting history.
Prior exact model verdicts remain unchanged. Original historical text follows:

# Controlling OWNER risk authority after PR16–17 — 2026-11-03

The explicit OWNER correction in the current thread is controlling: aggregate risk <=1% capital, aggregate margin <=40%, free reserve >=60%. Earlier conversation summaries conflict about whether historical absolute EUR2/80/120 values were OWNER constraints or DIRECTOR parameters. Do not fabricate a clean historical revocation chain from a code comment. This current directive supplies unambiguous authority for all future admission; DIRECTOR may choose stricter operational policies, never relax these percentages unilaterally.

Basis: continuously reconciled current equity, including marked positions and no additional deposits; EUR200 is unique initial capital, not a perpetual fixed equity. At initial EUR200: aggregate risk EUR2, aggregate margin EUR80, free reserve EUR120. Existing positions, pending orders and bounded ambiguous intents all consume the aggregate budgets. No correlation discount. Unknown unbounded exposure blocks new risk while automatic monitoring/reconciliation continue. Broker FreeMargin already excludes its existing margin; do not subtract the same amount twice. Reserve-after-admission is the smaller of equity minus aggregate margin and actual broker free margin minus proposed additional margin.

| Layer | Authority | Application |
|---|---|---|
| 1% aggregate loss,40% aggregate margin,60% free reserve | Latest explicit OWNER directive | Mandatory, scales with current reconciled equity |
| DD <=30%, unique EUR200, HARD21 system, authentic >=12m and independent confirmation | Continuing OWNER mandate | Mandatory final acceptance |
| Stop model, gap/slippage/spread/FX stresses, forecast threshold, model parameters | DIRECTOR research choice | Model-specific and frozen before evaluation; calibrated from authentic training evidence where available |
| PR16 2%-per-entry sizing | Historical evaluated configuration | Not current authorized admission; preserve exact old outcomes, never reinterpret as compliant with current limits |

OwnerRiskLimits enforces current aggregate percentages. PreventiveExecutionRisk uses remaining aggregate 1% capacity and 40/60 margin capacity BEFORE minimum/step sizing, alongside DD/stop/execution scenarios. PortfolioRiskBudget and SelectiveRecovery risk-review capacity also consume the same OWNER budgets. Recovery remains live even when no new risk is admissible; unknown submissions are never retransmitted.

Closed CausalFlowResearch binds explicitly to internal HistoricalPr16Risk, an unchanged copy of the original PR16 arithmetic. This isolates original numerical provenance; no authentic old model run, custody replay, source recollection or re-evaluation is requested. Original results, frozen protocols and receipts remain untouched. Synthetic regression checks are not new economic performance. New research must call current PreventiveExecutionRisk and report current authority, separate forecast absence, cost rejection, risk rejection and missing data. A failed exact model does not close its entire statistical/ML family.

This correction contains no LIVE/DEMO order code or Cloud activation. The single native cBot remains observation-only pending full operational/economic acceptance and explicit OWNER trading authorization.

# OWNER 2026-11-08 — Prospective two-endpoint statistical gate

This is a **prospective-only correction**. The original `research/sfx1_economics.py`, frozen SFX1 protocol, `docs/SFX1_AUTHENTIC_RESULT_20261108.json`, underlying signed receipt and original decision remain byte-identical. The field `adverseWeeklyHacBonferroniLower` in the frozen SFX1 scorer was **incremental over the matched momentum benchmark**, not the absolute adverse NET. SFX1 remains rejected (JPY negative selection; NZD underpowered and negative on other exposed splits). The 13 audit weeks remain **globally exposed**; none is an independent confirmation.

Future programmes MUST call `research/prospective_joint_stat_gate.assess_prospective_weekly` with **each predeclared family** and **matched same-entry benchmark**. Two distinct one-sided tests:
1. Conditional adverse NET *absolute* on the candidate vs the cash/no-position baseline;
2. Conditional adverse NET incremental vs the same opportunity's cost-consistent benchmark.

Use all eligible calendar weeks including zero-activity weeks, without counting those as completed trades; no missing cost/FX/funding may be treated as 0. The two separate weekly lower bounds are computed with HAC lag 3, approximate normal confidence with Bonferroni familywise `alpha/(2 * number_of_prespecified_families)`, and must **both** exceed zero, in addition to preregistered opportunity-count and active-week support minimums. Report both values separately with their actual metric names. Conservative multiplicity counts **all** planned mechanisms, not just successful ones.

This is an exploratory statistical screen, not a proof of Gaussian or stationary weekly returns. A positive result on already observed history cannot be called independent; a prospective confirmation split not yet exposed is required separately before selection. Actual broker funded EUR NET, shared portfolio risk, HARD21 and DD30 require the native broker ledger, not a Python bps approximation. All LIVE/DEMO orders and Cloud activation remain prohibited.

# DVI1-A1 — original new chronological decision-value result, exact closure (2026-11-17)

**Verdict:** `DVI1_A1_CLOSED_EXACT_NO_INCREMENTAL_ACTION_VALUE_VS_CASH_NO_PROMOTION`.

This is a **new** exact, preregistered policy/value-learning study. It is NOT CXL1 scoring or a relaunch/retuning/inversion of SDP2 or any older strategy. The original CXL1 **source only** was independently authenticated, decoded and reused with untouched old artifacts; all CXL1 outcome results and policy rules remain frozen. This is exposed development evidence, not independent confirmation, trading authorization, or proof that all accessible information is worthless.

## 1. Protocol-first, implementation and original run

- Authority: `docs/OWNER_SPEC.md`, OWNER v2.0 and 2026-11-17 continuation of DVI1.
- [PR #355](https://github.com/mariancradulescu/mxm-quant-cloud/pull/355) source/decision methodology accepted, merged main `5dc92e656c865681e7b05c80b5920920183db54f`.
- **Protocol FIRST:** `research/DVI1_A1_FROZEN_ACTION_VALUE_PROTOCOL_20261117.md`, separate commit `ffd7284fcdd1a11310c7ddf25242e1468ea4a9f6`, SHA256 **`14c39813b0703aad4736fdd02df86c7df34eb9a7835d6c585e15e98c301c1edd`**, ahead of implementation and scoring.
- [PR #356](https://github.com/mariancradulescu/mxm-quant-cloud/pull/356) merged as `eac1c2ee2b5946802b767fc0c82bf725166c241f`, implementation `research/dvi1_action_value.py`, SHA256 **`f8ce6ae225a593f93c412fe1cba6e9bb083978c9a4fc0563a844f0823813a5ea`**. Technical no-favorable-skips guard was committed pre-original (`7576014f6d7495509ddf5f5408d3248e7fc61b7e`) without changing the policy or hyperparameters. Full verify CI (both checks) and DVI1 targeted test/build/OWNER boundary PASS on this final implementation commit.
- Exact first-only authorized source-readback intent main commit `abc5f2058e7ceeaae7ab8322a14b07d743ef4dd9` changed only `ops/dvi1-a1-original-once.txt`.
- **NEW original** [Actions #44052605207](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44052605207), attempt 1: validate-protocol-and-native SUCCESS, protected-original-result SUCCESS; **zero new broker source requests, zero LIVE/DEMO orders or Cloud activation**.
- **Original public ZIP artifact [#14314426667](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44052605207/artifacts/14314426667)**, original ZIP SHA256 **`314463937f348464612d77eafd3d374eece1806f9021ed9d34b25bdf3bc40332`**, embedded `dvi1-a1-original-new-action-value-native-eur300.public.json` SHA256 **`47b1b8c41af85593655b3226047cd0dfd9bfe5c11046b50deccb0ee7f7e8d436`**. These hashes were reconciled against original uploader/job logs and downloaded byte-for-byte original ZIP/JSON; this documented reconciliation is Director-side and awaits an independent Auditor review.

## 2. Original source, exact population and identifiability

- CXL1 ORIGINAL previously sealed 275-clock source [Actions #43947388854](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43947388854) ciphertext SHA256 `24ac9a7b32e98b42cee6430f9bc786141c6adf4d13d501ffad8125bd5a25a508`, plaintext SHA256 `c368e320d84e69aae09f26f1284658a7dd179c633be960508b76c5d086948333`.
- CXL1 ORIGINAL earlier sealed 50-clock pilot [Actions #43945139889](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43945139889) ciphertext SHA256 `6e662beec28f0fc0aa987f394a3116d6db004059622cc2b374128af84b45277e`, plaintext SHA256 `4989fc8d82f315c99f44ed6f9ef5123e427cc038e31aa188706a38dd980b85c7`.
- Rebuilt ORIGINAL raw Pepperstone EUR account/custody: **3,264 original read-only protobuf request/response pairs**, 325/325 fully complete BTCUSD and 325/325 ETHUSD causal M5 predecision paths, 650/650 authentic original paired ETHUSD BID/ASK entry+exit and 650/650 contemporaneous EURUSD paired conversion routes. Zero unknown/removed decisions.
- Entire 325 original clocks retained: 13 consecutive globally exposed weeks 2026-08-17–2026-11-13, weekdays 08:30, 10:30, 12:30, 14:30, 16:30 UTC. First five weeks = **125 training clocks**; next eight weeks = **200 evaluation clocks**. No favorable hour, asset, side or evaluation-week removal. Two different action labels (LONG and SHORT) at every source-priced decision are counterfactual quote-side **conditional current-tariff model** outcomes, not fully executed trades.
- **KEEP/EXIT financial state is unidentifiable from this chosen original source:** there are only entry and terminal 30-minute paired marks, not intermediate position marks/feasible genuine alternative-exit quotes. No held exposure or adaptive-exit P&L was fabricated.
- In particular neither historical broker commission continuity, actual fills, full margin/equity history, gaps/intratick continuous equity nor genuinely unexposed future confirmation can be certified.

## 3. Predictive score vs actual action value

Three frozen as-of online mean-adverse-EUR learners use matured counterfactual quote-side action outcomes only (fixed one-hour embargo, zero prior with 32 virtual observations, >=20 samples, >=4 distinct completed calendar weeks, one standard error of week-block means before admitting a positive action):

- **FULL:** only two past-return signs ETHUSD + BTCUSD (4 sign states).
- **OWN:** ETHUSD sign only.
- **POOLED:** no directional state.
- **CASH:** permanent cash comparison, not a predictor.

Each non-CASH learner had **398 side-specific adverse-NET label/prediction comparisons** on the 200 evaluation clocks (199 with nonzero valid signs for both sides). Per label MSE in **EUR squared**, lower better:

| Adverse action-label predictor | Mean squared error EUR² |
|---|---:|
| Known-cost zero-price-movement reference | **0.009755217157397824** |
| POOLED | 0.009809915226913657 |
| OWN | 0.010034401358729454 |
| FULL | 0.010060601908960805 |

FULL is worse than cost-only, POOLED and OWN. It did NOT demonstrate a new usable market-price innovation beyond already observable friction. This MSE comparison is descriptive on a globally exposed and temporally dependent sample, not independent statistical evidence. Original source carried a legitimate future outcome for each clock; no positive winner subset was selected after results.

**Actual decision output** on the SAME 200 evaluation clocks:

| Online policy | Proposed LONG+SHORT | CASH outcomes | Native funded round trips | Conditional central NET EUR | Conditional adverse NET EUR |
|---|---:|---:|---:|---:|---:|
| FULL | 0 | 200 | 0 | 0.000000 | 0.000000 |
| OWN | 0 | 200 | 0 | 0.000000 | 0.000000 |
| POOLED | 0 | 200 | 0 | 0.000000 | 0.000000 |
| CASH | 0 | 200 | 0 | 0.000000 | 0.000000 |

For FULL, 182/200 clocks preferred CASH via negative/insufficient incremental expected value, 17 had insufficient matured matching weekly state support and one lacked a nonzero sign. OWN and POOLED each chose CASH 199 times based on value and once on zero sign. There were ZERO native OPEN/CLOSE facts; native financial replay **was not invoked with non-empty events**. The source and conditional counterfactual action labels were economically evaluated, but a funded portfolio's active execution/risk behavior was NOT tested; all named native cash identities follow from zero selected positions.

FULL **incremental modeled NET** relative to OWN, POOLED and CASH = **0.000000 EUR** in both scenarios. The maintained initial EUR300 is CASH parity, **not investment performance, positive alpha or certified loss protection**. Eight evaluation weeks had zero completed financed roundtrips. HARD21 not achieved; no active floating DD or gap-risk certificate. No independent chronological confirmation.

## 4. Exact closure, scientific interpretation and continuation boundary

Verdict: **`DVI1_A1_CLOSED_EXACT_NO_INCREMENTAL_ACTION_VALUE_VS_CASH_NO_PROMOTION`**. The exact two-sign, 32-pseudo-observation, 20-observation/4-week/one-SE rule at fixed 30-minute ETH minimum volume failed to find a positive causal expected-NET decision; no positive incremental economic value from BTC sign is demonstrated in this exact source. The result **does not demonstrate impossibility of predictive information globally**.

Do NOT rerun, retune, invert, relax the confidence/support gate, choose an advantageous time or symbol or adopt retrospectively the outcomes. Do not count isolated counterfactual labels as financed trades; do not report 300 EUR CASH as profit, and do not certify 30% DD through absence of exposure.

The wider DVI1 programme may continue with a truly distinct prospectively justified source/mechanism, but not by restoring a rejected DVI1-A1 exact configuration. No new general infrastructure and no new trading authorization were created.

**DIRECTOR executes. Independent AUDITOR verifies. OWNER decides.**

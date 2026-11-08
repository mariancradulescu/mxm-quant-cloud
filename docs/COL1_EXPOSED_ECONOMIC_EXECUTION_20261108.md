# COL1 — executed, exploratory, exact negative intraday index-calendar mechanism (2026-11-08)

## Source and fixed rule

Rule source committed before aggregate evaluation: `research/col1_exposed_session_premium.py`, branch commit `61283a9579eb719901d93867df8261f2e6fd8767`.

The data are **already publicly released source-authenticated original-account Pepperstone AIP1** market-price labels, not new collected OHLCV: `docs/AIP1_AUTHENTIC_RESULT.json`, Git blob `6868030638f0ec48b7592a0a069cad768605a1ec`, original source run **41735441128**. Original raw readback and account binding were previously verified. The observation rows are scheduled by the original AIP1 feature-availability calendar; they do NOT necessarily include every broker-open day or all listed indexes. Neither the frozen AIP1 prediction nor its `Primary` status is used to choose COL1 trade direction or an instrument.

Mechanism: every available US500, NAS100, UK100, GER40, JPN225, AUS200 event in **only the prior publicly exposed 2026-05-04 to 2026-08-03 selection cohort** is a 120-minute **long** price-proxy from cash-open +30 min to +150 min. No retrospective asset ranking, return-based selection, fitting, parameters, threshold search, altered session, new source, retained audit readout or future lookahead. All 13 calendar weeks are retained. The 359 later AIP1 outcome rows are not read for COL1 economics.

Prospective economic plausibility check before scoring: the original observed ~2h index-price movement scale can exceed low-single-digit *modeled* current source-date round-trip cost on some sessions, permitting a falsifiable fixed-clock 2h hypothesis, but not guaranteeing NET. Source `OutcomeBps` is **unsigned-direction raw gross log-return in bps**, verified against `src/Mxm.Core/AuctionInventoryResearch.cs`; all-long COL1 gross uses this directly, not `Side*OutcomeBps`. Cost `CostBps` is original AIP1 **modelled, current-term** round-trip friction (no historical broker-fill certificate). Central proxy subtracts 1x; adverse proxy subtracts 2x as conservative scenario; historic financing and conversion remain unsupported. Matched comparator is the **previously frozen published AIP1 forecast-side** applied to the **same rows**, only a descriptive benchmark (not a strategy replay, no model rerun, no recovery). Costs cancel in the same-cost incremental comparison.

## Actual executed results

Receipt: `docs/COL1_EXPOSED_AUTHENTIC_RESULT_20261108.json`, independently recomputed against public JSON in ordinary `research/verify_owner_policy.py` (no workflow modification).

- Source matched: **287/287 complete** already-published historical selection-event labels; **0 missing**; **13/13 calendar weeks** have a published event; **359 later observations excluded**.
- Equal-event per-week means then equal-calendar-week aggregate: **BRUT -1.178889 bps**, **conditional NET central -4.869963 bps**, **conditional NET adverse -8.561038 bps**.
- Against matched previous AIP1 predicted-side directional benchmark, **adverse NET incremental -5.279073 bps**; this comparator is for research only, not a qualified portfolio or newly funded baseline.
- With HAC3 lag3 and Bonferroni **two one-sided endpoints**, descriptive lower bounds: **-13.322381 bps vs cash**, **-14.785114 bps incremental vs frozen side comparator**. Both are less than zero and **fail** to show a strictly positive lower bound. At N=13 weeks, normal critical values are approximate and the global data are previously exposed; never label a new independent statistical validation.
- Authentic calendar-event slots/week: **20, 20, 29, 17, 15, 22, 25, 19, 20, 20, 20, 30, 30**. Only **5/13** weeks have at least 21 even hypothetical once-per-event signal slots; thus COL1 alone cannot make systemic HARD21 in 8 weeks, *before* financed entry, overlap or missing capacity. These **287 are event-level raw signal slots**, not admitted financed roundtrips.
- No instrument-by-instrument winner identified or optimized. No new C# predictor parity claimed. No native 300EUR funded replay or broker EUR NET, equity-sampled DD30 certificate, fills, H1/M15 new bars, independent confirmation or permitted live order. No Cloud activation.

**Exact status:** `CLOSED_EXACT_COL1_NO_NET_EDGE_EXPLORATORY`. No retune, inversion, search by sector, winner filtering or reuse of later rows to salvage it. A negative exact mechanism does not reject equity CFD as a class.

## B–E finitely bounded next candidate programme — not falsely executed

A maximum of two distinct further hypotheses, only if pre-existing genuine OHLCV and quotes are legitimately accessible for new fixed protocol registration, are defensible to evaluate as **exposed exploratory** work:

1. **COL2: causally lagged oil–USDCAD shock transmission**, M5 USDCAD matched to existing authenticated crude H1, adaptive lag set *a priori* to 1–3 hours, entry after both completed observations, forecast 2–4h. Requires overlapping synchronized OHLCV, directional cost/FX and funding. Not OCE1 oil/CAD mechanism rerun: a new explicitly lagged cross-source predictor with no reuse of its discarded signals. If original already-sealed source cannot be legally read back, **do not score**.
2. **COL3: relative index dispersion normalization**, six existing M5 CFD indexes, cross-sectional causal dispersion at completed H1/H4 anchors with 2–6h holding; must use shared-book, paired directional quotes, minimum lot and 300EUR margin constraints. Not XUA1 Asian synchronized risk or AIP1 open gap inventory refit. Without legitimate unsealed original price histories, **do not score**.

**These two are concepts, not executed experiments, decisions to trade, or approvals for a replacement broker workflow**. Avoid selecting among them by results already seen. The original MCS1 remains exactly preregistered and NOT EXECUTED; its blocked protected workflow must never be published via another route. No broker request, credential access, workflow or alternate service was attempted for COL1.

After exact negative COL1, decisive progress beyond exposed-source research requires a permitted independent prospective source and, separately, complete execution-cost/margin/portfolio continuity evidence. **The programme may close with zero qualified strategies; do not manufacture a candidate.**

# SFX1 — Frozen prospective native M15/H4 economic programme (2026-11-08)

Authority: `docs/OWNER_SPEC.md` v2.0, initial EUR300, systemic HARD21,
maximum floating-equity DD30%. **Distinct new programme, not a retune of
XUA1, CPF1, MFA1, MBF1 or another frozen study.**

Research entry is `research/sfx1_protocol.json` (locked before economic
outcomes). Targets: EURJPY, AUDJPY, NZDJPY, NZDUSD. EURUSD is a causal FX
conversion route only. Two hypotheses only: cross-JPY dispersion
recompression at the 08:15 UTC M15 close conditioned on two other completed
04–08 UTC H4 trends (45-minute hold); NZDUSD 07:00 UTC M15-volume reversal
against the previously completed 00–04 UTC H4 move (60-minute hold).
Both enter the NEXT completed M15 bar, benchmark same-target fixed
prior-H4 momentum on the **same selected opportunities**, with one shared
clock/cost basis. Only closed, gapless M15 history may be used.

Original-source collection is one locked 486-request account-bound read-only
cTrader Open API run: 52 weeks of M15 for the four new candidates plus
EURUSD causal quote conversion; five unscored chronological newer days;
two preselected quote clocks per week for the first 13 development weeks.
All original protobuf stays encrypted, paired request/response and original
EUR Pepperstone account binding independently verified on custody before
the actual market source ever reaches Python and C# feature-parity checks.
Missing BID/ASK never blocks **gross** OHLCV predictive analysis; unknown
effective execution cost bars **funded NET promotion**. No threshold
retuning, date replacement or inverse winner recovery.

For each candidate only if sufficient genuinely paired current/history
quote evidence: central/adverse *conditional modeled* bps = development
spread median/p90 (once) + correct min-volume `3 USD/lot per side`
authenticated as-of original CMA1/updated contract, converted with completed
EURUSD/EURJPY M15 rates + separate 0.5/1x-spread hypothetical slippage
+ 0.25/0.75bps explicit FX-route uncertainty assumption. Intraday horizons
do not cross original 22UTC rollover; zero **conditional** funding is not a
claim of all-horizon or historical swap-free trading. No close proxy is a
BID/ASK fill. Historical fee continuity and actual execution remain false.

Both frozen hypothesis families are tested with 26 development / 13
selection / 13 previously exposed audit weeks, calendar-week HAC(3) and
Bonferroni two-test qualification, identical same-clock momentum and
cash-flat baselines. Even a positive result is not an independent
confirmation: the prior 52 weeks are globally exposed. A separate
post-registration 12-month confirmation or appropriate genuinely future
evidence must be obtained before qualification. Only candidates with
economically positive matched adverse evidence, realistic quote/fill
conditions, minimum volume and concurrent EUR300 capital can progress
to the EXISTING `OpportunityOrchestrator` / `NativeFundedLedger`.
Funded round-trip count and worst floating DD are assessed at SYSTEM
level; never fabricate them from gross predictive signal counts.

No LIVE or DEMO orders, token refresh, Cloud activation or permanent
external runtime. Cloud-ready C# features are implemented once in
`SfxNativeSessionFeatures` and compiled in Mxm.Core; Python and GitHub
are only research-time proving tools.

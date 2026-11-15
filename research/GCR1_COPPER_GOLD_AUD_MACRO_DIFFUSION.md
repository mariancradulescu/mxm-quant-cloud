# GCR1 — Copper/gold growth-versus-safety repricing → subsequent AUDUSD (EX-ANTE PROTOCOL ONLY)

Authority: `docs/OWNER_SPEC.md`, OWNER v2.0 and 2026-11-15 post-TFX1 decision.
Status: **economic hypothesis preregistration, BEFORE GCR1 code, new source or outcome scoring**.
Nothing in this file is a profitable result, an execution authorization, or a claim of independent validation.
Closed exact TFX1, QPI1, SQIC1, RRP1, IPC2, WIR1, CDE1, FX dispersion and metals rules remain intact.

## 1. Competing mechanism decision BEFORE scoring

| Direction | Genuine information premise | Main economic obstacle | Decision |
| --- | --- | --- | --- |
| Repeat USDJPY corporate-fixing, London-fixing or quote-pressure rules | Institutional clocks / dealer quote revisions | Existing exact causal configurations already rejected or price evidence inadequate; replacing the threshold or clock is not new information | Do not recycle |
| Spot/-F index or dollar-index pairs | Maturity carry / basis repricing | SFV1 shows unproved actual contract point-value/roll and matching hedge units; equal-minimum paired margin is not a delta hedge | Not admissible as a funded alpha model on current evidence |
| **Copper versus gold macro-demand divergence observed BEFORE AUDUSD exposure** | Industrial-growth/risk appetite versus store-of-value/safety demand; AUD may reprice with lag | Macro correlation is **not** intraday causal predictability; 2026 gold demand may structurally decouple; commodity-specific news, CFD quote asynchrony and FX costs may erase all NET | **Select one falsifiable new information channel for exposed development only** |

Economic context (not price predictability proof): Parnes, *North American Journal of Economics and Finance*, 2024, DOI 10.1016/j.najef.2023.102016 documents an imperfect copper/gold information link to US Treasury yields over multi-day horizons, **NOT** a verified AUDUSD intraday lead. State Street's 2026 commentary explicitly cautions that gold/copper has recently decoupled from the usual slow-growth interpretation: https://www.ssga.com/au/en_gb/intermediary/insights/what-is-the-rising-gold-copper-price-ratio-signaling-for-investors.
The 4-hour target horizon below is a vulnerable conjecture, not derived from either source.

This test differs from closed IPC2 sparse-update **Copper** reversal, CDE1 Copper session handoff, RRP1 **XAUUSD** defensive rotation versus equity, and closed H4 five-FX own-price relative dispersion: two untraded metals serve as a jointly observed **external macro-information input**, and one low-margin currency is the only proposed trade. No old decision signal is rerun, retuned or reversed. Similarity is disclosed as a multiplicity/exposure limitation, not denied.

## 2. Fixed chronology, universe, observable decisions

Original Pepperstone EUR account, authenticated read-only Spotware Open API and existing private custody only. Fixed instruments: `Copper` and `XAUUSD` (context, never traded by GCR1), `AUDUSD` (sole trade target), `EURUSD` (USD→EUR valuation if required). No substitution, no posterior favored symbol.

Study 52 full Monday–Friday weeks from 2025-11-03 through 2026-10-30, inclusive: 260 weekdays, with three predeclared decisions each day, exactly **780 scheduled slots**. All are globally **EXPOSED DEVELOPMENT**, not an untouched holdout. Decision clocks 08:00, 12:00, 16:00 UTC +1.500 seconds; no time-of-day search. Do not retrospectively remove holidays or stale quote days. These windows cover European and US macro-market overlap, but no claim is made that a specific report occurred.

At each t use the 49 consecutive fully completed, aligned M5 *closing* observations ending at the just-completed t boundary for Copper and XAUUSD (48 exact five-minute returns over 4 hours). Historical bar close must be timestamped and available no later than the decision. Reject missing/zero/nonpositive/cross-session bars as **DECISION_UNKNOWN**, never zero return. No forward fill or best available later lookahead.

Define `c = ln(Copper_close(t)/Copper_close(t-4h))`;
`g = ln(XAUUSD_close(t)/XAUUSD_close(t-4h))`.
The change in log(Copper/Gold) is `c-g`; the absolute contractual metal price units cancel for *returns*, not for money or delta hedges.

- If `c>0` and `g<0`: immutable `BUY_AUDUSD_GROWTH` intent.
- If `c<0` and `g>0`: immutable `SELL_AUDUSD_SAFETY` intent.
- Otherwise, including zero: immutable `ABSTAIN_MACRO_AMBIGUOUS`.
- If earlier required bars are absent: `DECISION_UNKNOWN`. Never reclassify an established intent using post-decision quote, price, fee or label completeness.

The opposite-metal-price condition isolates divergent growth/safety information from a simple contemporaneous broad USD price move. It is not observed investor flow, actual traded commodity volume, a volatility index, or a guaranteed exogenous shock. No magnitude cutoff, indicator optimization, model training, directional switch or winner selection.

## 3. Fixed entry, exit, economic abstention

If a causal intent exists, sample a paired original **AUDUSD** BID/ASK at t+5 minutes (one price-side per order direction) with each original side as-of age <=20 seconds, valid and non-crossed. This is an attempted simulated entry, never an order. Exit at t+4 hours+5 minutes at genuine reverse executable price side. 4 hours is an explicit mechanism hypothesis about slower macro information diffusion; do NOT scan other holding times after results. A later invalidation is not evaluated; no intrabar protective-stop execution is invented. Native protective risk admission, collision with existing positions and eventual sizing are **separate common-ledger gates**, not excuses to erase original intents.

Current original-account enabled contract, legal min/step volume, side permission, dynamic margin at modeled allocation, commission/minimum, conversion fee, financing/swap timing and original as-of EURUSD conversion must all be authenticated. Historical tariff continuity and broker fills are not certified by current terms. Exit must be within authenticated session and must not cross a fee/swap time without modeling that actual scheduled fee. If quotes, fees, conversion or material holding path are missing, record `FINANCIAL_UNKNOWN` or `RISK_PATH_UNKNOWN`, **not** ABSTAIN, zero P&L, or dropped intent. The mechanical source signal may precede financial eligibility; do not condition signal existence on future observations.

Use native minimum AUDUSD unit only if truly funded under the same single €300 prospective shared book, with protective global 30% peak-to-floating-equity risk objective. Exact source-side BID/ASK crossing, nonzero original broker commission/minima and P&L FX conversion are explicit. Supplement with 0.5 bps central / 2 bps adverse **roundtrip extra hypothetical slippage**, labeled modeled not tariff. If minimum margin/fees cannot be reliably determined, fail closed and report. Count only fully completed funded round trips as portfolio activity, never intents.

## 4. Outcome-blind comparators and separation of evidence

On the **same immutable GCR1 intent clocks** and exactly matched finance-complete paths, compute:
(1) primary copper/gold implied AUD side;
(2) sign of AUDUSD's own preceding four-hour price change (contemporaneous own-momentum);
(3) matched long AUDUSD;
(4) matched short AUDUSD;
(5) cash 0.
All non-cash comparators pay the same actual quote-side, original current contractual costs, EUR conversion and conservative modeled slippage; no unfair mid fill or extra wallet. Report matched per-event EUR NET central/adverse, net differences and absolute cash benchmark.

For diagnostic *information specificity*, also report full 780-clock census of metal-opposite, metal-same-direction, zero and unknown signal states without choosing a more favorable state ex post. Opposite-sign metal observations mechanically make a copper-only sign and inverse gold-only sign identical: **do not present either as an independent incremental comparator** on these chosen events. A positive result cannot by itself identify the copper/gold ratio as the cause.

Chronological first 26 weeks and final 26 weeks are **two exposed subperiods**. Report each policy's sum and average EUR NET, week-equal-weight measures, quote/feature missingness, weekends/swap treatment, source timestamp gaps, contract currency, observed cost, risk samples, events and raw natural weekly count. No sample-dependent changing windows, side, assets, data-cleaning thresholds, slippage, or thresholds. Do not label either half independent validation.

Reject this **exact rule** if original finance coverage is sufficient and either half has nonpositive adverse NET, fails to improve on the matched cash benchmark or has no incremental adverse advantage versus own momentum and constant directional controls. If coverage is insufficient or materially biased, classify **INCONCLUSIVE** without selectively changing the calendar; do not call it a win. No numerical sample gate selected after prices. A weak, occasional positive bps value cannot be promoted.

## 5. Data custody, reuse, native boundary and portfolio priority

Reuse existing complete, integrity-verifiable original archives without repeating collection, notably overlapping IPC2 Copper/AUDUSD/EURUSD and independent XAUUSD archives **only where the exact required clocks, original BID/ASK, contracts and provenance really match**. It is not claimed that archival overlaps are complete or sufficient. Collect the missing original Copper/XAUUSD/AUDUSD/EURUSD periods freely via authorized protected read-only methods; register exact additional requests and all missingness BEFORE labeling; no external services or source/account substitution. Seal original raw protobuf and decoded evidence before any GCR1 outcome scoring. Never expose credentials or proprietary raw price tape.

Only if this exact channel has credible positive adverse absolute and incremental NET should the existing common C# `OpportunityOrchestrator`, `NativeFundedLedger` and `NativeFundedSession` replay a portfolio *counterfactual ablation* versus cash and other independently supported mechanisms with synchronized quotes and one continuous EUR300 book. No new general infrastructure, parallel broker, second capital account, implied diversification credit or standalone HARD21 test. Three scheduled GCR1 attempts a day are NOT three transactions and are not a weekly activity mandate. The system-wide HARD21, 30% floating DD, at least 12 months authentic evaluation, uncontaminated later confirmation and Cloud/Android native parity remain unproven.

Neither this proposal nor compilation/PR CI authorizes LIVE/DEMO orders, Cloud trading activation or OAuth changes. Protected original-account workflow requires its existing OWNER authorization and security gates; **never weaken owner-only or no-order guards to make a runner execute**.

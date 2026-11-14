# CSI1 — company-specific overnight repricing diffusion, not generic ETF confirmation

OWNER `docs/OWNER_SPEC.md` OWNER v2.0 and 2026-11-14 post-CAC1 decision.
**EX-ANTE FREEZE BEFORE ECONOMIC CODE OR PRIVATE PRICE SCORING**.
This research is DEVELOPMENT on globally exposed 2025–2026 calendar; even
unused historical marks are NOT independent confirmation.

## Economic comparison before any source request

A. CAC1 ETF/index aligned M5 or a new opening threshold: rejected,
   near-permanent signal, no company-specific information.
B. Existing 17 US-24 stocks' prior same-clock recurrence and overnight
   opening-disagreement reversal: already exact-rejected
   `research/EQUITY_CLOCK_PAYOFF.md` and
   `research/EQUITY_OPENING_DISLOCATION.md`; do not retune, re-run
   or invert either policy. Old authenticated 949,860 M5 bar archive
   is available *as prior development context* but belongs to
   different `.US-24` CFD contracts, not a substitute for `.US` quotes.
C. Cross-market crypto-to-financial-equity shock: possible different
   mechanism but a crypto move is not identical to exchange revenue;
   unspecified stock crypto beta and min fees make directional
   monetization ambiguous. Defer, do not pretend evidence.
D. **SELECT CSI1 firm-relative overnight price discovery**, exact target
   `AMD.US`, two independently named price controls `INTC.US`
   (semiconductor peer) and `NAS100` (broad technology basket),
   `EURUSD` strictly for signed FX. AMD.US was authenticated in CMA2
   current original account, with ~EUR7.99 minimum margin and a
   *single-clock* ~15.01 bps spread. Intel exact `.US` presence,
   ability to reproduce same company without corporate-action
   adjustments, and 2025–2026 coverage are UNKNOWN. Do not substitute
   `.US-24`, NVDA, another broker or quote venue if Intel absent.

A genuine firm-specific after-hours announcement/earnings/guidance may
initially affect AMD differently from semiconductor and index exposure.
Institutions may absorb this into morning cash prices over several
minutes; early contemporaneous peer-relative persistence may
distinguish information from transient auction noise. **NO actual
as-published earnings, corporate-news, analyst forecasts, trading
volume or order imbalance are observed.** The model sees a *proxy*
from broker's completed price bars; a price divergence alone is not
proof of corporate information. Competing explanations: AMD repriced
fully before entry; peer/index returns different because of their
own news; broker CFD adjustments/splits, delayed quote, volatility
clustering and execution friction. These explanations can defeat CSI1.

## Frozen original-source calendar, bars and causal event

56 consecutive Monday weeks 2025-10-06..2026-11-01, 280 predeclared
Mon–Fri scheduled days including holidays (missing remains UNKNOWN).
First 4 weeks used exclusively for causally matured, same-weekday
surprise reference; 52 weeks 2025-11-03..2026-10-30 evaluation.
All dates are globally exposed development, NOT a new holdout.
`America/New_York` timezone with DST. At every scheduled day
capture genuine ORIGINAL completed M5 source for AMD, INTC, NAS100
at 15:50..16:05 New York (the day before for overnight anchor) and
09:25..11:10 New York. The 15:55 previous *scheduled weekday*
close is taken only if an exact genuine completed bar exists;
Monday uses previous Friday, no searching backwards on holidays.
Use completed 09:30–09:35 `open` and `close` (not bar midpoint)
with a correct 09:35 decision clock. Never use post-09:35 candles
to decide source quote collection or side.

On each day compute three overnight signed log returns from prior-day
15:55 completed M5 close to today's 09:35 completed M5 close:
`rAMD,rINTC,rNAS`. Define peer and index residuals
`dP=rAMD-rINTC`, `dN=rAMD-rNAS`. Define the corresponding
09:30–09:35 candle-body relative returns `bP,bN`.
Require all four signs dP,dN,bP,bN to be equal, nonzero:
firm-specific gap AND first cash bar both supported by TWO
different controls, not merely common market momentum.

Economic novelty/surprise, not arbitrary bps optimization:
`min(abs(dP),abs(dN))` strictly exceeds the corresponding
`min(abs(dP),abs(dN))` for each of the **previous four same
weekdays**, computed only from fully observed historically matured
previous dates. If any of the four references is unavailable, UNKNOWN,
no replacement/trailing available-date lookback or implicit zero.
This identifies relative novelty in an ex-ante 4-week pattern, not an
assertion of earnings or a guarantee of profitability.

**PRIMARY prediction** = same residual sign (firm-specific continued
price discovery); entry of AMD *only* at original as-of 09:40 ASK for
long / BID for short. At 10:15 NY using strictly closed M5 from
09:35..10:15, compare AMD cumulative movement vs both INTC and NAS100:
if the AMD-relative change against either one is strictly opposite
to original forecast side, EXIT AMD at 10:20 sampled original quote;
else exit at 11:00. This is sampled invalidation, not an intrabar stop,
atomic pair or exchange auction fill. No proprietary news feed or
internet needed in final cBot. Feature contract can be replicated
with `MarketData.GetBars(M5, symbol)` on Cloud; source-data
completeness and actual Cloud execution not yet certified.

## Cost and control comparisons, fixed before outcomes

Original two-sided BID/ASK AMD and EURUSD separately sampled as-of
09:40, 10:20 and 11:00 NY for EACH causal intent (regardless outcome),
side age <=20 sec, no crossed or unresolved `hasMore`. Source and
quote requests under a hard post-auth read-only ceiling of 6000.
One original Pepperstone EUR LIVE account with identity guard only;
current exact broker minimum volume, step, commission/minimum,
USD-to-EUR conversion, signed margin buy/sell and no-swap schedule.
No missing quote or tariff replaced by OHLC or zero; all symbols
and holiday UNKNOWNs counted. Original protobuf tape plus decoded
bars/contracts/quotes encrypted RSA/AES-GCM under installed
original custodian BEFORE any post-entry financial scoring.

For each completely priced event use exactly equal original
entry clocks and independently defined same-signal reference:
(1) PRIMARY adaptive invalidation;
(2) same-side FIXED 11:00 exit;
(3) AMD own 09:30–09:35 momentum FIXED 11:00;
(4) unconditional long FIXED 11:00;
(5) unconditional short FIXED 11:00;
(6) same-event **opposite-side falsification** FIXED 11:00,
    never eligible to replace primary based on results;
(7) cash. Each current min AMD wire volume, original actual
BID/ASK and EURUSD FX, precise fee currency and conversion, 0.5
bps central/2.0 bps adverse additional *modeled* roundtrip slip.
Actual historical tariff, fills, liquidity and financing remain
conditional UNKNOWN. At signal weeks report unmatched cases and
all 260 scheduled evaluation days, no-signal as cash 0 only where
full predecision source genuinely available.

First and last 26 evaluation weeks separately, both fixed.
Report event frequency, 2025/2026 coverage, all quote/FX/cost
unknowns, joint denominator matched control NET EUR, absolute
against cash, incremental against own-momentum/fixed/long/short
and reversal falsifier, plus independent calendar exposure label.
Without robust positive **adverse NET EUR** on both halves AND
a positive comparison against SAME-ENTRY own momentum and
same-side fixed, close primary exact; no recovery via its
opposite-side control or changing symbol/exits/clocks.
Even positive conditional result only supports further common
EUR300 native C# funded research, never independent alpha,
HARD21, 30% continuous DD, 12-month validated fills or LIVE bot.
No order, OAuth reauthorization, Cloud activation, services,
separate funded wallet or source duplications.

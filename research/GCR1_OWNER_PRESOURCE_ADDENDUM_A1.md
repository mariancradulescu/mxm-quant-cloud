# GCR1 OWNER 2026-11-15 — PRE-SOURCE ECONOMIC/CAUSAL ADDENDUM (A1)

**Binding prospective addendum; does not replace or edit**
`research/GCR1_COPPER_GOLD_AUD_MACRO_DIFFUSION.md` (initial protocol commit
`67de712dd2b4efd0acb39b1ea6e34d51b0aa233f`). Written AFTER synthetic-only
CI and BEFORE any GCR1 original source acquisition, economic labels, or scoring.
No previously closed study is rerun, rescued, or retuned. The ORIGINAL GCR1
primary direction, 780 clocks, 4h predecision bars, +5min entry, +4h05 exit,
capital, fee/slippage assumptions, and abstention rule remain byte-for-byte unchanged.

## A. Information attribution with FULL 780-clock intention population

The GCR1 main opportunity selection conditions on copper and gold having
opposite 4h signs. On *selected* clocks copper sign == inverse gold sign:
comparing just those clocks **cannot identify incremental metal information**.

Freeze THREE independent prespecified policies on EVERY scheduled GCR1 clock:

- `combined` (ORIGINAL, untouched): BUY if c>0 and g<0; SELL if c<0 and g>0;
  otherwise ABSTAIN, exactly as initial protocol.
- `copperOnly`: BUY if c>0, SELL if c<0, otherwise ABSTAIN.
- `inverseGoldOnly`: BUY if g<0, SELL if g>0, otherwise ABSTAIN.
- The predeclared original `audOwnMomentum` on AUDUSD's **completed** 4h
  return (positive BUY, negative SELL, zero abstain) and `long`, `short`,
  `cash` provide non-metal references.

No metal-only option is a new deployable candidate selected by later outcome.
These policies are COUNTERFACTUAL DIAGNOSTICS and do not modify combined intents.
To score own AUD predecision momentum, require the 49 aligned, completed
AUDUSD M5 bars at the same clocks; if absent, own comparator
`DECISION_UNKNOWN` rather than a substituted shorter return.

**Population comparison**: all 780 clocks, grouped by first 26 vs last
26 full weeks, including every known abstention (return exactly cash €0)
and every unknown state (NOT zero). Report separately:
1. fixed-calendar **matched-source-complete** clock count, union of financial
   unknowns, complete-case `NET_EUR` sums and per-clock means for every
   policy (primary and both individual-metal comparators);
2. conditional traded-only per-entry NET, gross, cost, win/loss and natural
   frequency; avoid comparing unconditional sums with event-only means;
3. primary-minus-copper, primary-minus-inverse-gold, and primary-minus-own
   per-matched-clock **adverse** NET, including cash abstentions and financing
   uncertainty. A positive difference due merely to fewer trades can establish
   portfolio ECONOMIC selectivity, not scientific independent contributions of
   both information sources;
4. 2×2 sign-state census: `c>0,g<0`, `c<0,g>0`, both same nonzero signs,
   either zero, either missing; same-sign clocks show where combined deliberately
   abstains but metal-only policies forecast different exposures. Report the
   metal-only financed cost/NET on each same-sign cell, without post-result
   promotion of the opposite, zero, or same-sign cells;
5. each metal policy with its own immutable source availability before
   outcome prices, and a SECOND complete-common-input panel where all original
   c/g/AUD context and all price/fee/FX quotes exist. Neither varying cohort
   nor a nonpriced benchmark is allowed to improve a primary comparison.

Do not announce `joint-information alpha` unless combined has robust
absolute adverse NET above cash AND positive calendar-matched incremental
adverse NET compared with *each* copper-only, inverse-gold-only, own-AUD
and constant-side reference across both exposed halves. Even then
an unobserved common factor, USD, regime, news and selection effects
prevent causal identification of both metals without later independent data.

No arbitrary matching of a smaller favorable subset or optimized
trade frequency; document policy-specific missingness and common-sample
missingness.

## B. Complete causal separation of request, signal, finance, exit

Three independent timestamps/states for every one of the 780 scheduled
moments, with an immutable pre-outcome `calendarSlotId`:

- `SOURCE_DECISION`: exactly 49 ORIGINAL completed contiguous M5 end timestamps
  from t-4h through t for c and g (and AUD own comparator separately),
  with no future t+5m quote or t+4h05m outcome condition. `combinedIntent`,
  `copperIntent`, `goldIntent`, `ownIntent` are finalized and recorded here.
  Missing required predecision bars -> `DECISION_UNKNOWN` for the affected
  policy; do not reclassify the others.
- `SOURCE_FINANCE`: fixed read-only original AUDUSD+EURUSD BID/ASK clock
  pairs at t+5m, t+4h05m. Require both individual sides as-of <=20s,
  positive, noncrossed and nontruncated. Missing future entry, exit,
  FX conversion, current fee, margin or session -> `FINANCIAL_UNKNOWN`
  for otherwise valid intents, NEVER retrospectively `ABSTAIN`.
- `SOURCE_RISK`: complete observed holding interval marks/financing and
  potentially continuous floating equity are a separate condition.
  A fixed entry/exit result WITHOUT sufficient holding marks remains
  `RISK_PATH_UNKNOWN` and cannot certify drawdown 30%, native C# funding
  or a real broker fill.

Call the read-only API on the fixed *full day* bar/quote calendar independent
of whether later metal signs predict an opportunity. Preserve every
original request/response protobuf and aligned decoded source encrypted
BEFORE computing any post-entry EUR returns. If the original source is
truncated/absent, retain the fixed calendar row as UNKNOWN. No widened
freshness or OHLC fills to make a losing sample appear priced.

**Existing-source audit before collection:** an archive is reusable only if
its original identity/cryptographic provenance, precise instrument/day/time,
every one of the 49 contiguous predecision M5 closed-bar timestamps,
native original independent BID/ASK at BOTH entry and exit, signed EUR
conversion, fees and relevant holding marks are truly present. IPC2
Copper/AUDUSD/EURUSD archives have only selected sessions and 12 weeks;
QPI1/SQIC1 are different target/time windows; old original H4 or BID-only
captures cannot supply the required M5 + paired bid/ask/FX for the
full-year GCR1. **Do not claim a complete reusable GCR1 panel** from those
public aggregates. Reuse genuine complete matching source partitions if
a protected per-clock scan establishes them before requesting duplicates;
otherwise collect the missing fixed source once, read-only, retaining
original source identities/custody. A true historical account tariff or
actual execution fill is never manufactured.

**Call plan if these exact new windows are missing:** 260 days × 2 distinct
metal M5 daily requests + 260 days × 1 AUDUSD M5 daily request for own
momentum + 260 days × 4 unique clock marks (08:05,12:05,16:05,20:05 UTC)
× 2 symbols (AUDUSD, EURUSD) × 2 sides = 780+4160 = **4940** market
data requests, plus roster/contracts/expected margin. All <= one
GCR1-specific fixed 5,200-request post-auth ceiling. Separate raw
requests per API response; no hidden retries outside budget; explicit
source completeness register. Four quote clocks avoid duplicate requests
for the coincident 12:05/16:05 previous exit/next entry.

## C. Capital and event-time precedence (one native EUR300 book)

Predeclared original 4-hour position holding: entry 08:05/12:05/16:05 UTC,
exit 12:05/16:05/20:05 UTC, **at 12:05 and 16:05 exit and next entry
share the same nominal timestamp**. This is an overlap, not two free slots.

For eventual native replay, at identical event timestamp:
1. mark existing holdings at causal original BID/ASK and apply costs/FX;
2. attempt due exits, commit realized settlement, release margin **only**
   after a valid financed close, update realized/float peak/equity;
3. if exit/mark is unknown, keep exposure/margin reserved and **do not**
   accept new candidate under assumed released funds; record unresolved;
4. only THEN recompute actual free margin, financial risks, directional
   conflicts, portfolio heat and open candidate affordability;
5. open new admitted entries at native legal units and record stable
   position IDs. Nothing counts HARD21 until its true funded roundtrip
   is fully closed. No capital reset at 26-week boundary, weekends or
   between policies within the common system.

Each diagnostic counterfactual policy has ONE independently simulated
€300 continuous book for comparison to cash, not simultaneous multiple
real wallets. The actual combined common portfolio always has only ONE
initial €300 and accounts for all existing instrument exposures. An
interval whose exit cannot be priced must stay unresolved, rather than
permit admission, backdating or an invented flat P&L.

The original **standalone conditional** EUR costs/returns from source
are not automatically the native funded portfolio NET. Portfolio
contribution is the difference between joint and identical-time
ablation books *after* original-market price, margin and risk proof,
without optimistic correlation credit. Drawdown 30% includes
floating and fees, not just settlement snapshots; the lack of
continuous observed marks stays UNKNOWN.

## D. Explicit stopping/decision

No change to original rule, costs, timing, 26/26 exposed splits or
closed studies. Do not use a positive bps outcome as financial admission.
If the main GCR1 model has a source-complete, negative adverse NET in
either half or fails incremental adverse NET versus the SINGLE-METAL
and original matched own/long/short/cash controls, reject the exact rule.
If required full common-clock source, fees or risk evidence is missing,
report that precise limitation as **INCONCLUSIVE**; preserve any
conditional financial loss and missing denominator separately.
A passing *development* condition would justify later native funded
ablation and genuinely independent, unexposed confirmation — not
promote a trading cBot or activate Cloud.

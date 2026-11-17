# LPM1 — lifecycle-conditioned position management, FROZEN before implementation
Date: 2026-11-17. OWNER directive after MRF1-F1 / ENE1.
Base main: 1d3bad797d9637f4a1fc01c4b6befcd4082ca7bc.
This distinct development experiment calls no closed strategy or old outcomes.

## Economic hypothesis and alternatives
Price direction alone at a fixed horizon need not predict the value of an executable
position. Completed M15/H1 direction and relative volatility may condition the NET
distribution of a full stopped/trailing position. Test that incremental information
against a pooled (context-free) lifecycle model and cash, on identical clocks/costs.
The joint action is {cash, long/short x three exit managers}. No universal R:R.
Report all six active fixed-action counterfactual portfolios, even if the learned
policy admits nothing. These diagnostic books each replay the SAME initial EUR300
under mutually exclusive counterfactuals; NEVER add their profits/capital.

## Authentic source, frozen calendar, and collection
EURUSD only, chosen for direct EUR conversion, a known affordable legal minimum,
and liquid tick history; this is not a claim about all instruments or HARD21.
12 full UTC Monday weeks [2026-08-17,2026-11-09).
Six training weeks, three calibration weeks, three evaluation weeks.
All dates are globally exposed development, not independent confirmation.
M1 and M5 source warmup starts 2026-08-14. Retain genuine complete BID and ASK
tick paths 07:59–12:05 UTC weekdays, separated into <=30-minute API requests.
Preserve protobuf replies encrypted under the existing custody recipient.
No OAuth rotation, order request, new account, live monitoring or permanent service.
Budget <=7000 post-authentication read-only requests; historical <=5 requests/sec.
Detect hasMore and incomplete pagination; split a truncated interval recursively
until complete; equal-millisecond ticks must not be discarded at page boundaries.
No interpolation or OHLC-derived SL/TP fills. Aggregate equal-time bid/ask events:
cross-side ordering is unknown; disclose any differing within-millisecond prices.
Quotes stale >30s, inverted quotes, unpriced completion and gaps are explicit.
Keep unknown lifecycle outcomes, not zero returns; unknown future paths cannot
remove earlier offers or selectively exclude poor trading days.

## Causal decisions and managers
Candidate entry after every completed M15 bar 08:00–10:45 UTC, first genuine
two-sided quote >=bar close+1500ms. At most one minimum-unit EURUSD position
in each counterfactual book; this is a one-symbol research design, not an OWNER cap.
Only previously closed bars enter features. ATR is mean TR of last14 completed
M5 bars (with previous close); equilibrium is mean last8 completed M15 closes.
Context: sign(last M15 close minus prior M15 close), sign(last H1 return from
12 M5 closes), and ATR relative to previous14 M5 TR mean: 3x3x2=18 cells.
No outcome-dependent feature thresholds, parameter grid or additional candidates.

Managers, both directions:
1. VOL: initial stop1.5 ATR, profit target2 ATR.
2. STRUCT: initial stop at the most adverse extreme of last8 completed M5 bars
plus0.25 ATR, requiring positive stop distance; target entry equilibrium only
when favorable. Otherwise no profit target; close on completed M15 direction
opposing the position. State the realized initial target/stop ratio per entry.
3. ADAPT: initial stop1.5 ATR; tick-observed favorable extreme and2 ATR trail;
after favorable excursion1.25 ATR protect0.35 ATR profit; no fixed TP.
Close on completed M15 direction opposing the position.
All liquidate at first available quote >=12:00 UTC; this is session/funding safety,
not the primary objective or a 5/30/60/120-minute forecast horizon.
Never move initial protection away from entry or assume a stop guarantees price.
Use existing NativeCausalExitResearch via a separate prospective path-state method,
preserving all frozen existing methods and policy semantics.

Model fills use the next observed valid quote >=100ms after request plus slippage;
no fill at a touched barrier. For ambiguous same-millisecond events, preserve and
flag uncertainty, do not infer an ordering. Slippage per side: central0.25 observed
spread; adverse1 observed spread, floor one price tick; current native contract
commission/minimum/conversion/margin. No second spread charge.
Funding excluded only if original current contract schedule confirms no charge
inside this intraday holding window; otherwise mark financial evidence unknown.
Quotes are authentic observations; all fills, current-tariff historical finance
and adverse latency/slippage are CONDITIONAL_COST_MODEL, not broker executions.

## Learning, selection and falsification
Generate six complete minimum-volume action NET labels per entry from genuine paths.
Training weeks1–6: per-action pooled means, contextual means shrunk with32 pooled
observations, empirical win probabilities and risk/outcome distributions.
Calibration weeks7–9: report predictive MAE/Brier versus pooled; freeze per-action
mean residual bias and16 residual quantiles (midpoint empirical quantiles).
No retuning, action deletion, inversion or calendar selection after outcomes.
Evaluation weeks10–12: frozen context model vs pooled model vs cash; at each offer
select via existing OpportunityOrchestrator/NativeFundedSession and risk machinery.
Feed calibrated16 NET scenarios with real legal minimum/step/margin; use actual
current common equity/free margin and initial stop-based risk including costs.
Reject unknown current facts and 30% peak-equity risk breach. No positive advantage
is assumed in advance. Counterfactual fixed-action diagnostic policies may submit
a minimum-volume research intent directly to the same ledger with explicit
financing/DD checks, without claiming economic-selector admission.
If insufficient complete train/cal observations (<80/<40 per action), preserve
coverage and fail the learned model; still report source uncertainty, no substitutes.

Primary economic claim requires evaluation adverse contextual NET>0 and incremental
NET>0 over pooled and cash, no unresolved held/pending positions, and no sampled
DD>30%. Weekly lower bound mean minus2 sample standard errors is descriptive only;
three evaluation weeks cannot establish robust/independent qualification.
Always show all fixed-action results and negative/zero outcomes.
No result grants promotion, Cloud activation, live/demo trading, or independence.
No post-result policy changes; justified technical corrections retain originals.

## Required original report
Source requests, M1/M5/tick counts, exact hashes and original run/artifact identities;
coverage, ambiguous timestamps, future-missing and unresolved lifecycle counts.
Complete per-trade NET and initial-risk R distributions, empirical quantiles,
expectancy, win rate, profit factor, extreme loss/ES, margin/free margin,
tick-sampled floating DD, completed trips in EVERY eligible week incl zeros.
Separate training/calibration/evaluation. NET contribution is final common capital
minus EUR300, never sum of counterfactual books. Show initial RR, entry selection
and exit manager ablations, prediction diagnostics, closed trade details and event
chain hashes. Disclose sampled risk and historical tariff limits. HARD21 systemic,
DD<=30% including floating and >=12months independent evidence remain final goals.

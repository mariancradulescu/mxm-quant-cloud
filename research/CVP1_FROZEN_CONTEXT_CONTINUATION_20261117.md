# CVP1 — context-conditioned continuation value, frozen before implementation
Date2026-11-17. Base187a93448a4cd0bc9f78c9317c4c645766c52d41.
OWNER decision after LPM1. No LPM1/other closed policy or outcome is called.

## Ex-ante alternatives and falsifiable economic choice
A. More fixed technical entry/exit thresholds: cheap but cannot identify whether
the current remaining opportunity compensates turnover and loss risk; rejected as
main research. B. Large deep reinforcement-learning search: flexible but high
selection/overfit risk and difficult native reproducibility; rejected here.
C. A small native fitted continuation-value function plus independently trained
complete-lifecycle entry value: chosen. A coherent price state may have different
future optionality under cross-instrument USD repricing and tick-activity regimes.
Hypothesis: these observations improve actual after-cost lifecycle action value,
and a learned causal stopping decision improves funded common-capital NET over
structural protection alone. This is not a repaired LPM1 exit threshold.
All original closed results remain immutable.

## Population, data and chronology
New original read-only EURUSD/GBPUSD/AUDUSD, all USD quoted with genuine EURUSD
conversion; chosen to compare shared USD repricing with instrument-relative states,
not as independent diversification. Native M1,M5,M15,M30,H1,H4,D1 broker bars,
all seven actually used. At least80 prior calendar days of D1/H4 warmup, and
enough lower-frequency bars for64 completed observations. Collect60 weekdays
of complete BID/ASK ticks07:59–11:05UTC over12 weeks [2026-05-04,2026-07-27).
Entry candidate clocks08:00–09:55 every5 minutes; management observed each
completed minute plus every available tick for protection and fills.
All calendars are globally exposed development, never independent confirmation.
Weeks1–4 fit continuation, weeks5–6 fit lifecycle entry value, weeks7–9 calibrate
residuals, weeks10–12 evaluate. No outcome-driven date/asset/feature selection.
Missing current input suppresses an offer causally; missing future lifecycle does
not erase the earlier opportunity and makes the affected book unsettled/unknown.
Report every excluded asset and source reason; require all three source roles.
At most10000 post-authentication read-only requests, <=5 historical requests/sec.
Recursive disjoint interval splitting handles hasMore; retain all equal-ms side
events and flag unresolved order. No OHLC SL/TP execution, invented bars or fees.
Original protobuf responses and decoded native tape encrypted with the existing
custody key/run binding. No credential rotation, order or live monitoring.

## Native state and causal hypothesis families
For EACH of the seven intervals use last64 completed native bars:
- EMA8 minus EMA21 divided by mean14 true range;
- close displacement from EMA21 divided by that range;
- RSI14 (simple mean gain/loss equivalent) centered/scaled to[-1,1];
- latest tick volume relative to previous20-bar mean minus1.
Also use M1 impulse, ATR(M5)/price, spread/ATR(M5), UTC session fraction,
peer-average H1/D1 normalized trends and own-minus-peer H1 trend.
Clip continuous normalized features to[-4,4]; no fitted clipping threshold.
EMA is seeded from the first supplied close and uses alpha2/(period+1);
ATR uses14 genuine TRs and previous close; missing windows are unknown.
Tick volume is activity, never exchange volume. Orient signed features by side.
The FULL model, NO_PEER model and NO_ACTIVITY model are separately trained
with the omitted block zeroed, all reported; no evaluation winner selection.

FLOW eligibility: side agrees with EMA8–EMA21 on H1, price displacement on M15,
and last completed M1 close change. RETURN eligibility: side points toward H1
EMA21, M1 change already points that way, and H1 path efficiency over20 bars<0.35.
Both require a protective structural stop beyond the last20 completed M1 extreme
by0.25 ATR(M5), strictly on the loss side of entry and not touched at entry.
RETURN additionally requires its entry-time H1 equilibrium target to be beyond
two observed spreads plus one price tick. FLOW has no fixed TP.
Before admission verify the same protection/target logic returns HOLD at current
quote; reject ENTRY_ALREADY_INVALID rather than allow an immediate forced close.
At actual next-quote fill, recheck; an incompatible pending entry is canceled,
not retrospectively dropped as if never proposed.
Newly changed states may genuinely invalidate soon after entry; count them.

## Learned management and entry value
Native linear ridge (lambda16 on non-intercept coefficients), no grid search.
Continuation fit on weeks1–4 actual consecutive minute quote transitions:
side liquidation-price increment normalized by ATR(M5), plus0.995 times positive
next-state continuation. Session-final continuation is0. Fitted iterations stop
at max coefficient delta<1e-8 or32 iterations; report convergence/iterations,
clip predicted continuation to[-4,4] ATR for numerical stability.
This Bellman approximation is model exploration, not an optimal-policy certificate.
At a held completed-minute decision, HOLD if predicted remaining continuation>0,
otherwise request CLOSE; tick structural protection always has precedence.
After favorable movement reaches initial structural risk, stop may protect
break-even plus estimated remaining costs and trail2 ATR behind tick-observed
favorable extreme, never loosen initial protection. RETURN equilibrium is an
observed target, not a guaranteed fill. The first quote at/after11:00 requests
session safety close; elapsed horizon is not the economic exit objective.
Reuse NativeCausalExitResearch with a separate prospective method.

Weeks5–6 generate FULL/NO_PEER/NO_ACTIVITY compatible entry lifecycle outcomes
using their frozen continuation model. Fit per-family native ridge entry NET
in entry-ATR minimum-unit EUR scale. >=40 complete training and>=20 calibration
observations per variant/family; if inadequate mark that model unavailable.
Calibration weeks7–9 freeze mean residual bias and16 empirical midpoint residual
quantiles, plus descriptive win/stop/target probabilities. No further updates in
evaluation. Model calibration is based on completed paths before evaluation.
LONG/SHORT/CASH selection uses those complete-cycle scenarios, actual costs,
structural initial risk and the existing native risk/orchestrator/session.

## Funded alternatives and execution
For each central/adverse scenario, mutually exclusive one-EUR300 books:
FULL, NO_PEER, NO_ACTIVITY, PROTECT_ONLY (FULL entry information, structural/
profit protection and target but no learned minute closure), SIMPLE (compatible
FLOW/RETURN opportunities without economic forecast admission), FLOW_ONLY,
RETURN_ONLY, CASH. Removing one family is a whole-portfolio ablation.
No sum of book returns. Offer all eligible instruments jointly; multiple symbols
can coexist if funded. Use legal minimum units in this bounded edge experiment,
not an OWNER cap. Partial reduction below the minimum is infeasible: report it,
do not invent volume or double size just to demonstrate a partial.
Existing positions reserve their observed margin and conservative remaining
stop/cost risk. Shared rank scenarios assume adverse comovement, no independence
or diversification credit. Report every rejection reason and simultaneous risk.
No forced HARD21. System risk capacity equity minus0.7*observed peak; all held
positions enter it. At observed DD>=30%, request protective liquidation and suspend.
Gaps may overshoot; cannot certify a continuous bound from observations.

Model entry and exit fills: first valid original quote >=100ms after request,
central slippage max(price tick,0.25 observed spread), adverse max(price tick,
observed spread), on the appropriate side. Entry allowance fixed at request;
exit allowance repriced at fill. Current observed commission/minimum/FX fees,
legal volume and direction margin included separately. No double spread charge.
Use current exit slippage for reported conditional floating equity and risk,
in addition to the immutable ledger accounting; explicitly disclose gaps/staleness.
Composite quote/FX age<=30seconds. Current tariffs/margins are conditional
historical scenarios, not certified historical terms. Require genuine current
funding schedule to exclude a charge during the intraday session; otherwise stop
financial scoring, preserve original source and reason. No guessed zero financing.
No protection-order API calls; observations support research, not actual fills.

## Decision metrics and gates
Original source counts/hashes/custody; scheduled/compatible/offered/rejected counts.
Per mechanism and common book: central/adverse NET and incremental vs cash/SIMPLE/
ablations, expectancy, win rate, profit factor, payoff, complete-trade R distribution,
MFE/MAE, realized empirical stop/target counts/probabilities, initial RR distribution,
cost attribution, worst loss/ES5%, floating DD, margin/free margin/concurrency,
fully closed trips each W13-phase eligible week (all three evaluation weeks incl0).
Prediction MAE, Brier for NET>0, chronological weekly stability, mean-minus2 weekly
SE (descriptive only), model coefficients/counts, unknown labels/paths and residual
uncertainty. Zero-trade realized metrics=N/A. Do not infer qualification from CI.
Primary support requires FULL adverse NET>0 and incremental vs cash/SIMPLE>0,
settled book, no unknown held path and no30% sampled DD breach. Peer/activity and
management ablations identify incremental contribution, not automatically winners.
No promotion even if this exposed three-week evaluation passes. The final >=12
relevant independent months, robust NET, systemic HARD21 and risk requirements stand.
Exact negative outcome closes this configuration without retuning/inversion/rescue.
Technical diagnostics may preserve and identify actual errors without replacing
the original receipt or claiming fresh independent evidence.

## Official capability boundary
https://help.ctrader.com/open-api/symbol-data/
https://help.ctrader.com/open-api/messages/
https://help.ctrader.com/open-api/
Native indicator equivalents are reproducible C# research, not a live cBot launch.
Source collection never invokes any closed study, scoring model or trading request.

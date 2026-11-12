# YRC1 — JPY cross-asset risk-release and failed-auction equilibrium

OWNER v2.0. Registered BEFORE original Pepperstone market collection/scoring.
Two independent new economic mechanisms; NOT a rerun, retune, inversion,
or resurrection of JYP1, JRC1, AEX1 or any closed study.

## Economic rationale
A. Existing NZDJPY / new mechanism: failed acceptance (a quote-activity
expansion into the prior hour range followed by rejection) can mean-revert
when the close remains displaced from the eight-M15 equilibrium. Distinct
from JYP1's same-direction AUDJPY/NZDJPY catch-up and range acceptance.
B. NEW Pepperstone CADJPY (not previously financial-backtested), with new
CHFJPY defensive comparison and USDJPY shared-JPY context. When CADJPY
is the more forceful JPY-adjusted currency move relative to CHFJPY,
and USDJPY corroborates the yen component, CADJPY may experience
secondary price discovery. Test CADJPY continuation after established
local M15 acceptance, not a generic directional filter. Confirm
each instrument's actual broker presence, position permissions,
minimum/step volumes, FX conversion, financing, and financing risk.
If symbol or contract absent, fail closed: do not substitute another
unregistered instrument.

## Original-account read-only source
Original authenticated Pepperstone account and existing protected secrets,
official paginated M5 and original historical paired BID/ASK ticks for
CADJPY, CHFJPY, NZDJPY, USDJPY, EURUSD; JPY->USD->EUR conversion via
original USDJPY and EURUSD bid/ask route. 8 full exposed development
weeks 2026-08-31..2026-10-25, historical warmup from 2026-08-28.
40 weekdays only; 03:00:01.500–08:55:01.500 UTC marks at each 5
minutes, each quote side <=30 seconds age, exactly observed
original ticks, no midpoint/future quote fills. Historical M5
original-bar pagination follows existing <=7000 request budget.
Contract/tariff current-as-observed only; not historically certified.
No claim of prospectively clean confirmation on these eight weeks.
The 03:00–09:00 bounded capture is motivated by Pacific-to-Europe
overlap and 120–150 minute holding observation; not a universal
limit on future mechanisms or symbols.

## Prespecified decisions / feature clock
Evaluate every completed M15 at 04:00:01.500–06:00:01.500 UTC
every 15 minutes on weekdays. Read only 8 contiguous completed
M15 candles ending exactly at decision minus 1500ms for target,
plus relevant comparator. At fill, freeze ATR14 from 15 contiguous
completed M5 and eight-M15 equilibrium. Never use an uncompleted bar.

### A. NZDJPY failed auction to equilibrium
The last candle must break the prior three-candle high but close back
inside that high (bearish failed upward auction), OR break the prior
three-candle low but close back inside that low (bullish failed downward
auction). Wick in the failed direction >2x the absolute candle body
and >0, latest broker tick update count >mean of previous three.
For short, current closing price strictly ABOVE the mean of the
last eight completed M15 closes; for long, strictly BELOW it.
Prediction sign is toward equilibrium (opposite failed wick).
Forecast gross fractional magnitude=abs(last close - 8-bar mean)
/ last close, strictly positive, not outcome-calibrated.
Entry 1.5 ATR protective invalidation, causal M15-equilibrium exit
tested at executable quote, maximum 120 minutes safety bound.

### B. CADJPY differentiated JPY repricing
Eight completed M15 CADJPY, CHFJPY, USDJPY. Last H1 CADJPY
return and last H1 USDJPY return must agree in sign and be nonzero.
CADJPY absolute H1 movement > CHFJPY absolute H1 movement.
CADJPY newest close beyond the previous three M15 high/low
in the chosen direction, and latest quote-update count greater
than preceding three-candle average. Forecast gross fractional
magnitude=min(abs(CAD H1)-abs(CHF H1), abs(USDJPY H1)),
strictly positive. Trade in CADJPY H1 direction.
At fill 1.5 ATR invalidation, dedicated causal profit lock:
after >=1.25 frozen-entry ATR favorable mark, lock +0.35 ATR
of profit and trail 2 ATR from observed completed-M5 favorable
extreme; if no >=0.5 ATR favorable excursion after 45 minutes,
stagnation exit at next fresh original BID/ASK mark. Also
3 ATR observed-quote profit target and maximum 150-minute
protective safety limit. No intrabar priority or stop fill assumed.
The new policy must not affect original archived C# modes.

## Funded EUR300 portfolio & controls
Native single C# shared selector and funded ledger, central/adverse
cost, original contract/quote conversion, fees, currency swaps
and current margin, capital and conditional financing; concurrent
opportunities compete without separate wallets. Evaluate
YRC1_JOINT, YRC1_NZD_ONLY, YRC1_CAD_ONLY, YRC1_LONG,
YRC1_SHORT, YRC1_FIXED (TRUE native fixed 90m exit control
on identical prediction rule and own financed book), YRC1_CASH.
Report NET central/adverse EUR and percentage of initial EUR300,
gross vs fully-costed NET, funded complete closures per actual ISO
week (HARD21 portfolio target, never family cap), reference
long/short/cash incremental, duration percentiles and
EUR-margin*time, sampled floating-equity drawdown and missing
marks, exit-reason counts, financing and marginal family ablations.
Outcome-blind rules, no grid search, no optimizing response to
this source, no copying original closed study result as confirmation.

No LIVE/DEMO orders, Cloud activation, OAuth refresh, new external
service, new repo, synthetic broker fills, protocol rewrites,
retrospective promotion, or more than the single original source
collection requested. No trading qualification on eight weeks.

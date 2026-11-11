# CMR1 — US small-cap cash-close session-anchor reversion

Authority: `docs/OWNER_SPEC.md`, OWNER v2.0 and 2026-11-11 decision.

## Economic premise and distinction

Index CFD prices late in the New York cash session can temporarily deviate
from an accumulated session trading reference as intraday inventories are
rebalanced. If a large displacement has already begun to unwind before
15:30 New York, the remaining 20-minute cash session may continue to pull
US2000 toward its *broker tick-activity weighted M5 typical-price anchor*.
This is NOT the true exchange VWAP, an auction-imbalance measure or an
observation of institutional orders. The claim is falsifiable. It is a
cash-close anchored *within-instrument* inventory reversion hypothesis,
not ESP1's midday relative-size continuation, RRP1's NAS100/US500 leadership,
LDP1's NZD/AUD residual, QSR1's spread wait or a closed NAS100 rule.

## Ex-ante exact rule

US2000 is the sole trade candidate. EURUSD supplies observed USD/EUR
conversion only. Evaluate fixed weekday sessions 2026-05-04 through
2026-10-30 (26 weeks), chronological halves of 13 weeks. All dates are
globally exposed development data, never independent confirmation.
The instrument must be enabled on the authenticated original Pepperstone
EUR account, have a valid currently observable minimum-volume contract,
both minimum-direction margins within the initial EUR300, positive fees
or explicit zero-fee fields, short eligibility, and a valid trading
schedule covering entry to exit.

For each NY-local weekday, require *every* completed M5 bar from 09:30
through 15:25 (72 contiguous bars). Define session reference
A = sum(tickVolume * (high+low+close)/3) / sum(tickVolume), using
only those completed bars and strictly positive total tick activity.
At 15:30, let d = 10000*(lastCompletedClose/A-1). Require |d|>=20 bps.
Require that the absolute deviation measured from the completed 15:10
bar at 15:15 exceeds |d| by >=3 bps, i.e. reversion already started.
Forecast long if d<0, short if d>0. Fixed entry 15:35 NY,
fixed exit 15:55 NY. No price between decision and entry may alter
the signal. No holding across daily swaps.

The *declared* same-clock benchmarks are long, short, cash and the
last 60-minute (14:30–15:30) completed-bar momentum sign. All policies
use identical eligible signal days and 15:35/15:55 quote clocks.
Missing target BID or ASK, USD/EUR conversion, fee or margin is unknown,
never replaced or treated as zero. Quote evidence is indicative:
no fills, market depth, or historical tariff certification.

Price each side at as-of <=20s historical entry/exit BID and ASK.
Preserve separate observed spread, current contract commission,
positive fees and P&L conversion. Current terms are retrospective
scenarios. Charge 0.5 bps round-trip central and 2.0 bps adverse
additional hypothetical slippage to each non-cash policy. Equal-weight
priced observations within a week; equal-weight active weeks within a
half. No tuning, inversion, candidate substitution or outcome-driven
calendar changes.

## Admission and integration boundary

Per half require >=10 fully EUR-convertible priced events in >=6 distinct
weeks and >=75% priced of the pre-price completed-bar signals. Require
model adverse mean strictly >0 and above every declared funded-direction
proxy benchmark (long, short, last-hour momentum) in EACH half.
Passing this hurdle authorizes only a separate PROSPECTIVE common EUR300
native C# funded evaluation with matching reference books, source
cost uncertainty, open-equity/margin, ablations and systemic HARD21;
it does not imply funding, historical fills or independent confirmation.
Otherwise exact CMR1 closes with its original receipt. No orders,
Cloud activation, credential changes, or legacy replay.

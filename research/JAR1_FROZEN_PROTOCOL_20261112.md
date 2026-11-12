# JAR1 — causal prior-session index-opening reversal (pre-score freeze)

**Freeze time:** 2026-11-12, before evaluating any JAR1 payoff on AIP1
rows. The following is a *new distinct historical development hypothesis*,
not a refit of AIP1/BDP1, not a COL1 long-only filter or inversion, and not
a retune of a closed model. Only already exposed original-account
authenticated source labels are available, never a fresh holdout.

## Economic premise and universe

The 120-minute index opening move on one trading session can reflect
temporary inventory pressure. On the next nearby market day this move
might partially reverse as inventory is rebalanced. The hypothesis is
falsifiable and directionally symmetric: opposite the **previous**
observed 120-minute opening return, never the latest current-session
return. This may fail, including after spread and commissions.

Source frozen file: `docs/AIP1_AUTHENTIC_RESULT.json`,
expected raw-file SHA-256 `ed23b6d7ce289ce1eeede6626ef8d9bce09d2cfbdb59fd6fe4b4493a75a4bd3c`.
Original authenticated source run **41735441128**, source audit in that
receipt. Use exactly six original index CFDs:
AUS200, GER40, JPN225, NAS100, UK100, US500.

Analyze **only** existing AIP1 selection interval
`Protocol.developmentEnd <= At` and `Exit < Protocol.selectionEnd`,
the 13 calendar weeks already exposed to research. Never use
`ExposedAudit`, later `Forecasts`, source prediction `Side`,
`MeanBps`, `Primary`, `StandardErrorBps` or their outcomes for
model selection or for an entry signal. Do not reopen/replace AIP1 or
COL1 decisions. Only prior **selection** observations provide signals.
Missing earlier history means abstention, not assumed zero.

## Causal signal and matched policies

At each source-scheduled market event `(Symbol,At,Exit)`, select the
latest **earlier** source event for the *same symbol* that satisfies:
`prior.Exit < current.At`, `0 < current.At-prior.Exit <= 96h`,
`prior.OutcomeBps` is finite and nonzero.
The source's signed `OutcomeBps` represents gross close-only two-hour
return, not the historical AIP1 fitted forecast side. Select the latest
previous *scheduled* event first; if that event lacks a usable matured
outcome or is too old, abstain rather than skip backward to a favorable
earlier day. No current outcome or any later row is used for the signal.

**JAR1 side = negative sign of prior outcome**. Entry is unchanged
original opening+30m clock, exit unchanged opening+150m (120m holding).
One candidate per original source symbol/calendar event; no extra
event filling. Any missing current label is an unknown outcome, not a
pre-entry exclusion; all signal candidates must be counted.

For every eligible JAR1 event, score JAR1 reversal, same-clock
continuation (positive sign of prior), fixed long, fixed short and
cash on the *identical* event set. Never select a winning direction,
symbol or calendar from results. No historic strategy modification.

## Economics and evidence

For each candidate with a complete *current* close-only label, use
`gross=side*OutcomeBps`,
conditional central proxy `gross-CostBps`,
conditional adverse proxy `gross-2*CostBps`.
The source's `CostBps` is already published source-date current-term
round-trip modelled friction; NOT historical executable BID/ASK, EUR NET,
real slippage/funding or native broker fills. Invalid/missing costs
yield unknown outcomes for all policies, never a zero-cost trade.
Equal-event mean within each of all 13 weeks followed by equal
calendar-week means (zero activity separately identified, **not**
treated as a successful no-trade week); include all six symbols and
both first six and last seven chronological weeks. Report candidate
frequency, missing source coverage, source calendar participation,
unconditional and matched-policy gross/central/adverse proxies, and
paired cost-equal adverse deltas.

Descriptive statistics, if support exists: HAC(3) with fixed
2-endpoint Bonferroni 1.959963984540054 factor, applied to all 13
weekly adverse means versus cash and to weekly JAR1-long differences.
Require for preliminary exploratory economic support, *without
promoting*: positive adverse mean in each prespecified 6/7-week half,
positive full adverse mean, positive HAC-adjusted lower bound for
adverse versus cash and versus same-frequency long, and >=4 distinct
completed-signal weeks in each half. Zero-activity weeks count as
zero in the full-calendar statistics. The same tests apply in the
reported receipt even if the result is negative; no fallback tuning.

No EUR300 funded replay can be inferred from bps proxies. The
original source event calendar is feature-selected and not all
broker-open sessions, and distinct indexes may have correlated
risk/exposure. HARD21 must use actual financed closed round trips,
not source candidate counts. Do not annualize 13-week exposure.
Independence, historical tariff continuity, fractional risk,
continuous drawdown, execution and Cloud parity are unproven.
No read-only broker request, token use, orders, Cloud activation,
new external service or separate ledger.

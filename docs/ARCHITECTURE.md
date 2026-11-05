# Architecture status under OWNER specification v2.0

Controlling requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md).
Status below describes implementation, not economic or activation acceptance.

| Component | Implemented | Material limitation |
|---|---|---|
| Read-only authenticated collector | Original LIVE binding, SCOPE_VIEW, bounded Open API, v2 encrypted custody and C# receipt/readback | Source-specific quote coverage and historical cost evidence remain incomplete |
| Research | Frozen causal studies, a positive conditional modeled wick fragment and MSP1 development across 12 instruments/multiple timeframes | No independently confirmed NET edge; shared exposed calendars |
| Native opportunity selection | Common joint scenarios, greedy marginal utility, causal clocks, redundancy/conflict rejection, shared risk/margin reservation | Research heuristic; no authentic incremental portfolio validation |
| Python funded replay | One EUR200 chronological event ledger, overlapping positions, bid/ask, supplied FX/fees/slippage/financing, aggregate round trips | Sampled marks; no certified continuous drawdown or historical execution proof |
| Native C# economics | Common funded ledger/session, attributed monetary reconstruction, open-equity/margin observation, forecasts and shared allocation | Authentic filled broker recovery, full execution equivalence and continuous risk remain unproved |
| Native Cloud adapter | Single observation-only cBot, native inventory and timer reconciliation | No trading authority, autonomous trading recovery or device acceptance |

Flow: authentic source → causal opportunities → predictive evidence → common
native selection → shared allocation/risk → funded chronological replay →
independent confirmation → fully equivalent native C# → single Cloud cBot.

Historical recovery proof obligations below remain applicable. The prior status
table was superseded without deleting its git history.

## Restart proof obligations

Native Positions, PendingOrders, History, HistoricalOrders and Transactions are inventory sources. Their availability does not prove unlimited retention or completeness. Closing history is not a continuous floating-equity series.

Let H(t) be the supremum of account liquidation equity since authorized inception, including unrealized P/L and accrued costs. Drawdown is 1-E(t)/H(t). Sampled equity cannot guarantee observation of every intra-sample peak; execution gaps cannot guarantee the 30% limit. The validation policy must include conservative liquidation estimates and preventive buffers.

Two paths can have the same deposits, closing deals and current positions but different unrealized peaks before closure. Therefore those records alone do not uniquely determine H. Replacing H by max(200, current balance, current equity) understates drawdown after profitable excursions and is prohibited.

A certified upper bound U >= H gives conservative drawdown 1-E/U. Establishing U from market data requires complete exposure intervals, volume changes, executable prices, conversion rates and cost bounds. OHLC reconstruction without these premises is not certified. No finite justified bound means Protective mode: no new orders and no inferred reset of the peak. The current implementation deliberately supplies no peak certificate. This is a protective foundation, not yet autonomous restart acceptance.

Unknown order outcomes must not be retried. Future intent reconciliation must map broker order/deal IDs and labels, handle partial fills and establish a request barrier before any new submission. Labels alone are not broker-side idempotency. Missing history or uncertain requests keep the system protected. Existing positions require a separately validated protection/exit policy; this diagnostic build never manages them and must not be deployed for that purpose.

Adaptation must be a bounded deterministic function of causally available, ordered data and a versioned configuration. Missing warmup or model selection events prevent promotion. No durable LocalStorage assumption; no permanent external service is introduced. Future execution adapters must use the same core as replay.

## Official references

- https://help.ctrader.com/ctrader-algo/compiling/ — external build and AlgoBuild/AlgoPublish/IncludeSource.
- https://help.ctrader.com/ctrader-algo/mobile-algo/ — mobile Cloud operation.
- https://help.ctrader.com/ctrader-algo/references/General/Algo/ — native collections.
- https://help.ctrader.com/ctrader-algo/guides/local-storage/ — Cloud storage limitations.
- https://help.ctrader.com/open-api/ — OAuth, read-only scope, historical API and limits.

Linux compilation is distinct from Cloud-host runtime and Android device acceptance. Those runtime tests remain blocked by the absence of activation authorization, not by a Desktop requirement.


## Prospective observation feasibility

EPA1 and EPA2 retain their frozen receipts, methods and outcomes. The current
research sequence starts with source and economic support, before substantial
collection. `CausalObservationClock` selects the first valid atomic event using
only prior route state. It requires explicit complete pagination and fresh valid
BID/ASK plus conversion sides. It never selects a price extremum or fabricates
missing observations. CEF1 compares every authenticated event-window result with
the independent Python reference, then checks route-local costs and funding
support separately from common portfolio observation coverage. Counts are unique
symbol/horizon/cohort paths, not duplicated across candidate families.

CEF1 cannot approve a full economic study: new feature/label sample sizes and
chronological trial registration, new-episode pilot, joint holding valuation and
repriced financing remain required. Missing historical tariffs, depth, account
stop-out and intramark risk remain explicit. The CEF1 event clock and holding-risk
policy run in research/replay. The current Cloud adapter additionally observes
platform open equity/margin through NativePortfolioObservation; it does not
transmit protective closes. No economic qualification follows from compilation.

CEF1 run41695561224 verified native/reference parity on4284 authentic windows.
It found570/612 common all-six clocks and8/36 fully supported unique paths under
the explicit minimum-volume current-rule financing screen. This validates a
usable observation mechanism on exposed source; it does not validate a predictive
candidate or permit selecting the successful July cohort. XAUUSD April capacity
failures demonstrate why source coverage and EUR200 funding must be checked
separately. The subsequent batch endpoint invokes the identical holding-risk
kernel in one process, removing thousands of process launches. Protected readback
requires its entire economic support result to match the original frozen receipt.

## SQP1 economic research integration

SQP1 directly combines native sequence forecasts (M15/H1), event clocks, source
valuation, the existing opportunity allocator and holding-risk kernel with the
existing one-capital funded ledger. It adds no workflow file, external service,
second allocator or broker simulator. The existing protected collection/custody
jobs execute the outcome-blind small pilot, bounded continuation, raw reconstruction
and all disclosed economic cases. Conditional research and verified product
admission remain distinct. Dynamic quote unions follow selected/open exposure;
missing unrelated symbols do not erase a valid portfolio valuation. Same-calendar
state IDs align common decision/exit request horizons, not fictitious identical
fill timestamps; loss/peak aggregation grants no diversification credit. Independent
incremental NET, continuous risk evidence and full native ledger equivalence remain
unresolved; compilation of these kernels is not final Cloud product acceptance.

SQP1 run41706496201 completed real source collection, raw custody reconstruction,
native forecasting/selection/holding protection and funded chronological evaluation.
The primary uncertainty screen abstained; central sensitivities admitted seven
closed modeled trips and lost about EUR2.13/EUR2.43. Maximum overlap was one:
implementation supports shared simultaneous exposure but this study does not
validate its economic diversification. All24 primary ablations are zero from
abstention, not evidence of incremental alpha. SQP1 is closed without retuning.

The frozen book audit reconciles cash and every cost, confirms the native early
capacity-protection signal precedes the XAUUSD close, and distinguishes factual
trade attribution from marginal reallocation. Original generic EPA1 close labels
are preserved as provenance. A neutral caller-controlled label is now available
for future dispatchers; old caller defaults and frozen outputs remain unchanged.
The newly native sequence kernels are compiled into the single observation-only
.algo; the Cloud adapter and full funded ledger equivalence remain unfinished.

## Integrated programme and native funded-state transfer

BDP1 consolidates192 contextual diagnostics and48 predeclared contextual mixtures over52 complete weeks in one native discovery
pass with chronological26/13/13 boundaries, cost/financial support and explicit
multiplicity/exposure accounting. Conditional BID-bar cost scenarios are an admission
stage, not funded economic performance. Signal ceilings preserve every full week,
including zero weeks, and cannot count as HARD21. The existing allocator is retained;
execution-priced joint allocation and marginal portfolio testing remain later
requirements for any candidate surviving this programme.

NativeFundedLedger now contains the funded monetary/position state previously only
in Python. Native facts reception binds existing encrypted evidence and immutable
intents/fills/marks, checks accounting and sampled equity, and restores after every
event without invoking old research logic. Hash-bound checkpoints detect accidental
corruption; they do not authenticate broker history or certify global equity peaks.
Native modeled fills still require an execution adapter and broker outcome recovery
before product acceptance. No order path or permanent Python service is introduced.


Executed state: source41724643418 and corrected reception41726863225 reconstruct441,240 authentic M5 bars. The initial32-bit calendar defect is disclosed in `BDP1_EXECUTION_REVIEW.md`; original artifact13275041084 remains preserved.64-bit week partitions now pass for all240 groups across both13-week evaluation phases. No mixture passes even the base-cost scenario, so there is no new financed NET or portfolio marginal-NET proof. The exact configuration is closed, without relaxed thresholds or subset promotion. The result is stored verbatim in `BDP1_AUTHENTIC_RESULT.json` and audited in `BDP1_EXECUTION_AUDIT.json`.

Native funded fact confirmation matches the frozen SQP1 cash/costs/sampled drawdown within EUR1e-18, including restart after each of90 events per nonempty scenario and idempotence. Higher causal current margin is respected for new-position admission. This pure C# state is available in the common core; cBot remains observation-only. Actual broker outcome reconciliation, representative simultaneous financed exposure, independent NET, HARD21 and continuous floating-equity certification remain unproved.


## Cash-opening research and native broker identity state after PR48

AIP1 is closed on authentic run41735441128: six index CFDs,394,847 M5 bars,456 matured training labels,22 training weeks and646 later session episodes. No forecast passes the predeclared uncertainty screen even before costs. There is no new financed NET, marginal portfolio benefit or independent confirmation. Original successful receipts and the earlier Decimal custody interruption are preserved in `AIP1_AND_NATIVE_IDENTITY_RESULT.md` and JSON records. Old studies remain unchanged.

NativeFundedSession is wired into the one observation-only cBot: order/deal/position identity contracts, account-bound checksummed local checkpoint, model/broker remaining-unit mapping and broker-clock freshness for modeled floating equity. At PR48 the ledger was a modeled monetary book; PR49 added attributed monetary reconstruction, while identity facts alone still cannot create priced broker fills or authenticated money. Missing held marks block further model entries. Unknown journal history remains unknown after restore. The genuine current/seven-day empty broker receipt verifies protection and normalization; nonempty partial-fill monetary import, durable Cloud restart, actual peak/equity history and operational product acceptance remain absent. No transmission/order code is introduced.


## Atomic monetary reconstruction after PR49

NativeFundedSession now connects positively attributed deal/funding monetary facts to the SAME NativeFundedLedger through atomic whole-journal reconstruction, with partial entries/exits, fees, causal EUR conversion and funding. Missing costs/history, stale cash, mismatches or deleted old facts reject adoption without balance repair or capital reset. v1 checkpoints migrate; MODELED/BROKER financial domains remain distinct. The cBot reaches this gate with unknown current history/financial evidence and remains observation-only.

`NATIVE_MONETARY_RECOVERY_RESULT.md` separates the executed immutable MODELED settlement proof (four cases,30 recovery cuts, EUR1e-18 cash/NET tolerance) from deterministic funding/partial-fill contracts and unavailable genuine nonempty broker recovery. No new economic experiment or source request occurred. Open-position liquidation/margin evidence and lifetime peak remain unknown; checksum-bound local state is not encrypted custody or proof of Cloud durability. Economic qualification and all final OWNER targets remain outstanding.

### Continuation after PR49: open-equity integration

`NativeFundedSession` now owns `NativePortfolioObservation` as well as the common
monetary ledger. The observation-only cBot supplies current account equity/margin,
position quantities and net PNL, checks their independent reconciliation, and
persists the sampled observed peak in its versioned session checkpoint. It emits
entry suspension and reduction-review identities, never order requests. Current
platform marks exclude any unknown extra exit/liquidity cost; no lifetime peak,
continuous drawdown, actual liquidation or Cloud persistence is certified.
Frozen SQP1 holding valuations exercise this path without rerunning its signals,
allocator, exits or NET. CCP1 uses the same native valuation in a bounded financing
preflight; it supplies no return model and promotes no counterfactual to a strategy.

## Current integrated status after MSP1 (2026-11-04)

MSP1 evaluated 12 instruments and multiple timeframes only in exposed historical
CONDITIONAL_COST_MODEL research. It has no adverse selection support and is
closed exactly. Its modeled bps cannot flow into the native EUR200 allocator as
financed NET; no additional models, orders or Cloud activation followed.
Instrument universes are research eligibility, not mandatory simultaneous positions.
The native common allocator, monetary ledger and portfolio observation session
remain the single implementation route; independently certified full lifecycle,
continuous drawdown and durable Cloud restart remain outstanding.

### Native broker flat-state reconstruction without durable LocalStorage (after PR56)

The existing native Cloud cBot now reads the documented cTrader Algo
`Transactions` (`Transaction.Id/Time/Type/Amount/Balance/MaxEquity`) and
`History` (`HistoricalTrade.ClosingDealId/PositionId/EntryTime/ClosingTime/
GrossProfit/Commissions/Swap/NetProfit/Balance`) in addition to
`Positions`, `PendingOrders` and current account balance/equity/margin.
After two identical source-fingerprint polls, an **entirely flat** account
with a single positively observed initial EUR200 deposit and no other observed
cashflows may be reconstructed atomically into the **existing**
`NativeFundedLedger`. Each distinct closing trade's reported net is summed
with the same initial EUR200 and compared against the current broker balance.
The reported gross, swap and commission must explain its net; missing/ambiguous
monetary components reject the readback. Prior accepted settlement fingerprints
cannot disappear or change. No second capital ledger, new risk allowance or
synthetic balancing transfer is introduced.

Cloud cBot does **not read or write LocalStorage**: the official Cloud runtime
keeps it in memory, GetString on an unset key can raise an exception and Flush
cannot persist. The native broker readback begins afresh on each restart and
retries automatically on the normal timer.
Known unresolved local order intents, held positions, pending broker orders,
additional cashflows, unsettled commissions and unexplained cash differences
still prevent this exact *flat* adoption. A nonflat account stays under
`NativeFundedSession.ReconcileMoney`'s positive execution-history evidence
requirements; no open position is discarded to manufacture flatness.

**Separate certificates:** a successful flat cash identity restores an
account-bound current cash record and permits causal *research/observation*
to continue without storage. It does not establish lifetime cashflow-history
completeness, filled-order attribution, HARD21, a continuous equity path or an
upper bound on the historical peak. Transaction `MaxEquity` contributes only an equity-peak **lower bound**.
Previously observed sampled drawdown and peak are never reduced by a newer
cash readback. Historical closing balances are not equity marks when other
positions may have been open. The unknown lifetime peak **upper bound** is
not reconstructed or reset after restart.
Recovered historical closing rows are deliberately not counted as certified
complete funded round trips without their complete opening/fill chain.
New orders and trading Cloud activation remain impossible.

Official API contracts:
https://help.ctrader.com/ctrader-algo/references/Account/Transactions/Transaction/ ;
https://help.ctrader.com/ctrader-algo/references/Trading/History/HistoricalTrade/ ;
https://help.ctrader.com/ctrader-algo/references/Trading/Positions/Position/ ;
https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/ .

CI `BrokerFlatReadbackChecks` covers restart without checkpoint,
funded wins/losses in one EUR200 book, repeated polls, stale/truncated history,
unknown financial legs, extra transfers, pending orders, unreconciled intents
and evidence of an earlier observed equity peak. These are deterministic
contracts, not broker execution, actual Cloud restart acceptance or
predictive economic validation.

## Authentic extended universe and economic evidence (2026-11-05)

The architecture still has **one** authority: [OWNER v2.0](OWNER_SPEC.md).
The collector, run-bound encrypted readback, native C# selector, risk accounting,
NativeFundedLedger, NativeFundedSession and observation-only Cloud cBot are
unchanged foundations. A new research source does not add a second ledger,
allocator, trading runtime or independent trading authorization.

| Layer | Implementation and authenticated evidence | Not established |
|---|---|---|
| Full instrument inventory | PR #73, protected cTrader SCOPE_VIEW run #41939175379, 5,339 nonarchived symbol rows, 1,755 visible, 96 current contract probes, 89 margin observations, 74 current minimum margins below EUR200 | Full contract coverage, current *tradability* of every visible symbol, historic spreads/margins, actual EUR200 executability |
| Conditional quote costs | PR #74–75, CSP1 run #41940740480, 19 of 36 causally synchronized BID/ASK quotes; 8 stale/asynchronous, 7 missing-side, 2 crossed/invalid | Historical complete spread distribution, commissions, slippage, conversion, funding, fill feasibility |
| Extended-universe prediction | ERP1 run #41948500095: 393 equal-notional paired opportunities, adverse selection negative; MBF1 run #41971150620: 8 predeclared groups, none pass selection | Broker-priced EUR NET, independent edge, portfolio funding, system HARD21, continuous drawdown proof |
| Native financial execution semantics | Existing common selector and native C# ledger support modeled shared allocations, monetary facts, partial fills and sampled open-equity observation; CI exercises synthetic/frozen deterministic contracts | Real nonempty broker order/fill parity, complete lifetime equity path, durable Cloud restart, fully authenticated historical financed NET |

The two Asian MBF1 groups have **zero complete evaluable episodes**: 260
scheduled feature clocks lacked complete aligned source observations. They are
**data-limited, not evidence of a negative edge**. The other MBF1 groups are
negative after central/adverse conditional cost in the globally exposed
selection calendar. ERP1 and MBF1 remain frozen in their exact scored forms;
neither may be inverted, retuned, rerun, or salvaged from exposed audit outcomes.

**Evidence integrity:** the existing byte-for-byte `frozenFileSha256` gate
now covers `docs/FULL_CTRADER_ACCOUNT_INVENTORY_AUTHENTIC_20261105.json`,
`docs/CSP1_AUTHENTIC_SPREAD_RESULT_20261105.json` and
`docs/MBF1_AUTHENTIC_RESULT.json` in addition to ERP1 and historical
receipts. `research.verify_owner_policy` verifies source/coverage semantics
and rejects silent financial qualification. These checks protect original
evidence; they are **not** a statistical or financial certificate.

**Operational development rule:** before implementing a forecast, establish
from already archived source the required consecutive completed bars, session
calendar, prospective entry/holding marks, development-period cost observations,
current minimum-volume/margin applicability and route conversion/funding gaps.
Incomplete scheduled clocks remain denominators, not zero-return trades.
Admit distinct hypotheses by economic premise and causal availability, not a
fixed number of families, two favorite horizons, or an inherited universal
40-trade / 3-standard-error gate. All reused historical calendars remain
globally research-exposed; another asset on that calendar is not an
independent confirmation.

**System financial boundary:** a hypothetical margin below EUR200 is necessary
only for the instrument's current minimum grid; simultaneous portfolio capacity
requires shared cash, currency conversion, commission floors, open P/L and
margin/risk reservations. Conditional bps is not native funded EUR NET. The
existing C# funded ledger/allocator is used only after distinct selection-period
economic support; no risk or frequency passes solely from proposal counts.
HARD21 remains a system-wide requirement on complete financed round trips per
prospectively eligible week. The 30% portfolio maximum drawdown needs floating
liquidation equity including costs and conservative unseen-peak bounds;
sampled marks are insufficient. The Cloud cBot still has no authorized order
path or accepted runtime.

## OCE1 source reuse and economic outcome

Read-only original-source-only [OCE1 run #41976399909](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41976399909)
reused the **original bound-account** BDP1 USD/CAD M5 and ERP1 SpotCrude H1
encrypted archives without broker requests or old predictive model calls.
Original protobuf reconstruction verified 74,161 M5 and 5,877 H1 closes.
An explicitly preregistered Tuesday–Thursday 12–15 UTC calendar had
614/624 complete source/holding clocks, avoiding the previous MBF1 Asian
missing-feature failure. The H1 energy feature, subsequent M5 entry
and two-hour target holding have distinct causal timestamps.

The single predeclared oil-export-receipts-to-CAD directional hypothesis
produced 192 **unfunded** signals. The 46 selection signals averaged only
+0.123398 directional gross bps, versus -6.203439 central, -12.461684
adverse and -24.754270 stress bps after *conditional non-financing*
costs. Development cost cases used 18 causally observed, original
BID/ASK quote windows; actual commissions, financing, conversion,
slippage, fills and historical funded margin remain unknown. Current
minimum USD/CAD margin EUR29.79 is not an execution certificate.
The exact OCE1 configuration is closed as **not supported**, without
reversal, retuning, audit-based rescue or a gratuitous funded C# replay.
This negative result does not disprove unrelated market premises, shared
system HARD21 or the project; it does NOT validate them either.

The same existing SHA256 gate now pins the original OCE1 public result,
alongside the other November 5 source receipts. No simulated proposals
count as broker round trips or native financed EUR NET. The common native
risk/ledger path remains the only permitted eventual portfolio path
when a **distinct** candidate earns prospective economic support.

## Integrated cost attribution and actual specialist-to-native boundary (IES1)

The current source material distinguishes authentic **historical** BID/ASK
observations from the **current** authenticated broker contract (including
commission type, minimum commission and currency, lot size, physical minimum
volume and step, PnL conversion rate, funding schedule, leverage and margin).
The official Open API `ProtoOASymbol` supplies four commission calculation
types (USD/million USD, USD/lot, percentage of quote notional, quote
currency/lot), a separate minimum-commission currency/type and per-trade
volume in cents; current `ProtoOAExpectedMarginRes` is a point-in-time
observation. Algo `Symbol.MarketHours`, `DynamicLeverage`,
`GetEstimatedMargin`, `CommissionType`, `MinCommissionType` and
`PnLConversionFeeRate` are documented but not automatically certified by
historical Open API archives. No historical DOM panel is available.

`research/contract_eur_cost.py` converts each contract fee to **EUR**
using explicitly supplied, time-bound cross-asset rates and a separate
minimum-fee floor. Missing rate, tariff, financing or slippage is **unknown**,
not zero. Recorded spread is charged **once** when projecting from a mid-price
forecast, or **not added** on top of already BID/ASK-priced cash execution.
The gross-PnL-dependent conversion fee remains unknown until the relevant
profit amount and conversion rate exist; current broker fields are not a
certificate of historical fee schedules. No closed study receipt is repriced.

`ResearchSpecialistAdmission.Inspect/Estimate` now provides an executable
internal responsibility boundary: feature clock, broker/quote and FX evidence,
predictive comparison against a benchmark, full EUR uncertainty/cost/margin
screen, then only the EXISTING `OpportunityOrchestrator.Estimate` on common
states and a single EUR200 capital book. The same `NativeFundedSession`
and `NativeFundedLedger` remain responsible for future actual priced
facts/held equity; this bridge does not manufacture those facts. Missing
finance or commission blocks candidate admission. No external agents or
second allocator/ledger exist; any nonempty allocation in synthetic tests
is CONDITIONAL and not a trade or a native financial parity certificate.

IES1 only audits the BDP1 **original encrypted raw source** (six existing
FX/gold assets, 52 globally exposed weeks, M5 and historical fixed quotes);
it never invokes BDP1's closed forecast or selector. Across ALL assets it
compares the sign of an already completed prior hour with the following
complete hour against an explicit neutral sign-probability benchmark and
reports complete weeks and missing bars. Original archived development
BID/ASK at fixed clocks is combined **illustratively** with later captured
current contract fees in EUR; no missing FX route, spread or fee is zero-filled.
No overlaid EUR fees are passed off as historical executable NET, no instrument
is selected as a winner from the exposed calendar, and no marginal allocation
is admitted without a separate prospective supported candidate.

The official cTrader CLI supports `backtest` for .NET 8 .algo files, but
requires a separate cTrader ID/password-file/account context (not supplied
by the existing Open API SCOPE_VIEW secrets). No CLI cBot backtest, broker
execution, demo order or Cloud activation is claimed here. Current Cloud
remains Linux-based and accepts only suitable compile-time dependencies.
Continuous floating-equity drawdown, true independent NET and system HARD21
are not demonstrated by IES1 or this integration.

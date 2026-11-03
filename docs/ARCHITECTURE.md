# Architecture status under OWNER specification v2.0

Controlling requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md).
Status below describes implementation, not economic or activation acceptance.

| Component | Implemented | Material limitation |
|---|---|---|
| Read-only authenticated collector | Original LIVE binding, SCOPE_VIEW, bounded Open API, v2 encrypted custody and C# receipt/readback | Source-specific quote coverage and historical cost evidence remain incomplete |
| Research | Several frozen causal studies, genuine preliminary positive wick NET, broad development across six instruments/timeframes | No independently confirmed NET edge; shared exposed calendars |
| Native opportunity selection | Common joint scenarios, greedy marginal utility, causal clocks, redundancy/conflict rejection, shared risk/margin reservation | Research heuristic; no authentic incremental portfolio validation |
| Python funded replay | One EUR200 chronological event ledger, overlapping positions, bid/ask, supplied FX/fees/slippage/financing, aggregate round trips | Sampled marks; no certified continuous drawdown or historical execution proof |
| Native C# economics | NET accounting/acceptance, source admission, forecasts and adaptive scenario sizing | Full native execution replay equivalence remains incomplete |
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
stop-out and intramark risk remain explicit. The Cloud adapter still does not use
the new clock or manage open risk; the existing native risk implementation only
runs in research/replay. No economic qualification follows from compilation.

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

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
| Native Cloud adapter | Single observation-only cBot, native inventory and immediate stop | No trading authority, autonomous trading recovery or device acceptance |

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

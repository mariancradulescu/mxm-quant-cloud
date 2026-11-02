# Approved direction and current boundary

The OWNER selected a new PUBLIC repository. The old repository remains untouched. Only sanitized source, public documentation and synthetic checks belong here. No account identifiers, original account data, market datasets, OAuth values, custody keys or decrypted artifacts may be committed or uploaded as public CI artifacts.

## Components

| Component | Responsibility | Current status |
|---|---|---|
| Machine-side collector | Existing Open API application, read-only authenticated account selection, bounded requests, encrypted custody | Selective extraction pending |
| Research | Temporal split, immutable data provenance, predeclared eligibility, distinct hypotheses | No new experiments started |
| Mxm.Core | Shared economic decisions, accounting, recovery and risk | Initial protective recovery and round-trip counter |
| C# replay | Same core; authentic costs, conversion, funding, executable bid/ask and margin | Pending implementation and data |
| Mxm.Cloud | Native account recovery and single portfolio; no external decision service | Observation-only adapter, stops immediately |
| Android | Import `.algo`, manage one Cloud instance, owner stop | Officially documented path; device acceptance pending |

No strategy is active. No historical numeric risk, margin, reserve or position-count caps are inherited. Python may support machine-side collection but is never a runtime requirement for the cBot.

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

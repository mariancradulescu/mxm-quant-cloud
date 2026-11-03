> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# cTrader CLI backtesting — bounded feasibility verification (2026-11-03)

Official Spotware documentation (checked on 2026-11-03):
- https://help.ctrader.com/ctrader-cli/
- https://help.ctrader.com/ctrader-cli/cbots/
- https://help.ctrader.com/ctrader-cli/faq/
- https://help.ctrader.com/ctrader-cli/use-commands/

**Documented capability:** `ctrader-cli backtest <file.algo> --account=<account> --symbol=<symbol> --period=<period> --start=<UTC> --end=<UTC> --data-mode=ticks`, or use `m1`, `open`, `tick-csv`, `m1-csv` according to available data. The CLI runs without Desktop on Linux, macOS, Windows or its official Docker image; a .NET8 `.algo` and authenticated cTrader ID are prerequisites. Reports can be saved as JSON/HTML and event logs.

**Present integration verdict: FEASIBLE IN PRINCIPLE, NOT EXECUTED.** The official batch CLI workflow specifies cTrader ID and a credential password file (`--ctid`, `--pwd-file`); the existing project uses cTrader **Open API OAuth SCOPE_VIEW**, which is a different authentication mechanism. There is no proof that these five existing protected environment secrets satisfy CLI login. Do not silently convert them, request new credentials, create a password file, or send credentials to GitHub. A read-only `metadata` check may be useful later, but CLI `backtest` must not be represented as currently available in the protected pipeline.

The **only current** `.algo` is observation-only; native CLI backtesting it today would show no trading edge even with credentials. Deferred until at least one research-proven mechanism warrants a read-only/no-live-orders C# parity harness. Do not use CLI's `run` or trading commands, do not alter cBot trading enablement, and do not add a parallel infrastructure merely to make a green CI check. Compare causal decisions, cost and execution differences, not artificially identical PnL.

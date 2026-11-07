# MXM — Cloud-native feature surface and economic family coverage (OWNER, 2026-11-07)

**Authority:** [OWNER v2.0](OWNER_SPEC.md). Research and data ingestion are separate from the final *single native C# cBot* running in cTrader Cloud. This is a compact **implementation and economic triage**, not an indicator sweep or a profitability claim.

## Official Spotware platform capability — checked 2026-11-07

The [official cTrader Algo API index](https://help.ctrader.com/ctrader-algo/references/) marks listed members with Desktop/CLI/Cloud environments. Platform availability does **not** prove that broker data has sufficient coverage or that any strategy has economic edge.

| Feature family | Official API / Cloud | Existing MXM capabilities | Economic use now |
|---|---|---|---|
| Complete OHLCV/tick volume and multi-timeframe | [MarketData/Bars](https://help.ctrader.com/ctrader-algo/references/MarketData/) **Cloud** | M5 authenticated custody, native H1/H4/D1 warmup | CPF1 three causal H1 families, 12 original instruments |
| Trend: EMA, KAMA/FRAMA, Donchian, ADX, Supertrend | [Indicators](https://help.ctrader.com/ctrader-algo/references/Indicators/) **Cloud** | C# Mxm.Core causal features, earlier closed momentum programmes | **CPF1 Donchian + tick-activity**; no indicator parameter grid |
| Mean reversion: Bollinger, RSI, Keltner, Stochastic | Same **Cloud** indicator catalog | Existing research on fixing, contextual reversions | **CPF1 prior-20 Bollinger z**; not a retune of LFX1 |
| Price action: closed high/low, rejection wick, swings | [Bars OHLC](https://help.ctrader.com/ctrader-algo/references/MarketData/Bars/Bars/) **Cloud**, pure C# math | Earlier M15 wick, auction and OHLCV studies are closed | **CPF1 H1 one-sided prior-12 sweep rejection**, no future pivot confirmation |
| Volatility, tick volume, DOM/BID/ASK | ATR/volume Indicators, [MarketDepth](https://help.ctrader.com/ctrader-algo/references/MarketData/MarketDepth/) **Cloud** | CSP1, DCP1, BCF1 genuine but incomplete paired cost at fixed clocks | Volatility from OHLCV feasible; DOM predictive economics remain source-limited |
| Contract, hours, leverage, margin, FX conversions | [Market Data Symbols and MarketHours](https://help.ctrader.com/ctrader-algo/references/MarketData/) **Cloud** | Original Pepperstone contract/margin inventory and native portfolio risk | Cost/margin eligibility *before* response scoring, 300 EUR one capital |
| Positions, pending orders and real settled history | [Positions](https://help.ctrader.com/ctrader-algo/references/Trading/Positions/) and [History](https://help.ctrader.com/ctrader-algo/references/Trading/History/History/) **Cloud** | NativeFundedLedger, broker flat/open readback, monetary reconciliation | Observation, joint risk and eventual accounting; **no order execution permitted** |
| Adaptive classification / regression / statistical model | Pure .NET/C# math **Cloud**, dependencies must support Linux | Native selectors, orchestrator, C# risk and ledger | Only if novel predictive mechanisms pass costs and matched benchmark |
| Broker clocks, session features | MarketHours, Server UTC **Cloud** | Authentic prior TWC1/LFX1 / source-gap research | Causal fixed decision clocks; no external economic calendar needed |
| CLI backtest, optimizer, indicator calculation | [cTrader CLI](https://help.ctrader.com/ctrader-cli/) research/CI only | GitHub Actions C# build and source-bound readback | Independent testing tools, **never a Cloud runtime requirement** |
| Open API and MCP | [cTrader MCP](https://help.ctrader.com/ctrader-ai-agent-connect/) and Open API research only | Existing Pepperstone read-only protobuf transport and encrypted custody | Research ingestion/accessory; never in the cBot decision execution path |

**Cloud-specific restrictions:** [official Cloud cBot requirements](https://help.ctrader.com/ctrader-algo/documentation/cbots/cloud-requirements/) state Linux execution, HTTP requests not sent, WebSocket port limitations and non-durable LocalStorage/files on restart. GUI, WinAPI, WinForms/WPF are not Cloud runtime dependencies. Actual [OnBarClosed behavior](https://help.ctrader.com/ctrader-algo/documentation/cbots/cbot-bar-events/) demands a *closed* candle, never the current forming bar. No automatic conversion of Cloud API availability into demonstrated historical price/quote or settled trade evidence.

## Distinct economic family coverage and current choice

- **Already historically studied and closed exact:** ERP1 (pair dislocation), PVE1/PVE2 (OHLCV path continuation/absorption, daily H1 pullback), OCE1 (oil/CAD transmission), GEP1 and IMT1 (cross-asset lead/lag), LFX1 (fix), FLS1 (FX underreaction), RCP1/IPF1 (adaptive common portfolio), MBF1 and other frozen hypotheses. No old model is imported, rescored or inverted.
- **Historical source-limited:** BCF1's 52 H1 weeks pass, but paired BID/ASK freshness preflight fails; DOM/tick-depth alpha remains unproved. Do not convert missing snapshots into favorable costs.
- **New, *separately prespecified* and evaluated jointly:** CPF1 `DONCHIAN_TREND_VOLUME`, `BOLLINGER_OVEREXTENSION_REVERSION`, `H1_FALSE_BREAK_LIQUIDITY_SWEEP` on the original 12 M5 Pepperstone symbols and authentic current-term cost contexts. Each uses complete closed H1 candles reconstructed from 12 consecutive original M5 bars. This is a new fixed **exact configuration**, not a retune of earlier rejection.
- **Unexplored and not claimed economically:** confirmed risk-adjusted native trend/mean-reversion/pattern combinations, continuous cloud DOM execution, native cTrader backtests with independent unexposed price history and reconciled fill costs.

**Experiment contract:** [CPF1 fixed protocol](../research/cpf1_protocol.json) fixes instrument universe, hourly windows, 26 development/13 selection/13 unscored-exposed-audit weeks, indicator thresholds, same-clock 4h-momentum and flat benchmarks, observed tariff/scenario costs, six familywise adjusted one-sided tests, F2 development futility and stop logic **before scoring**. The 52 weeks are all already exposed: positive results are exploratory only, never independent certification. A proposed signal is not a broker-financed, closed trade or native EUR net.

**Product boundary:** The existing `src/Mxm.Cloud/MxmCloud.cs` is observation-only (`AccessRights.None`, no LIVE/DEMO orders and no activation). Existing selector, C# native funded ledger and monetary recovery remain authoritative. Any selected feature must first pass exact C# parity and then joint EUR300 funded replay, true global floating-equity drawdown and system-wide HARD21; neither source bars nor an indicator alone qualify.

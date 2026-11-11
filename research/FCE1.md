# FCE1 · Common currency repricing and commodity effort exhaustion

Registered before requesting source. One continuous EUR300 C# development
portfolio, six ISO weeks from 2026-02-09 through 2026-03-20 UTC inclusive.
Treat the calendar as exposed. Process Monday–Friday 15:00–18:59 UTC,
with causal minute marks at second 1.5, no intervening clock imputation.
Enter from 15:15 through 17:15 UTC on completed M15 only. Use earlier M5
for warmup, combine contiguous groups into M15, and preserve the exact
input tape in existing encrypted custody. Causal BID/ASK at most 30 seconds
old per side and EURUSD conversion are for costs, fills and valuation.

## Two economic families

**FX common USD repricing.** GBPUSD, AUDUSD, NZDUSD share a currency factor.
Directional repricing is more likely to persist when both a currency pair
and EURUSD travel efficiently in the same direction. For each instrument
and EURUSD, compare the latest four contiguous M15 close-to-close moves
with the preceding four. Require same-signed latest hour return in both,
absolute return at least as large as the preceding hour's absolute return
in each, and net absolute move at least two thirds of total absolute
close-to-close travel in each. Use the smaller of the two latest absolute
returns as the exploratory gross return input. The last M15 change must
agree in both markets. Manage by M15 direction invalidation and entry ATR
protection, with a 90-minute safety cap.

**Commodity effort versus progress.** For XAUUSD and SpotBrent, test
whether an aggressive impulse exhausts when the next same-direction
candle requires more broker tick activity for less candle-body progress,
followed by a retracement. Of the last 11 contiguous M15 bars, use the
first eight as the baseline. The first impulse body exceeds the baseline
mean high-low range. The following bar has a smaller same-direction body,
higher tick volume, and a close extending the impulse. The third bar
must close beyond the second bar's open against the impulse. Take that
reversal only when the existing eight-close equilibrium lies ahead in
the proposed direction. Use the normalized distance to equilibrium as
the exploratory gross input. Exit by the existing equilibrium or
volatility protection, with a 60-minute safety cap. Broker tick volume
measures price update activity, with no exchange volume assumption.

## Financial comparison

Reuse the existing selector, common equity, outstanding margin, ledger,
adverse-cost path, grid and adaptive exits. Per-unit risk includes
1.5 entry ATR, spread and modeled slippage in EUR. Search the minimum
volume and one additional legal step when available. Obtain current margin
for both exact volumes in one authenticated request and conservatively use
the larger per-unit margin for valuation. Use the same forecast, cost and
risk inputs for the minimum-volume-only counterfactual. Forecast cost per
unit uses the minimum-volume fee floor; realized modeled fee uses filled
volume. These bounded sizing scenarios have no historical tariff,
independent risk calibration or broker-fill certification.

Compare joint, each family in isolation, long and short on the same
opportunity definitions and a minimum-only joint ledger. Each counterfactual
starts once from EUR300. Report closed central/adverse NET, incremental
adverse versus cash and the best constant side, marginal family and sizing
contributions, weekly closures, peak shared margin, and floating equity
coverage. Report 1-minute data gaps and drawdown on observed marks;
intraminute prices and equity outside the recorded market windows are
outside that measurement. A drawdown path with missing marks while held
does not certify risk. All evidence is exploratory and orders and Cloud
stay disabled. No candidate advances without positive absolute and
incremental adverse NET, adequate financial coverage and adequate evidence.

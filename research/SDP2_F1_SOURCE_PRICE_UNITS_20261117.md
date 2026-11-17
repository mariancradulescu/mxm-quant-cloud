# SDP2 F1 — source price unit correction, no model retuning

Original attempt Actions 44037808869 at e3d4bc1c01fa4e5a3936ad1f40a69796071bbe2b is preserved. During code review while the source job was still waiting, before inspecting any SDP2 score/result, Director identified that `research/decode.py:decode_bars` returns integer OHLC values in Spotware 1/100000 price units. SDP2 had used those integers directly in currency-conversion routes and physical-volume EUR evaluation.

This unit omission invalidates economic EUR comparisons across USD, JPY/CAD and GBP/AUD quote routes: simple USD-route cancellation is not a universal unit conversion. **Any economic output of the first attempt is invalid and cannot be selected or promoted.** The original attempt is retained, not replaced. The plugin has no workflow-cancel operation; the browser has no signed-in GitHub session, so cancellation could not be performed without a new login. No credentials were accessed or permissions changed.

F1 divides original OHLC integers by exactly 100000 **after** existing cryptographic/protobuf reconstruction and before source panels/FX/physical-volume valuation. Raw authenticated originals remain untouched. Timestamps, volumes, source universe, feature ratios, model family, hyperparameters, horizons, train/calibration/evaluation clocks, benchmarks, risk and native admission rules do not change.

Add a regression covering actual integer-to-price units and every used quote-currency route (USD, JPY, CAD, GBP, AUD), in addition to existing Python-label/native-ledger settlement parity. No score-driven parameter choice, selected asset, signal inversion, or favorable result rescue is authorized. The corrected technical execution requires its own explicit one-time intent and preserves both run identities and source digests.

This is an implementation correction within an ongoing new study, consistent with OWNER's technical-diagnostic exception, not reopening any closed study. Original attempt results must remain separately labeled invalid where they exist. F1 is not independent confirmation.

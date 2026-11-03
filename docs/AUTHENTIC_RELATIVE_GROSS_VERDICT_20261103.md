# Authentic new 5-FX USD-relative H4 gross verdict — frozen 2026-11-03

## Evidence and execution
* Frozen causal hypothesis: `docs/FROZEN_USD_RELATIVE_GROSS_20261103.md`; implementation in `research/relative_gross.py`.
* New GitHub PR #24 merged, main exact request marker commit `fa835d276573b1d19e51e28935bdc51c58140663`.
* Authenticated workflow [#41608022074](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41608022074): **SUCCESS**, original sealed Pepperstone Europe LIVE read-only run `41476636915`, ciphertext SHA256 `50e40f62156f598d715d6052e466ae7ef77b9bc39117cad37472c7f0f505e61d`.
* Native C# original source parity **TRUE**. Full weekly public research receipt in [Actions artifact](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41608022074/artifacts/13216809374). Public aggregate preserved verbatim plus provenance in [JSON](AUTHENTIC_RELATIVE_GROSS_VERDICT_20261103.json). Raw prices/account/secrets are not exported.
* The cBot remains observation-only; zero LIVE/DEMO orders, no Cloud activation.

## Actual research result
| Diagnostic | Result |
|---|---:|
| Five authentic annual-span H4 sources, bars each | 1,571 |
| Aligned five-instrument H4 timestamps | 1,571 |
| Selection-phase scheduled windows | 317 |
| Incomplete authentic feature/path windows | 10 |
| Complete paired predictive gross observations | 307 |
| Hypothetical roundtrip legs, **NOT actual executions** | 614 |
| Full eligible UTC weeks (zero weeks included) | 10 |
| Weeks with >=21 *planned* legs, not HARD21 broker completions | 10 |
| Positive pair gross fraction | 53.094463% |
| Mean historical BID-close *gross proxy*, bps per equal-notional leg | **-0.53448464** |
| Mean weekly aggregate *gross proxy*, bps per leg notional | **-14.83490858** |
| Approx 2.6-SE weekly lower bound, bps per leg notional | **-61.68807266** |
| Zero-cost robust-gross predeclared gate | **FAIL** |

At illustrative unverified round-trip **0 / 1 / 3 / 10 bps per leg** the arithmetic per-leg average remains **-0.53448464 / -1.53448464 / -3.53448464 / -10.53448464 bps**. These are NOT authenticated historical broker tariffs.

**Verdict: `CLOSED_GROSS_ZERO_COST_SUPPORT_FAIL_NO_RETUNING`.** The positive hit fraction does not overcome a negative mean and negative weekly lower bound. The exact cross-sectional rank-reversion hypothesis fails gross economic support before commissions; do not rescue by reversing direction, retuning the lookback, dropping unfavourable instruments or selectively choosing profitable weeks.

### Strict non-claims
The 307 episodes are causal BID-bar close-to-close **price-only labels**. They are neither broker executions nor filled events. No contemporary BID/ASK execution prices at these decisions, complete historical tariffs/FX swaps, actual minimum-lot EUR200 portfolio, funded NET EUR, actual HARD21, financed drawdown, independent held-out profitability or real order acceptance can be concluded. The final20% performance was never scored. Calendar has prior development exposure, therefore holdout isolation is not proof of independent confirmation. These limits do not imply the entire cross-sectional or predictive family is invalid, only this exact configuration.

No configuration restart, backward cherry-pick, reuse of the closed model or new code in the observation-only Cloud cBot is authorized by this receipt.

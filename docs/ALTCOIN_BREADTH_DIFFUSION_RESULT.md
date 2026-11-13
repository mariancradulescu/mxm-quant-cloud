# Delayed altcoin repricing — exposed development result

The protocol was published on the remote branch at commit
`56c842e6c1cc8b480c2129c56bd8e91ba540ae85` before the evaluator was run.
It is the parent of the separate code and result commit. The original
archive supplied 480,177 authenticated M5 bars. The decision required
all five series, with 235 of 1,428 clocks eligible. The other 1,193
clocks lacked decision evidence. None of the selected target holding
paths was missing. The strict decision coverage requirement applies to
this fixed cohort and calendar.

| Target | Signals | Peer gross bps | Own momentum bps | Matched long bps | Matched short bps |
|---|---:|---:|---:|---:|---:|
| XLMUSD | 34 | +0.09 | -3.63 | +4.93 | -4.93 |
| POLUSD | 25 | -12.51 | -5.34 | +3.69 | -3.69 |

Cash was zero. XLMUSD gross was +9.60 and -71.23 bps in the two segments
(30 and 4 observations), and POLUSD +27.19 and -171.34 bps (20 and 5).
The combined increments versus own momentum were +3.73 and -7.17 bps.
Descriptive 95% four-week block intervals for those increments were
[-52.18, +48.00] and [-52.08, +15.56] bps. Both exact configurations
failed the frozen screen. Low coverage and dependence on the common
cohort limit generalization across crypto contracts and calendars.

The original probes put minimum margins near EUR0.95 for XLMUSD and
EUR0.47 for POLUSD. These values alone do not establish legal current
volume, execution cost, EUR notional or availability. BID-bar returns
are gross price proxies. Synchronized executable quotes, actual minimum
volume, contemporaneous conversion and fees, and holding-period funding
remain unpriced. Gross and NET in EUR, common-ledger risk, HARD21 and
independent confirmation remain undemonstrated. No new broker requests
or funded round trips. The results do not warrant the C# common replay
for these exact rules.

[Protocol](../research/ALTCOIN_BREADTH_DIFFUSION.md) ·
[Aggregate receipt](ALTCOIN_BREADTH_DIFFUSION_RESULT.json).

Reproduce with Python 3.12 and NumPy 2.3.5:

```sh
python -m research.altcoin_breadth_diffusion /path/to/original.zip /tmp/altcoin.json
cmp /tmp/altcoin.json docs/ALTCOIN_BREADTH_DIFFUSION_RESULT.json
```

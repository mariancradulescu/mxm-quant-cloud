# US-24 opening dislocation — development result

The [frozen protocol](../research/EQUITY_OPENING_DISLOCATION.md) used
949,860 original M5 bars across 17 Pepperstone US-24 share CFDs. It tested
whether overnight peer-relative strength improves selection of an opening
reversal long. The rule chose a name before the 09:50 New York entry proxy
and held 45 minutes. The comparison used the same entry and exit clocks.

| Sample / policy | Clocks | Gross BID-bar proxy, bps |
|---|---:|---:|
| Overnight and opening disagreement | 228 | -13.2038 |
| Opening reversal alone, paired | 228 | -12.3774 |
| Uniform one-name benchmark, complete cohort | 201 | +0.5425 |
| Overnight and opening disagreement on uniform clocks | 201 | -15.7839 |
| Cash | — | 0 |

Across 51 weeks, 255 days were scheduled, 21 lacked a sufficient cohort
and four had no signal. Of 230 chosen opportunities, two model paths and
one opening benchmark path were incomplete. The original decision cohort
is retained. Missing outcomes do not replace a name. The uniform reference
requires future paths for all eligible names and is reported on its separate
201-day complete cohort. The available-case model mean equals the paired mean.

The model earned -13.1554 and -13.2489 bps in the two segments. Its
increment over opening reversal was -4.4133 and +2.5173 bps. The
combined increment was -0.8264 bps, with a descriptive 95% four-week
block interval from -11.9346 to +15.7301. The absolute interval was
-23.6094 to -1.9017 bps. Median sampled favorable/adverse excursions were
+46.44/-45.41 bps. The fifth percentile of final return was -238.87 bps.
These are bar-based diagnostics with exposed historical dates.

The exact rule failed its frozen follow-up screen. Contractual volume,
decision-time EUR conversion, executable quotes, fees and joint equity
remain unknown for these paths. The result does not establish signed EUR
gross or NET for varying notionals. Zero funded round trips, no common
drawdown or HARD21 evidence, and zero new broker requests or orders.

[Aggregate receipt](EQUITY_OPENING_DISLOCATION_RESULT.json). Reproduce
from repository root with Python 3.12 and NumPy 2.3.5:

```sh
python -m research.equity_opening_dislocation /path/to/original.zip /tmp/opening.json
cmp /tmp/opening.json docs/EQUITY_OPENING_DISLOCATION_RESULT.json
```

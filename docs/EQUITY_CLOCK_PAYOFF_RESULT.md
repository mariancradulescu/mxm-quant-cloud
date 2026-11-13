# Recurring equity-clock payoff — exposed development result

The original archive supplied 949,860 verified M5 bars for 17 Pepperstone
US-24 share CFDs. The frozen rule ranked one long candidate using the past
40 weekdays of same-clock stock-relative returns. It used 12 initial
weeks and evaluated 39 later weeks with 25-minute holding intervals and
the same number of positions in the paired benchmarks.

| Paired policy | Mean gross bps |
|---|---:|
| Recurring clock rank | -2.3274 |
| All-clock rank | -2.9345 |
| Uniform one-position reference | -1.0963 |
| Cash | 0 |

There were 1,686 paired clocks from 2,340 scheduled, with a weekly median
of 45 and range 12–59. The 2,168 available model paths averaged -1.7679 bps.
A total of 115 clocks lacked a decision. Among eligible clocks, missing
paths affected the model 57 times, the all-clock benchmark 70 times and
the uniform reference 539 times. These flags can overlap. The paired
result conditions on availability of all required future observations.

Gross was -3.0103 and -1.6747 bps in the two chronological segments.
Compared with all-clock rank, the mean increment was +0.6071 bps
(95% descriptive block interval -2.3020 to +3.9353). Against the uniform
one-position reference it was -1.2311 bps (interval -3.3786 to +1.1362).
The absolute gross interval was -5.2609 to +0.6594 bps. The paired gross
fifth and 95th percentiles were -94.29 and +83.60 bps. Median favorable
and adverse sampled excursions were +14.50 and -15.55 bps; the adverse
excursion fifth percentile was -105.49 bps. Excursions describe the
observed path and do not price a realizable exit.

The archive records historical minimum-margin probe estimates of
EUR0.09–6.69 across the cohort. Those are indicative. Decision-time
margin, current fee and executable bid/ask are unpriced. Since gross is
negative before friction, this exact rule fails the frozen screen and
does not justify targeted collection or funded evaluation. Central and
adverse NET and continuous drawdown remain unmeasured. Zero funded
round trips, broker requests, orders and Cloud activations. The entire
study is exposed development. No independent confirmation.

[Protocol](../research/EQUITY_CLOCK_PAYOFF.md) and
[aggregate receipt](EQUITY_CLOCK_PAYOFF_RESULT.json).

Reproduction with Python 3.12 and NumPy 2.3.5:

```sh
python research/equity_clock_payoff.py /path/to/original.zip /tmp/equity-clock.json
```

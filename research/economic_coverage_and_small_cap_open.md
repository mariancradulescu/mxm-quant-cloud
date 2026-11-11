# Economic coverage and small-cap opening adjustment

The original PR #192 is frozen. The cost diagnostic uses seven different
weekdays, November 2–10, 2026, with no signals or return comparisons on its
three diagnostic symbols. Observe AAXJ.US, EUBund-F and US2000 at 10:05
and 11:05 in the target exchange timezone (Berlin for EUBund-F, New York
for the other two). Observe EURUSD once at each distinct UTC clock.
Request historical BID and ASK over 60 seconds. Report separately missing
side, truncation, crossed pair, equal pair, age above 20 seconds and
coverage within 60 seconds. A fresh positive equal pair is observable at the
same as-of clock when both source sides are present. It is counted
separately. The economic gate uses at most 20 seconds for both sides,
with no relaxed fallback. Report exact failure codes from current
contract fee attribution and separate required FX for principal P&L from
FX for nonzero fees. Compare commission evaluation with versus without a
USD rate using only current explicit fields and observed prices. This is
prospective source diagnosis outside the original study dates.

**Predictive configuration.** US2000 only. Test whether overnight
repricing that contradicts the previous US cash-session final-hour
direction fades after the open. On Tuesday through Friday, use the
previous calendar day's 15:00–16:00 New York return and its 16:00 close,
and the current 09:30 M5 open. A completed 09:30 bar is available at 09:35.
Enter opposite the gap direction only when the gap and prior final hour
have opposite nonzero signs. Use 10:05 entry and 11:05 exit. The previous
cash close and final hour, rather than intraday relative equity dispersion,
define this hypothesis. Match gap continuation, unconditional long,
unconditional short and cash on exactly the same selected clocks.
No symbol substitution, parameter fit or retuning.

Before the extended collection, require an enabled US2000 with verified
short selling, positive minimum margin on both sides within EUR300,
and at least five of seven diagnostic days with both usable target and
EURUSD entry and exit pairs, contract fees, current session coverage, and
no daily swap crossing. If this fails, publish diagnostics without
predictive collection. If it passes, use May 4–October 30, 2026 in two
fixed 13-week halves. Require contiguous completed M5 for the prior
final hour and modeled holding interval. No interpolation. Use causal
executable prices and FX, observed current tariff components, and central
and adverse round-trip slippage of 0.5 and 2 bps of opening notional.
Compare the strategy and benchmark returns on the same priced subset,
report all bar-complete gross observations separately, and weight active
weeks equally. Require at least 12 priced observations across six weeks
and 75% of bar-complete signals per half. In each half adverse bps must
be positive and strictly exceed every benchmark. Otherwise preserve the
observed coverage or economic rejection and stop this exact configuration.

The screen is exploratory. An admission warrants a separately wired
common C# replay with real sampled floating marks and matched full-book
ablation. Source rows and credentials remain private. Only aggregate
receipts are published. No orders or Cloud activation.

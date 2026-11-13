# VIA1 — post-impulse price absorption with structural exits

## Ex-ante economic choice (OWNER 2026-11-13)

The last EURJPY quoted cross-parity study was gross-negative and closed. We do
not repeat it. Alternatives considered: a historical order-book imbalance
cannot be proven from the conserved source (live-only depth is not historical);
another fixed-horizon cross-asset acceleration duplicates an exposed information
channel; a completed 15-minute **impulse followed by a five-minute counter-move**
can instead reveal failed price acceptance. This is not the closed US500
09:30 opening-level reclaim, the M15 wick/session test or the signed-variation
continuation test: the trigger is a rank-defined *local impulse failure* at
any fixed intraday decision clock, with a shock-specific exit and invalidation.
The explanation may be false: a counter-move can simply be noise in a lasting
trend. There is no assumed edge or optimized threshold.

## Source, markets and time

Use the unmodified authenticated **NXE1** Pepperstone original account tape
from Actions run `43377275493`, encrypted artifact `14015883688`, public
receipt `14016671008`; verify cipher, receipt and plaintext SHA-256 in the
existing `research.us500_quote_confirmation.original_tape` function. No new
broker requests, no raw original data publication, no execution or Cloud
activation. Two predeclared existing-universe targets: EURUSD and US500.
The distinct new-symbol research direction remains authorized and open;
this study makes no inference about it.

Study exactly the original 17 wholly EXPOSED development weeks starting
2026-07-13, ending 2026-11-09, weekdays, UTC 10:00, 10:15 ... 16:45.
At each scheduled decision t (a sampled quote t+1.5 seconds), require
nineteen contiguous M5 as-of BID/ASK pairs through t (t-90m ... t),
strict positive ordered sides, valid signed EUR conversions and known current
contract metadata. The mark at t, not a later mark, fixes the decision;
a 5m snapshot does **not** establish the entire intrabar path or depth.

## Causal prediction and full policy — one exact configuration

Compute six nonoverlapping consecutive 15-minute log-mid changes from
the nineteen sampled prices. Latest change q must be nonzero and strictly
larger in absolute value than all preceding five changes. Its last completed
five-minute sub-change must have the opposite sign. Ties abstain. This
requires no fitted threshold, volatility multiple, extra indicator, or
symbol selection. Predict the opposite of q: absorption/reversion.

For each intent, freeze at t:
- shock starting midpoint S = midpoint(t-15m);
- shock extreme E = maximum of the four midpoints t-15m ... t for an
  upward impulse, minimum for a downward impulse;
- side = opposite sign(q).
Attempt one entry at t+5m on the broker-observed opposite-side quote.
Do not back-fill a missing quote or enter if the entry midpoint has
already reached or crossed S or violated E. Log these separately.

Exit at the **first subsequently sampled M5 mark** whose midpoint reaches
S (reversion objective) or violates E (signal invalidation). If neither
occurs, liquidate at t+95m (90 minutes after entry, a protective exposure
ceiling, not a universal profit target). Execute hypothetical liquidation at
the actual observed exit BID/ASK, including per-side slippage assumptions.
Missing a monitoring quote before exit means **UNKNOWN**, never a favorable
assumed fill or a forced close. Use no bar still open at decision.

Historical tariff continuity is not established: the original authenticated
current terms condition all EUR results. Validate the same observed minimum
volume, zero commission minimum and conversion fee when asserted, USD-per-lot
commission, correct signed FX conversions and current margin snapshots as
in the existing source evaluator. Do not cross a known swap time with an
unpriced funding cost. The initial stage is standalone, **unfunded**;
overlap across candidate clocks, cash, risk and systemic HARD21 remain
unresolved pending the shared native C# ledger.

## Comparison and falsification

Report scheduled, missing-decision, no-signal, signal-intent, missing-entry,
already-invalid-entry, missing-monitoring/financing, successfully-priced,
and exit-reason counts **separately**. Compare the conditional candidate
policy with: (i) fixed 90-minute reversion from the identical entry,
(ii) same-clock fixed 90-minute last-shock momentum, (iii) matched long,
(iv) matched short, and (v) cash. Every benchmark uses the exact same
eligible fully observed 90-minute monitoring path for fair paired
comparison; the adaptive candidate may exit early. Report candidate
returns on its own causally available exit separately, and a
complete-path *paired* subset for fair comparator arithmetic. Do not
select after knowing future completeness. Missing extension after an
early candidate exit is reported, not silently used to bias matched
comparisons.

Report GROSS, modeled central and modeled adverse EUR at legal minimum
size, weekly counts, first 8 and last 9 calendar weeks, worst sampled
open adverse mark, median holding time, source and protocol hashes and
fixed source identity. Cost assumptions and price proxy limits must
remain explicit. A target advances to full financial validation only if
positive gross and positive adverse conditional NET occur in both
chronological segments, and its paired adverse advantage over the
stronger of own momentum, fixed reversion, constant long/short and cash
is positive across all weeks. This is a strict preliminary evidence
test, not a global signal filter. Otherwise close this exact rule.

No outcome from these 17 exposed weeks is independent confirmation.
No retrospective retuning, inversion, changed stop, calendar hunting,
promotion on a small sample, broker LIVE/DEMO order, or Cloud activation.
All gains are provisional, not funded portfolio NET; OWNER still requires
one EUR300 native ledger, <=30% floating DD and 12+ months with untouched
chronological confirmation before any financial qualification.

# AEX1 fixed 90-minute control — postclosure technical correction

Owner v2.0 permits a bounded, disclosed technical correction where the original
financial experiment has an implementation defect. **Never overwrite or
reinterpret the original** AEX1 run #43240155847, artifact #13954129933,
public JSON SHA256 `6c601caa12d91f2f4661460082a18992be791fc0bd7ae1507e07de5b8269fba9`,
nor its original paired Pepperstone FCE1 tape (run #43036474843,
artifact #13863803890, source SHA256
`4decd33d6c4c66a5dfbf63b4a790d062e21ff65db3f8eed034db45f72b296d60`,
ciphertext SHA256
`c780798f12380a3be2a546f1a18f7cf14be774d9377eb535bfa9d82ccee4909d`).

**Observed defect**: original AEX1_FIXED C# model's effectiveExitPolicy
indicator was FROZEN_LEGACY_FIXED and funding horizon 90m; the actual
tracked position exit policy was built from `NativeProductMarket.ExitPolicy`
on the adapted tape, not from that indicator. Original artifact's supposed
fixed control had 3 Chandelier, 7 entry-volatility invalidation, 1 M15 reversal
and zero FROZEN_LEGACY_TIME exits. Consequently the previous original
+21.585678051 EUR comparison between AEX1 adaptive and purported fixed
control cannot prove exit benefit.

**Correction scope:** execute only `AEX1_FIXED` on the identical original
six-week FCE1 source with every input quote's **actual**
`ExitPolicy=FROZEN_LEGACY_FIXED` and `HoldingMinutes=90`. The hypothesis,
direction, forecast, feature clock, minimum lot, risk, cost, source, EUR300
initial single ledger, original AEX1 joint/long/short/ablation books and
frozen original receipts are not changed or reexecuted. In the same native
decision engine, fixed closing is requested on the first eligible observed
quote at/after 90 minutes and is not fabricated when unavailable. Verify
corrected control exit reasons contain no adaptive triggers and do not
allow a nonfixed closure to stand as 90m control. Price and commissions
remain conditional model fills, no certified historical execution.

The corrected reference can inform the *technical* interpretation of AEX1,
not a promotion/retuning/independent validation. No new instrument, signal
rule, data collection, order, Cloud activation, OAuth refresh, new account
or new external service. The original AEX1 joint adverse NET -37.81843135548
EUR stays economically negative regardless of corrected control outcome.

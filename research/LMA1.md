# LMA1 — London benchmark auction pressure

Temporary inventory adjustment around a scheduled physical metals benchmark may
revert after the auction. The benchmark schedule is a timing hypothesis, not a
claim that benchmark prices or actual auction order flow are observed. XAGUSD
(previously studied) and XPTUSD (new) are separately trade-targeted. EURUSD
is conversion only. No symbol substitution.

Fixed before data collection: 2026-05-04 through 2026-10-30, London local time,
weekdays excluding 4 May, 25 May and 31 August UK bank holidays. From closed
broker M5 bars, calculate the 30-minute log return ending at the auction clock
(noon silver, 14:00 platinum) and require absolute return >=25 bps. Reverse
the sign. Measure simple gross return from +5 to +35 minutes. Require every M5
close in each window. Use the same construction exactly one hour earlier as
a descriptive timing control, and same-clock long and short as directional
controls. No actual auction execution or spread estimate.

Preflight: enabled roster, opening mode, legal minimum units, both broker
margin directions. For every usable outcome, reuse the contract cost adapter
to price minimum-size two-side commissions under currently observed terms.
Use same-clock EURUSD M5 reference rates for indicative currency translation;
these bars do not certify executable FX quotes. Compare gross bps with the
mean commission hurdle in each half, excluding unobserved spread, slippage and
conversion charges. Tariff continuity and fill prices remain unknown.

Two fixed targets and two chronological halves, no optimization, no pooled
winner or independence claim. At least 15 auction sessions and 10 control
sessions, each across at least 6 active weeks in each half. Average equally
across active weeks. Gross must beat both directional controls, the timing
control and the commission hurdle in both halves before any further quote
collection or native replay. Even a pass only licenses exploratory follow-up.
No orders or Cloud activation.

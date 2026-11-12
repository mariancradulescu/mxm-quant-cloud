# WIR1 · Friday inventory reduction

Preregistered on the CAL1 continuation before inspecting outcomes for this
mechanism. Dealers and clients facing a weekend holding gap may reduce
intraday directional inventory late on Friday. Test a partial reversal of
the preceding two-hour price displacement. It is a calendar-conditioned
price hypothesis, with no inference of observed positions, flows or causal
attribution to dealers.

On Fridays at 16:00 UTC, use the open of the first and close of the last
of eight consecutive completed M15 bars. A nonzero move fixes the fade side.
Observe through 19:00 UTC. Quotes are the original as-of observations
retained in the first minute of five-minute slots. Enter on the next
eligible mark after at least one second, cancel a stale entry at ten
minutes, and use the existing ATR Chandelier and 90-minute safety exit
with subsequent quoted execution. Score the fade and its continuation
at the same initial opportunity, each with its own stop and exit path.
Include gross and central/adverse net normalized by entry notional.

Existing-instrument lane: original encrypted FCE1 source, target AUDUSD,
GBPUSD, NZDUSD, XAUUSD. Exclude the source's energy and conversion-only
routes from opportunities. Copper lane: independently verify original
Pepperstone name, trading mode, short permission, quote currency,
minimum-size margin and tariffs before reading prices. Collect only the
six corresponding Fridays, original M5 and five-minute quote marks with
EURUSD conversion. The source does not substitute for missing data.
Copper is a stand-alone test; do not combine its balance or results
with the existing portfolio. Current authenticated margins and tariffs
are retrospective scenarios. The adverse book doubles spread, slippage,
fee and financing debits and stresses FX; it provides no guarantee of fill.

Freeze at 2026-03-02 00:00 UTC. Training Fridays are 13, 20 and 27 February,
evaluation Fridays are 6, 13 and 20 March. Use only outcomes completed
before the boundary. Pool by family, normalize per entry notional, and
give each training week equal weight. Require three distinct weeks.
Require positive standalone and incremental expected stressed NET
relative to the continuation, after subtracting three times the larger
of the two standard errors of weekly means. The allowance is descriptive
on three correlated market weeks, without a confidence-coverage claim.
Raise the allowance for excess current estimated friction above training.
Admit the predetermined fade or cash using the common prospective gate
and current quote/fee/margin verification. Costs already in NET are
charged only once. No long/short choice based on projected gross.
The allowance is neither tuned to outcomes nor a quote-age substitute.

Use one continuous EUR300 native ledger per policy: joint, FX only, metal
only, long, short, cash. Same opportunities and causal exits for the
funded controls. Long and short ranking tokens establish consideration,
without a predictive claim. Report completed trades weekly, gross,
central/adverse NET, ablation differences and shared sampled risk. The
three held-out Fridays can falsify or motivate a longer study, cannot
provide independent confirmation, HARD21 or certified continuous DD.
An abstaining book at 0 EUR equals cash and has no proven advantage.

The cBot and replay call the same observation-only C# profile. The cBot
polls the same slot on a later runtime clock, using native terms and rates.
Exact live ticks, timestamps and FX parity remain unverified. The opt-in
profile is development-only. After restart, absent training history the
predictor abstains. Checkpoints without predictive state are rejected.
Financial monitoring and existing broker recovery are separate from the
isolated model ledger. No order, Cloud activation or new OAuth authority.

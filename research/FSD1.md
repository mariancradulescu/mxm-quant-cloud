# FSD1 · Year-scale original Pepperstone after-entry viability panel

Before reading outcomes, freeze the clock, costs, features, exits, controls and
screen. Original Pepperstone EUR account, read-only. Retain sealed input and
public aggregate receipt. No re-execution of a closed study. Use the published
CMA/XUA inventory for selection. GBPUSD and NatGas had observed minimum
margins EUR39.91 and EUR24.74. This is current-contract feasibility, not actual
funding or a selection based on historical performance. NatGas tests whether
a larger price scale can overcome a wider spread. Do not presume archive
coverage or independence. Project development already saw subsets of these
symbols/dates. Treat the entire source as development.

Request completed M5 bars from 4 August 2025 and discrete two-sided as-of
marks on UTC weekdays from 11 August 2025 to 9 November 2026 exclusive. Latest
quote-side age 30 seconds, no synthetic fills at OHLC points. Evaluation
3 November 2025 through 8 November 2026 (53 calendar weeks); earlier 12
weeks train only. Record complete market observations and priced outcomes
by ISO week. Missing marks/bars/funding cause explicit attrition.
Quotes: 14:00:01.500 and 16:00:01.500 UTC for both, plus 15:00:01.500
for NatGas and EURUSD. No inference about intrainterval risk or unmarked hours.

- GBPUSD: prior observed 14:00–20:00 session return is the baseline direction.
  Early-Europe 08:00–12:00 return confirms it if same sign. Hypothesis:
  overnight inventory repositioning that survives the next morning carries
  through the US overlap. Enter at 14:00 and mark scheduled exit at 16:00,
  before the observed late-session segment. Keep dissenting sessions in the
  control distribution. Never reuse a stale previous session after >4 days.
- NatGas: use 13:00–14:00 movement as baseline direction. Confirm it only if
  both last two completed half-hour closes are outside the same edge of the
  preceding observed 14:00–20:00 session range in the baseline direction.
  Hypothesis: sustained price acceptance beyond the preceding session
  distribution reflects energy inventory repricing. At 15:00, exit if the
  executable liquidation quote invalidates the prior range edge. Otherwise
  exit at 16:00. All paired directional controls use the same chosen exit
  clock for comparability. The bar prefix ends strictly before the entry
  mark. No tick rule, calendar forecast, DOM or external information.

Use actual observed entry and exit quotes, native contract commission,
round-trip slippage max(0.00001, spread/4) per quote and side, EURUSD
conversion and signed financing. Adverse: double spread/slippage/commissions,
negative financing doubled, positive financing zero, additional 0.1% on
the signed conversion rate. Current contract terms applied conditionally
to historical quotes. Prices are modeled quote fills at stated marks.

Measure favorable and unfavorable tails, gross capture, cost, central and
adverse NET for selected/other observations and matched long/short outcomes.
Fit separate equal-week win probabilities for confirmed and pooled prior
sessions before evaluation. At least eight training weeks per conditional
cell for scoring. Brier against pooled past probability on matched rows.
For each candidate compute paired weekly means against the reverse direction,
absolute adverse NET and 3 standard errors with positive lag-one dependence
allowance. Screen for positive absolute and incremental bounds, lower Brier,
and at least 40 observed evaluation weeks. This is a conservative joint
exploratory criterion for two preregistered candidates, not formal
multiplicity-adjusted inference. No optimization over horizons or thresholds.
Do not promote, and do not finance a candidate that fails the preflight.
The source covers at most two opportunities per weekday. It cannot establish
systemic HARD21, intrainterval drawdown or real broker execution. Native
features use only Algo-observable bars, ticks and contract inputs. Cloud
clock/quote parity and live restart continuity are separate.

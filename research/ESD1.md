# ESD1 · Extended-session economic discovery

Original Pepperstone EUR account, read-only. Use the original account inventory
for selection before opening outcomes. Existing NAS100, new LTCUSD, BTCEUR and ETHEUR.
NAS100 supplies weekday index exposure, LTCUSD supplies a different CFD class
with observed minimum size 0.1 and EUR2.51 inventory margin, and the two EUR crypto routes test
whether an account-listed EUR crypto contract can be priced over weekends
without relying on stale FX. Recheck mode, short eligibility, volume, fees,
swap schedule, current directional margin and market schedule. EURUSD converts
weekday USD cash flows. A weekend EUR target requiring a USD commission route
is ineligible if that contemporaneous route is missing.

Use 16 calendar weeks, July 20 to November 9, 2026 exclusive. Weeks 1–8
are earlier development, weeks 9–16 later development. All history is exposed
for project purposes. No fit or threshold search. Fixed clocks are UTC,
with quotes observed 1.5 seconds after the nominal clock and no older than
30 seconds. Candidates and controls share the same priced rows and exit clock.

- NAS100 weekdays 07:00 and 13:00, one-hour hold. Hypothesis is inventory
  rebalancing after a directional impulse that stalls. Compare completed prior
  H1 return with the final completed M15 move. Enter opposite the H1 return
  when the M15 already retraced up to half the impulse measured over the
  preceding 45 minutes.
  Benchmark is prior H1 continuation. Max ten potential trips per week.
- LTCUSD weekdays 07:00 and 13:00, one-hour hold. A high-activity late break
  of the earlier hourly range can mark new information diffusion. Require the
  latest completed M15 close beyond the high/low of the preceding nine M5
  bars, and more tick updates in the latest M15 than the preceding M15.
  Benchmark is prior H1 continuation. Max ten potential trips per week.
- BTCEUR and ETHEUR Saturday and Sunday 08:00 and 16:00, 30-minute hold. Hypothesis is
  weekend range rejection after one-sided quote pressure. Require the last
  completed M5 bar to breach exactly one edge of the preceding 25 minutes
  and close within that range. Enter toward its midpoint only if the midpoint
  is still ahead. Benchmark is prior 30-minute continuation. Max four
  potential trips per week per route. Assess both routes individually, since
  the clocks and crypto exposures overlap. This is a range rejection, separate from MBF1
  weekend shock drift and weekend-to-FX transmission.

Causal completed bars must be contiguous. Tick activity counts price updates,
with unknown depth. Use original paired quotes, native side-specific broker
fees, causal signed conversion, and known funding. Central slippage per side
is the greater of one quarter spread and 0.00001 quote units. Adverse doubles
spread/slippage/fees and financing debits, discards financing credits and
stresses signed FX by 0.1% on non-EUR flows. Current terms condition historical
replay. Model gross mid-to-mid and report NET and matched momentum, long,
short and cash. Coverage and friction are reported by route. A route needs
at least six distinct priced signal weeks in each half, positive absolute
and incremental adverse NET in both halves, and positive weekly adverse
lower bounds (three standard errors with lag-one allowance) versus both
cash and momentum in the second half to warrant native funded follow-up.
No favorable subgroup extraction. Individually priced trip opportunities
are distinct from a jointly funded result. Endpoint marks cannot certify
floating drawdown or model intrainterval liquidation. No orders or Cloud.

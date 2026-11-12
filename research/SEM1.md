# SEM1 · Session economics and predictive discovery

Original Pepperstone EUR account, read-only. Existing routes EURUSD, NAS100,
XAUUSD and SpotBrent span currency, equity index, precious metal and energy.
XAGEUR tests a newly priced silver route selected from the authenticated
inventory (observed minimum 50, EUR232.61). ETHEUR's ESD1 contract and quotes
justify testing weekday and weekend coverage with a distinct mechanism.
FSD1/ESD1 and existing archived FCE1/DCP1 prices have limited quote clocks for
this purpose. Use the inventory and their public receipts for source selection.
Collect fresh paired marks only at the fixed panel clocks. Verify account,
trading mode, two-sided permission, directional margin, volume and tariffs.

Ten calendar weeks from 2026-08-17 through 2026-10-25, exposed development.
Each week sample one weekday, rotating Monday through Friday, and for ETHEUR
also one weekend day, alternating Saturday and Sunday. Sample UTC entry clocks
01:00, 04:00, 07:00, 10:00, 13:00, 16:00, 19:00 and 22:00, each with endpoints
at +30 and +90 minutes. Observe quote sides as of nominal time +1.5 seconds,
up to 30 seconds old. Map every clock/horizon regardless of signals. Distinguish
current continuous contractual session, historical paired quotes, signed EUR
conversion and complete financial valuation. Rollover without supported tariff
math is missing. Count gross absolute terminal movement and zero-move friction
as feasibility diagnostics; a profitable ex-post direction cannot be selected.
Do not infer liquidity depth from quote availability or tick volume.

Completed contiguous M5, M15-equivalent endpoints and H1/H4-equivalent returns.
Six fixed hypotheses with same-row signed H1 momentum, long, short and cash
references. All clocks retained; neither half is used to choose the best hour.

- EURUSD: H1 counter-move inside the prior three-hour trend, with the last M5
  moving in the prior trend's direction. A short-lived inventory retracement
  may end as the original currency move resumes.
- NAS100: current H1 opposite to the previous H1; latest completed M15 in the
  current direction and current H1 magnitude exceeds previous H1 magnitude.
  Test whether full reversal of a prior hour denotes repricing persistence.
- XAUUSD: previous H1 gold return and EURUSD return have the same sign, with
  the latest M15 in gold opposite that sign while EURUSD's latest M15 still
  agrees. Test resumption of gold's move if the currency leg persists.
- SpotBrent: require aligned three-hour Brent and NAS100 direction, and Brent
  H1 sign opposite the three-hour direction. Test a common risk repricing
  surviving a transient local pullback. This is a price relation hypothesis.
- XAGEUR: XAUUSD divided by EURUSD at causal H1 endpoints leads the target.
  Require silver's H1 return to agree, but have smaller absolute return.
  Test lead/lag from EUR gold to EUR silver with a causal currency adjustment.
- ETHEUR: trade continuation of the latest H1 when the preceding three-hour
  return agrees and latest M15 tick activity exceeds the prior M15, while
  latest M15 direction still agrees. Quote activity is price updates.

Use native broker cost functions, separate commission, signed EUR conversion,
financing and slippage. Central slippage is a quarter spread per side with
the existing minimum. Adverse doubles spread, slippage and fees, doubles
financing debits, drops credits and stresses non-EUR flows by 0.1%. Current
contract terms applied to historical quotes are conditional. Summarize
direction, fixed-horizon gross, NET, adverse cost burden, and matched references.
First five weeks and last five weeks are two prespecified development halves.
Use calendar-week blocks with dependent legs/clocks kept within blocks.
Report equal-active-week means and three-standard-error lower bounds with
positive lag-one allowance. This is descriptive screening, not formal inference
across twelve comparisons. Only an entire route/horizon may warrant funded
follow-up: at least four distinct priced signal weeks in each half, positive
early adverse NET and incremental versus momentum, and late lower bounds above
zero for both. No hour or alternate-direction selection. A funded follow-up
would require the common C# allocator, concurrent marks while held, one EUR300
book, and relevant counterfactuals. No order, Cloud activation or independent
confirmation. Shared entry clock counts are overlap diagnostics only.

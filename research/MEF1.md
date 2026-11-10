# MEF1 — cross-class cost and capacity comparison before predictive collection

LMA1 interpretation addendum. The original protocol and receipt are immutable.
12:00 silver and 14:00 platinum are scheduled auction starts. The +5 to +35
minute window measures response relative to the scheduled start. No confirmed
completion timestamps or auction-flow data were observed, so LMA1 does not
establish post-completion reversal. Exact configurations remain rejected.
Sources: [IBA silver specification](https://www.ice.com/publicdocs/IBA_Silver_Auction_Specification.pdf)
and [LME auction guide](https://www.lme.com/-/media/Files/Trading/Systems/LMEbullion/LMEbullion-User-Guide-V18.pdf).

MEF1 uses existing original Pepperstone Open API account binding and current
contract terms. Eight Tuesday snapshots from 2026-09-01 to 2026-10-20.
AUDUSD at 13:05 UTC, others at 14:05 UTC. These are liquidity reference clocks,
not assumed open auctions or exchange event timestamps. Use freshest BID and
ASK within the preceding 20 seconds. Discard truncated, missing or crossed
observations. EURUSD is conversion only. No substitutions or time search.
Report observed spread and as-observed minimum-size two-side commission
separately. Spread plus current fee is an indicative hurdle, not a historical
round-trip fill or total cost. Slippage and time-varying spread at exit remain
unmeasured. No outcome-based instrument selection or price return scoring.

Compare targets chosen for economically distinct research routes: AUDUSD
(liquid FX control for cross-session risk transmission), SpotCrude (energy
inventory absorption), XPTUSD (industrial-metal liquidity distinct from the
closed LMA1 rule), Coffee (agricultural supply shocks), US2000 (small-cap risk
repricing). New symbols must be confirmed in the broker roster. Contract
margin is current and individual only. These routes require their own causal
trigger and directional control before any outcome study; MEF1 qualifies none.
Use the receipt to prioritize the next data collection according to coverage,
friction and ability to share EUR300, without combining historical results.
No orders, Cloud, credential changes, or C# funded evaluation in this preflight.

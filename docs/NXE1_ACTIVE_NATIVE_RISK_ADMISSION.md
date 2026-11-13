# NXE1 — prospectively binding full-position session risk + new economic mechanisms

Accepted OWNER correction after PR #255–#258. This branch registers **only
new research modes** `NXE1_JOINT`, `NXE1_EXISTING`, `NXE1_NEW`,
`NXE1_CASH`. The two new economic premises, frozen before new history
acquisition, are EURUSD cross-asset risk-transfer (existing), and
US30 industrial-vs-US500 return divergence with activity deceleration
(new Pepperstone instrument, optional only when contract and affordable
at minimum lot). US500 provides simultaneous context, not a tradable
candidate in this study. EURUSD provides original USD→EUR conversion.

**Critical risk boundary:** native `NativeHistoricalProductReplay.Evaluate`
now passes the evidence to `NativeProductMarket`, and both evaluator
and C# loop force the admission gate for every `NXE1_*` mode regardless
of any optional flag. Current native one-wallet EUR300 equity, floating peak,
free margin, physical minimum volume margin and minimum downside
override or bound user-supplied risk evidence. Causal as-of broker
schedule, full planned holding quote + conversion monitoring,
session interruptions and all gap risk must be accounted for.
No universal 120min holding cap; new candidates can specify larger
holds without changing frozen source protocols. No fabricated stop fill.

**Important economics limitation:** historical contract schedule read
in Nov 2026 is *not* an as-of schedule for Jun–Oct 2026.
It must NEVER be backdated to pass risk admission in historical replay.
The new source can nevertheless measure **exploratory predictive outcomes**
on observed historical BID/ASK, with calibration labels matured before
decision and fully described missing-quote scenarios; original historic
portfolio cannot be called prospectively financed solely from this
current schedule metadata.

The prospective hypotheses are not inherently profitable. A gross forecast
is merely a magnitude heuristic until actual later returns, cost
distribution and benchmark excess demonstrate predictive support.
No closed MSE1/YRC1 exact configuration is revived. HARD21 is
systemic; no orders LIVE/DEMO or Cloud trading activation.

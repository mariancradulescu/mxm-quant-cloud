# MCS1 — prospective cross-class H1 / completed-H4 programme (2026-11-08)

**Status: PREDECLARED + CODE IMPLEMENTED; AUTHENTIC ORIGINAL-ACCOUNT
H1 COLLECTION NOT STARTED.** Attempting to create a new protected
GitHub Actions workflow containing the original Pepperstone credential
environment was rejected by tool safety checks. No retry that alters
or bypasses that restriction is authorized. No new account H1 bars,
BID/ASK history, authentic predictive labels, outcome metrics or
funded EUR NET are available from MCS1 at this stage.

Authority: `docs/OWNER_SPEC.md` v2.0, original EUR300 prospectively
funded shared capital, HARD21 SYSTEMIC and global max drawdown 30%.
All closed ERP1/MBF1/XUA1/SFX1 etc. remain frozen. The source asset
universe comes *from existing authenticated original CMA2 inventory*:
NatGas gas CFD (min margin EUR24.74, min 100 units, one fresh spread
11.104942bps); USDX dollar basket CFD (EUR183.84/10 units, spread
4.917823bps); AMD.US equity CFD (EUR7.99/0.1 shares, spread
15.011258bps, USD0.02 minimum fee each side). **These are SOURCE-DATED
contract facts, NOT historical cost distributions.** Cross-asset
co-occurrence of margins EUR216.57 is neither a free-equity certificate
nor financed simultaneous allocation.

`research/mcs1_protocol.json` was fixed before ANY target OHLCV or
forward label was inspected. Three distinct H1 native C# families
(`McsNativeH1Features`) and matching Python parity expressions:

1. NatGas: 12–19 UTC working-day completed H1 evaluation,
   four-hour gas exhaustion with a quiet two-hour USDX backdrop,
   H1 volume and contrary latest-hour gas impulse; 1H predicted
   holding, matched same-event 4H trend benchmark.
2. USDX: 12–19 UTC completed H1, two-hour overlap directional
   drift with aligned latest H1 volume and price; 1H predicted
   holding, matched same-event long-only USDX index benchmark.
3. AMD.US: 15–19 UTC completed US cash-session H1, 80bps
   prior-hour extreme plus 1.25x trailing four-hour tick activity;
   1H mean-reversion prediction, matched same-event H1 momentum.

These are not the old XUA1 energy H1 news/crypto/GBPJPY strategies
and not the old SFX1 four JPY/NZD fixed-clock models.
At most **105 preregistered decision clocks per nominal 5-day trading
week** (40 NatGas + 40 USDX + 25 AMD.US) exist BEFORE bar gaps
and signal filters. HARD21 requires >=20% of nominal clocks to
be admitted, *funded and closed*, assuming each slot can be used once
and concurrency permits; 20% is a simple mathematical feasibility
threshold, **NOT a forecast or achieved frequency**. The objective
is system-wide, not per symbol.

The planned separate source phase has exactly 324 original-account
read-only requests: 3 account/asset/universe headers, 6 as-of
contract/margin requests, 159 weekly H1 bars (3 x 53 including five
newer chronological unscored days) and 156 historical BID/ASK sides at
2 fixed development clocks/week x 13 weeks x 3 instruments.
Raw request/response must be independently authenticated, sealed
using existing custody, and actual native signs compared against
Python BEFORE future returns are accessed. No blind grid or retuning
after results.

Research computation `research/mcs1_economics.py` is implemented,
but **has not been run with genuine MCS1 market data**. Its outputs
will separate source frequency (non-financed), BRUT close-only log
returns, matched gross benchmark, current-contract-only median/p90
observed development spread, separate modeled slippage, minimum
AMD commission and 0.5/1bps explicitly modeled route uncertainty;
no perfect quote sample may be assumed. Minimum 8 distinct quote
dates/sample, otherwise conditional NET is null while genuine
gross exploration is allowed. It uses
`research/prospective_joint_stat_gate.py` to test two separate
familywise-adjusted HAC adverse endpoints: vs cash **and** vs
matched benchmark. 26/13/13 prior weeks are globally exposed; the
last 5 days, if ever collected, stay unscored as genuine later
chronological source. No actual broker fills, finance or new
independent confirmation is available.

The Cloud-compatible SINGLE native Mxm.Core feature module is
not plugged into funded `OpportunityOrchestrator` because zero
MCS1 candidates have authentic positive predictive and NET proof.
No second financial ledger was built. The existing
`NativeBrokerContractCosts`, `NativeFundedLedger`, EUR300 capital,
HARD21, DD30 and owner order/Cloud prohibitions are unchanged.

**Current result:** H1 instruments economically selected and
engineering/causal regression tested; actual source H1 data 0 new,
model BRUT not evaluated, central/adverse NET null, funded EUR NET
null, admissible broker roundtrips 0, independent confirmation false.
The workflow security refusal prevents claiming execution.

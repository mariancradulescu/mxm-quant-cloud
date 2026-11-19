# NPI1 — original immutable source integrated C# economic readback (2026-11-19)

## Evidence and original custody
- OWNER MVO1 decision in Issue #393 remains in force: SPE1/MVO1/OEI1/OEI1-A1/LPM1 remain closed and their research/results untouched.
- NEW NPI1 protocol frozen at commit `e26c4584eeac2cfd910d970a0e4df95d2722fe5d` before NPI1 implementation or this readback.
- Implementation merged PR #397, merge commit `832da02696043a25b79e3fa56f18a61fb0784a7f`.
- NPI1 CI original native verification #44494626686 **SUCCESS**.
- Exactly one original NPI1 Actions run [#44494972731](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44494972731): verify **SUCCESS**; protected original-source native-financial job **SUCCESS**.
- Original publicly archived artifact **14514233621**, `npi1-original-native-financial-conditional-public`. ZIP contains `receipt.json` and `native-economic.json`.
- Immutable input source: original OEI1 run #44247979857, ciphertext SHA-256 `c28a69c2ee738f209cfd025a7424377629c9ac59f695c2b87422c2577c4d4c86`, decrypted original tape SHA-256 `32f3401cfede314a7a3b110c0636166a2680b2f440e3428dd5c1b70f12acaf1b`. The source bridge verified both against original source receipt under installed original custody; no source re-collection or closed economic rerun.
- `native-economic.json` SHA-256 **550483195f42d274720c145adea5d17d205c9beee12df1b211ce06b5caa40e73**, verified equal to `receipt.json.NativeReportSha256` by independent readback in the Director environment; full independent Architect-Coordinator source/event review still pending.
- Valid authenticated sampled original as-of bid/ask minute marks (both sides at or before timestamp and <=30 seconds old): EURUSD **7,140**, ETHUSD **7,141**, SpotBrent **7,141**, US500 **7,140**; total **28,562** observations, 60 original source-recorded days per symbol. Original source intentionally covers only 13:30–15:30 UTC daily sample window. Nothing certifies whole broker session.
- **Zero broker requests, zero LIVE/DEMO orders, Cloud OFF, no new service**.

## Financial source-bound C# study results

All are separate EUR300 *conditional counterfactual model* books, not combined or actual broker funded accounts. Core code uses `NativeFundedSession.DecideResearch` with `OpportunityOrchestrator`, original `NativeBrokerContractCosts` current-as-observed conditional quote adapter, `NativeFundedLedger` MARK/REQUEST_OPEN/OPEN_FILL/REQUEST_CLOSE/CLOSE_FILL and `NativeCausalExitResearch.AssessLifecycle`. Model fills use actual as-of original quotes **at later minute observations**, not actual original broker execution receipts. Historical cost stability and financing are not attested. Price sampled at one-minute marks does not bound continuous intraminute floating risk.

| Distinct policy | Predecision proposals | Selected/open model fills | Closed complete model trips | Unresolved held/pending | Conditional closed quoted NET before unverified financing | Modeled final cash | Modeled sampled max DD (NOT continuous) |
|---|---:|---:|---:|---:|---:|---:|---:|
| FIRST_ADMISSIBLE | 361 | 80 | 79 | 1 / 1 | **−10.077144069674981 EUR** | 289.922855930325 EUR | 4.693681% |
| CROSS_MARKET_PERSISTENCE | 62 | 18 | 17 | 1 / 1 | **+1.8164792792117923 EUR** | 301.8164792792118 EUR | 7.619391% |
| MICROPRICE_REJECTION | 663 | 261 | 261 | 0 / 0 | **−32.63420752604892 EUR** | 267.3657924739511 EUR | 12.517457% |

The full EUR300 initial cash is not restarted between study splits in any single book. The figures are **not** realized broker NET or certified adversarial NET. Drawdowns are sampled, include only observations received, and cannot certify OWNER <=30% including continuous floating. The models use historical as-of original quotes, current as-observed (not historically proven) tariff/margin, adverse conditional slippage; unmatched funding periods remain UNKNOWN. No independent holdout.

### Stage sums (completed round trips booked by exit clock; all calendar globally exposed)
- FIRST: development 79 trades **−10.077144 EUR**; calibration 0; exposed final evaluation 0. 1 unresolved held/requested-close state prevents claiming terminal complete settlement.
- CROSS: development 17 trades **+1.816479 EUR** (all in 2026-W34); calibration 0; exposed final evaluation 0. **NOT** evidence of a reproducible positive predictor: one unresolved held/requested-close state blocks later admissions and terminal equity includes unrealized modeled marks.
- REJECT: development 111 trades **−21.315521 EUR**; calibration 74 trades **−7.910393 EUR**; exposed final evaluation 76 trades **−3.408294 EUR**. This directly rejects economic promotion of the exact predeclared mean-repair mechanism; it loses conditional cash even before unknown financing.
- No simple subtraction between cross-policy outcomes is a valid matched incremental return because policies have different causal entry and exit paths. CASH baseline is 300 EUR, each separate policy starts with 300 EUR.

### Source continuity versus settlement
- FIRST: 5 held-gap observations, 5 cross-day source-window boundaries **with official session cause unknown**, 3 observed re-entry price discontinuities, and 4,165 status checks for a pending execution with unknown outcome.
- CROSS: 2 gap observations, 2 cross-day source-window boundaries **session cause unknown**, 1 observed discontinuity, 6,545 pending-execution-unknown checks.
- REJECT: 17 gap observations, 17 cross-day source-window boundaries **session cause unknown**, 14 observed price discontinuities, 0 final pending positions. This does not certify full intrabar risk/funding.
- The 4,165 / 6,545 pending counts are **clock observations of one unresolved pending state**, not 4,165 or 6,545 separate broker failures or rejected orders.
- The model intentionally does not close/release margin on absence of observations, nor treats next day's quote as a known fill if an unobserved interval exceeded the frozen two-minute pending-response bound. Thus a persistent unresolved intent can freeze later admissions. This is a source/evidence limitation, not necessarily an exchange closure or broker failure.
- The recorded cross-day intervals can represent genuine broker session closure, source coverage ending at 15:30, or unavailable archived data; the source cannot distinguish these independently. A price discontinuity at re-observation is descriptive and does not prove when an intragap price move occurred.

### Certification and next economic decision
- `RealizedBrokerNetEur=null`, `CertifiedAdverseNetEur=null`, `CertifiedContinuousFloatingDrawdown=null`, `CertifiedSystemicHard21=false`, original broker fill evidence false, historical tariffs/funding continuity false, source session schedule uncertified. **No alpha promotion**.
- Dominant demonstrated dual bottleneck: (1) the only continuously scorable fully completed REJECT mechanism loses conditional cash in every split; (2) the apparently positive CROSS book is censored after week W34 by one unresolved persistent closing intent, so cross-week durability and incremental advantage are **unscored**.
- Remediation for future product: source-bound order-status and historical funding/FX/margin evidence for the specific unresolved intent and each complete trade, genuine official session schedule, wall-clock stale-observation protective logic that does not invent exits, and independent intrahold floating risk coverage; do not retune, remove gaps, fabricate fills or reuse the NPI1 exposed outcome to select future trades.
- Architect-Coordinator via Issue #393 must independently verify artifact bytes, original source/custody SHA, event-chain and ledger accounting, legal volume, prospective features, benchmark comparison, cost/funding assumptions, gap handling and actual cBot Cloud observation adapter parity before any OWNER decision. This readback is a DIRECTOR analysis, not that independent audit.

Original run result is final and immutable; no NPI1 rerun or post-result retuning is authorized by this readback.

# IVP1 — authentic original VIX-before-US500 economic-information source gate (2026-11-17)

**Exact DIRECTOR source-only verdict, for OWNER and independent AUDITOR:** `IVP1_PRESOURCE_STOP_NO_OUTCOME_SCORING`.

This study was STOPPED **before any forward US500 return, trade P&L, cash-vs-VIX gain, or C# EUR300 financed model was evaluated**, because the exact prospective source/identification prerequisites failed. This is neither a negative EUR return nor a universal verdict against implied volatility; it is a valid and compulsory economic information feasibility stop. Never call it loss-making or profitable. Do NOT lower a gate, re-time a trade, re-select a VIX symbol, score postpilot profits, replay the exact experiment or start a renamed IVP2 using the exposed pilot.

## 1. Frozen source-blind research ordering

1. New options-implied-volatility source, **not target US500 OHLCV**, proposed as a rationally distinct information channel. Pepperstone public lists `VIX` CFD and official underlying VIX is based on option-implied expected volatility. The authenticated prior 5,339-symbol Pepperstone roster original publicly included `VIX` but did NOT attest broker account enabled status; original IVP1 preflight verified it. The CFD may not track spot VIX or underlying options customer order flow identically.
2. Original **source- and outcome-blind frozen protocol** PR [#345](https://github.com/mariancradulescu/mxm-quant-cloud/pull/345), merge `93c0c3a94c20e273b3022e0d50ff0b569b468853`, file [research/IVP1_VIX_US500_TEMPORAL_OPTIONS_RISK_PRESOURCE_20261117.md](../research/IVP1_VIX_US500_TEMPORAL_OPTIONS_RISK_PRESOURCE_20261117.md), original SHA-256 `502c1480f4b09918a037104a0709a1631b25ca5f54b9ad8077db9c9726dfc4ec`.
3. Separate source-blind **target-own prior-time-aligned information ablation**, PR [#347](https://github.com/mariancradulescu/mxm-quant-cloud/pull/347), merge `6fc8f727747c61af23172ee291d4faec5e15a04d`, file [research/IVP1_PRESOURCE_A1_ALIGNED_TARGET_PRICE_HISTORY_20261117.md](../research/IVP1_PRESOURCE_A1_ALIGNED_TARGET_PRICE_HISTORY_20261117.md), original SHA-256 `a89cbcfcdf419d9622554cacd8a1d6b0b86e0d4e214c26bd19082c7de3592de3`. This upgrade was made BEFORE any IVP1 original market-data collection or outcome exposure.
4. Only afterward PR [#346](https://github.com/mariancradulescu/mxm-quant-cloud/pull/346) source-only pilot code/synthetic tests/protected workflow merged, `49eb4ee3917d9916342bff498ea21a23c3f8bf5a`. Source code and tests are unchanged after original result. Secretless validation and post-merge CI passed. No closed prior study was rerun.
5. One OWNER/main one-file original source trigger `ops/ivp1-original-pilot-once.txt` committed **`04a93a71986e8da297f6145579576dbf26a6e790`**, exact subject `OWNER_IVP1_OPTIONS_VOL_US500_SOURCE_PILOT_ONCE`, actor `mariancradulescu`. First attempt original [Actions #44020275250](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/44020275250) **SUCCESS**, including `validate-source-only`, `recipient-from-existing-custody`, and `original-vix-broker-source-no-economic-outcome`. All jobs SUCCESS. No broker trading/Cloud jobs.

## 2. Original protected custody — independently checked

- Original **encrypted raw request/response protobuf** artifact ID `14301350641`, ZIP SHA-256 `383ca75b2be320248ae2e640318305a983274c71b3dc2fd9c19f0f235e99cdbf`. Enclosed unchanged encrypted source `ivp1-original-pilot-source.v2.enc` SHA-256 `e40fd328c9633942fe82bc13250c12b4f80397fca0ba3bc39c0b6ec04d6b6700`. Original plaintext SHA-256 commitment `de0c30f18dd34301244be6056898adeee6fe100a225c1beed7701e9a91d96b82`; plaintext encrypted and not publicly exported.
- Original **source-only public aggregate JSON** artifact ID `14300842395`, ZIP SHA-256 `8a7d19125bcad36bf068e3d107cf617e952d89ec42db47e65b65df0658c1d15a`; internal `ivp1-original-pilot-public.json` SHA-256 `8937ca2051b21dd6f6988d9adc53c6ef9fa3f9e1ae90388c4886a21c9815960f`. Both ZIPs and enclosed original byte SHA256 were independently calculated from the downloaded original GitHub Actions artifacts.
- Original account is the verified bound Pepperstone EUR account, all `707` explicitly allowlisted read-only source requests including VIX/US500 completed M5, US500 and EURUSD historical BID/ASK and current legal broker contract/margins. No orders or Cloud; no original payoff labeling.

## 3. Frozen calendar and exact SOURCE results

Fixed 10 pilot weekdays, 2026-11-02 through 2026-11-13 (two five-day chronological halves), five fixed clocks UTC 14:00 / 15:00 / 16:00 / 17:00 / 18:00; **50/50** source requests made without selecting dates by profitability. Original full calendar would have been 325 events over 13 weeks, 25 per week; **no** prior 275 full-study clocks were collected after the source gate failure.

**Strict non-overlap to reject simultaneous-correlation language**: VIX M5 moves are completed T−35→T−15; US500 recent own moves T−15→T. Pre-source A1 requires US500's **same earlier T−35→T−15** move as a mandatory competing direction, not a transformed substitute. Three nonzero predecision predictors must be compared before claiming VIX adds actionable information beyond target own price; the pilot did NOT evaluate their subsequent returns.

| Prespecified pilot gate | Authentic original measurement | Pass requirement | Verdict |
|---|---:|---:|---|
| Original VIX, US500, EURUSD enabled, US500 current legal min 0.1 CFD and both directional margins <=EUR210 | US500 EUR33.72 BUY / EUR33.72 SELL; original account/quotes permitted | all metadata & finance valid | **PASS** |
| Both VIX & US500 strictly completed source bar sets at scheduled T | **44 / 50**; first five days **24 / 25**, last five days **20 / 25** | >=45/50 and >=21/25 each | **FAIL** |
| Original US500+EURUSD fresh BID/ASK all THREE entry/middle/exit marks | **50/50** clocks, **150 US500** and **150 EURUSD** valid pairs | >=45/50 and >=21/25 each | PASS |
| VIX vs US500 recent direction mismatch, and all three nonzero | **15 mismatches**, **40** three-way nonzero | >=10 and >=40 | PASS |
| **VIX vs US500 earlier same-20m-window direction mismatch** | only **4 mismatches** | **>=8** | **FAIL** |
| Predecision US500 15m absolute move versus actual original spread + current minimum fee + adverse assumed 2bps friction | absolute 15m median **10.113197bps**; spread median **0.528643bps**; broker min commission ~0bps; extra model slippage 2bps | prior amplitude > indicative round-trip cost | PASS |

Source-reconstruction counts: VIX completed-bar sets 44, missing 6; US500 completed-bar sets 50, missing zero; all EURUSD quote sides and US500 quote sides source-reconstructible at all 150 distinct mark clocks. **No economic outcomes** were scored, so source completeness and occasional sign agreement have NOT been converted into profits.

**Interpretation:** For the exact predeclared predictor, the observed VIX signal differed from US500's own same-earlier-window direction on only **4** source-only opportunities. Therefore the pilot offers insufficient evidence that this options-volatility-linked CFD quote adds a distinct directional decision beyond prior target index pricing in the stipulated calendar. An observed gap from earlier own pricing would still not prove true economic prediction without returns. This source-prerequisite failure says nothing about untested VIX states, later windows, other assets, truly independent option flow or other conditional mechanisms. Do not move thresholds or times on this exposed panel.

## 4. Final exact status and programme constraints

**`IVP1_PRESOURCE_STOP_NO_OUTCOME_SCORING`**: 2/5 original predeclared source gates failed (bar completeness and genuinely new directional information). A complete EUR300 C# economic test was **not** and **must not be** executed for this exact hypothesis. `grossEur=null`, `centralNetEur=null`, `adverseNetEur=null`, `stressNetEur=null`, `fundedCompletedTrades=0 original executions`; zero modeled trades is NOT an observed profitable CASH strategy. No actual or modeled broker fills. There is no basis to promote, reverse, resample or label this family as profitable or loss-making.

OWNER final objectives continue without any concession: one capital pool EUR300 no reset, systemic HARD21 >=21 financed complete trades per eligible week, targeted adverse floating DD <=30% including missing intratick unknown, independent chronological confirmation and eventual native C# cTrader Cloud Linux parity. `MarketData.GetBars(TimeFrame.Minute5, symbolName)` is documented Cloud-compatible, but account-specific source timing, history parity and execution-grade fills are NOT certified by this pilot. No LIVE/DEMO orders, Cloud activation or permanent external services. Subsequent genuinely distinct causal research may proceed prospectively but NEVER use this original IVP1 pilot to retune this exact direction.

**Custody directive:** retain original sealed source and public ZIP/JSON bytes, source protocol and A1 hash, workflow original IDs. This final report only documents their existing outcome; it does not rerun economic studies or mutate source.

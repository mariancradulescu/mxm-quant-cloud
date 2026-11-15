# GCR1 — recuperare originală, raport economic și verdict OWNER, 2026-11-15

**Clasificare:** developmental, globally exposed, original Pepperstone EUR account,
read-only source, historical original BID/ASK, **current-contract cost models**,
NOT broker actual fills / native EUR300 funded portfolio.

**Authority:** docs/OWNER_SPEC.md OWNER v2.0; 2026-11-15 OWNER GCR1
decision, mandatory A1 / A2 supplements and justified F1/F2 source-readback
diagnostics. The exact ORIGINAL GCR1 signal and parameters are unchanged.
NO retuning, inverse-side recovery, selected dates, modified source, new order,
LIVE/DEMO transaction or Cloud activation.

## 1. Immutable custody and execution reconciliation

- Original GCR1 source run:
  [#43723906148](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43723906148)
  — successful source-only capture, **4,428** verified postauthentication
  Pepperstone read-only requests, 260 weekdays / 780 fixed UTC decision
  clocks, source encrypted before any GCR1 financial scoring.
- Original encrypted source artifact **#14165348903**.
  Its uncompressed ciphertext SHA256
  `f0ace5ff7e260025ebc61f5072a5d7ca89410253972935089ebe143621791d6e`.
- Original public source metadata artifact **#14165079629**.
  ORIGINAL raw public bytes SHA256
  `4b2985a6639b0f1ba66dc293eb159a914e582c0d20886cfbf50e0bebc0426120`;
  exact trailing literal backslash+n parser defect recovered F1
  **without modifying or overwriting the original artifact**.
- Reused ORIGINAL **BDP1** source run **#41724643418**, original sealed artifact
  **#13273950911**, ciphertext SHA256
  `e47ba7204ca7e07e7bb523ede8a8171f49b216cad09914142ed548839660a370`.
  Original BDP1 source account/protobuf audit succeeded. Reused **70,550**
  native XAUUSD M5 bars and **74,177** AUDUSD M5 bars; neither source
  predictor nor closed BDP1 economic policy was rerun.
- F1 source-join error run #43725959198 failed closed BEFORE financial
  scoring; once-per-day causal data join corrected ONLY in PR #306.
- Original-source-only F2 protected readback run
  [#43732374056](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43732374056):
  **SUCCESS**, original-source-independent protected readback,
  **zero additional broker requests**.
- F2 encrypted composite source artifact **#14168577551**,
  ciphertext SHA256
  `d36460bbb7600f2b3d565b883914733e0dfce98746cd1e91062e0af71e7a33f9`,
  plaintext provenance digest
  `21237d0ed4597103f5398a8d16da49f23c44b13225530d0d749e3f206d621cf8`.
- Original public economic artifact **#14168293487** (GitHub artifact ZIP
  digest SHA256
  `81c964c667bc5bc50cb1cf44f36940c126b062363f8174bde83d4f68f2f8b5a2`).
  Full extracted original JSON SHA256
  `b10519c7c4510d75b4ee86609e6402a9767df3d3f9c4da5efad6379df5cf45b0`.
  Never replace this receipt with a revised verdict.
- Fixed protocol hash:
  initial `ede728241050fdec886c0733909cebdb6a0504092a94e554c50f262f131a465a`;
  A1 `319b94d66673d1cc72c05d2c8d7535cd76df1b2fb936e76ffac6464fca3ea03d`;
  A2 `b7403fa721f5d5a3025b09dd69e851df29820b0165c02affed3371e3fbf3517e`.

## 2. Fixed 780-clock population and financial source completeness

- Exact scheduled: 780 clocks (08:00, 12:00, 16:00 UTC) over 260 weekdays;
  **780** retained, no future-price-based selection.
- Combined original intents: **136 BUY**, **107 SELL**, **522 fixed causal
  ABSTAIN**, **15 unknown predecision source**. Total **243** signaled
  directions BEFORE financial availability is known.
- Metal-state census: 136 Copper-positive/Gold-negative, 107
  Copper-negative/Gold-positive, 521 same-sign, 1 zero,
  15 missing metal decisions.
- Financial quote/FX panel: **763** nominal clocks priced with current-term
  source, **17** financial source UNKNOWN; COMMON all-policy
  complete-case panel **755**, unknown **25**. These 25 are *not*
  zero-return cash and cannot be silently removed from coverage
  denominators or claimed as loses/wins.
- Common complete-case: **372/390** clocks in weeks 1–26, **383/390**
  in weeks 27–52. The distinct audit cohorts remain development
  chronologies, NOT independent confirmation.
- Combined original active entries **238** on common financial panel;
  **not** 238 funded native roundtrips. Five causal signal intents did
  not enter the complete-common sample.
- No native common-book financing, no observed complete intraholding
  liquidation equity and no broker actual fills are provided.

## 3. Economic outcomes, shared common-calendar comparison

All entries below are **conditional model EUR NET**, after observed
two-sided original price quotations and **current contract tariff,
EUR conversion, commission, and central/adverse assumed slippage**.
Not certified historical executions. Policies each use the identical
**755 common-scored scheduled clocks**. Flat abstention has genuine
cash NET 0; missing financial or predecision source is NEVER converted
into cash.

| Fixed policy | Central modeled NET EUR | Adverse modeled NET EUR |
|---|---:|---:|
| **GCR1 original combined** | **−20.152587** | **−41.525002** |
| Copper-only causal side | −71.363258 | −139.369945 |
| Inverse Gold-only causal side | −60.089047 | −128.186828 |
| AUDUSD own completed-momentum | −87.122472 | −154.678500 |
| Constant LONG | −35.186033 | −103.283814 |
| Constant SHORT | −99.563037 | −167.660818 |
| Cash / no trade | 0 | 0 |

GCR1 versus Copper-only: incremental adverse **+97.844943 EUR**;
versus inverse Gold-only: **+86.661826 EUR**;
versus own AUD momentum: **+113.153498 EUR**;
versus constant LONG **+61.758812 EUR** and SHORT **+126.135816 EUR**;
but versus cash: **−41.525002 EUR**, so **no positive absolute
adverse economic edge**. Same-sign metal calendar cells make combined
abstain; avoidance of costly single-metal bets accounts for material
relative difference and does NOT identify a causal contribution of
both metal factors.

### Frozen original 26/26 chronological halves

| Chronology | Matched clocks | Active combined entries | Central NET EUR | Adverse NET EUR |
|---|---:|---:|---:|---:|
| First 26 weeks | 372/390 | 129 | +1.540176 | −9.769823 |
| Last 26 weeks | 383/390 | 109 | −21.692764 | −31.755179 |
| **All 52 weeks** | **755/780** | **238** | **−20.152587** | **−41.525002** |

Conditional combined adverse mean per active entry: **−0.174475 EUR**;
**96 positive / 142 negative** modelled marks. Central mean per active
entry **−0.084675 EUR**, **102 positive / 136 negative**.
No native funding or actual broker order was used to derive these counts.

**HARD21 arithmetic:** maximum **10 GCR1 original causal signals in
any of 52 calendar weeks**; zero weeks with 21 GCR1 signals, even
before funding. This is NOT proof that the SINGLE eventual diversified
system cannot meet HARD21, but the GCR1 configuration alone cannot
satisfy it.

## 4. Two distinct verdict axes: immutable source vs OWNER economic admission

**Original public receipt decision field MUST remain intact:**
`INCONCLUSIVE_FULL_CALENDAR_COVERAGE_CONDITIONAL_NET_DISCLOSED`.
It correctly means 25/780 all-policy comparison clocks remain incomplete;
we do NOT assert a negative financial outcome for those 25.

**OWNER economic decision on genuinely evaluated matched clocks:**
`REJECT_EXACT_GCR1_FOR_PORTFOLIO_PROMOTION_NEGATIVE_ADVERSE_NET_BOTH_HALVES`.
The original GCR1 rule lost NET EUR in both adverse halves (and all-year
central), despite outperforming the weaker active controls. It did not
outperform cash in adverse terms and failed the precommitted essential
absolute economic test. These two verdicts are logically compatible:
incomplete full-calendar financial certification, plus strong
nonqualification evidence on the observed common population.

Never invert, retune, add filters, select Copper/Gold favorable cells,
rescore a closed hypothesis or call exposed chronology independent.
The exact GCR1 study is conserved and **not promoted**. A subsequent
new hypothesis must be a genuinely distinct advance-frozen mechanism,
not a way to rescue this one.

## 5. Unproven qualifying requirements

- Actual broker NET EUR: **UNKNOWN**, not the modeled totals above.
- Native shared EUR300 ledger financing, close-before-open at
  12:05/16:05, partial close, free margin, contract lot,
  side-specific margin: **NOT executed/certified in this receipt**.
- Floating equity throughout the complete 4h interval, true maximum
  portfolio drawdown <=30% incl. floating and costs: **NOT certified**.
- HARD21 systemically (21 truly funded complete roundtrips each
  objectively eligible week): **NOT certified**.
- Twelve months of independent, as-yet-unexposed evidence: **NOT
  established**; all 52 calendar weeks globally research-exposed.
- No LIVE/DEMO orders, no Cloud activation, no OAuth refresh, no external
  service; these restrictions continue.

## 6. OWNER decision after GCR1

Transition future discovery emphasis to a prospective, systematic
OHLCV/price-structure and regime learning framework. See the separate
OWNER methodology specification; do not use one plausible commodity
relationship as a substitute for genuine predictiveness or robust
executable EUR after shared-capital costs and risk.

# OWNER B–E: BCF1 protected source gate and verified EUR300 necessary-capacity result — 2026-11-06

**Authority**: `docs/OWNER_SPEC.md` OWNER v2.0. Single continuous prospective EUR300, maximum 30% global drawdown, system HARD21 only, native C# financial authority. NO LIVE/DEMO orders and no Cloud.

## Genuine execution attempted; not represented as economic research success

BCF1 prospective fixed protocol `research/bcf1_protocol.json` and exact one-file protected intent were merged as PR #108 and #109. The genuine [GitHub Actions #42172375939](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/42172375939) has two attempts:

- Attempt 1: `verify=SUCCESS`, `custody_recipient=SUCCESS`, `bcf1_bond_curve_source_only=FAILURE`.
- One OWNER-authorized failed-job retry, **same unchanged protocol and code**, attempt 2: `bcf1_bond_curve_source_only=FAILURE` at the same boundary.
- Both attempts logged `APPLICATION_AUTH_VERIFIED`, followed immediately by `BCF1_FAILED_CLOSED_NO_SENSITIVE_DETAIL`, with **no** `ACCESS_TOKEN_EXPLICIT_VIEW_VERIFIED`. Thus failure was during or before confirmation of account-list/token scope, **before original account authentication, historical H1, symbol contracts or BID/ASK quote capture**.
- Exact underlying cause is **unconfirmed**. Possible causes include invalid/expired access token, permission-scope/account-list rejection or a transport/server response error. The safe logs distinguish none of them; do not fabricate a token-expiry certificate or print protected reply payloads.
- The existing installed custody key was verified, but **no new BCF1 encrypted source artifact was created or read back**. Original 52-week historical prices remain globally exposed; the reserved 2026-11-02–2026-11-06 chronological window was **not captured**. The existence of new confirmation observations is **not established**.
- No predictor, model, signed return, selection outcome, finance conversion or economic scenario was scored. No closed model was reopened, no orders were sent, Cloud was not activated. BCF1 is `SOURCE_ONLY_AUTH_BLOCKED_NO_RESULTS`, not `CLOSED_EXACT_NEGATIVE`.
- Do not repeatedly relaunch BCF1 with the same unverified credentials. This condition requires a bounded, authorized SCOPE_VIEW authentication correction/verification; cannot be solved by choosing a different trading model or retrospectively substituting historical data.

## Executed read-only verification of existing REAL Pepperstone account evidence

Unlike the blocked BCF1 capture, original independent account inventory run [#41939175379](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41939175379) is authentically preserved: public artifact [13375915761](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41939175379/artifacts/13375915761), exact `full-inventory.public.json` SHA256 `1b15d08fa14bf67239acf31109b1f0f11093df7fe5c1b04fcbf1bff893040c5a`, encrypted source ciphertext SHA256 `3609973af1f6af996d9724742df64f27cbf1ea27821ad2bafcd27ccd93c94992`.

Genuine original account: **5,339 returned symbols; 1,755 visible; 96** category-stratified current-contract probes; **89** genuine min-margin observations; **7** close-only/disabled.

| EUR-equity static single-minimum-volume scenario | Count of 89 authentic margin observations strictly below threshold |
|---|---:|
| Initial EUR300 | 79 |
| Illustrative EUR210 after 30% loss from an unchanged EUR300 peak | 74 |
| Historical EUR200 threshold for comparison | 74 |
| Historical EUR140 stress point | 70 |

The **five** originally probed minimum units that are below EUR300 but not below EUR200: `XAGUSD` EUR232.60, `XAGEUR` EUR232.61, `Coffee` EUR242.20, `US30` EUR237.90 and `HK50-F` EUR277.33. These are **not candidate strategies** and not proof of simultaneous portfolio funding or of affordable costs; 79/89 is not 79 funded positions.

For the intended unscored EUR bond-rate curve source gate, **old** observed minimum margins were `EUBobl-F` EUR22.71 and `EUBund-F` EUR24.57 (sum EUR47.28), only historic current-term snapshots, **not freshly reverified BCF1**. Actual duration-risk, contract rolls, expiration, per-fill BID/ASK, financing and volume constraints remain unknown.

Original spread preflight CSP1 exposed just **19 valid causal BID/ASK pairs of 36** predeclared observations, 17 unknown/invalid; it is not a complete historical cost model for this larger universe.

## Precise six-level HARD21 separation

1. Technical observable opportunities: GEP1 exposed **2,398** over 52 weeks, including non-promoted groups; no BCF1 observation outcomes.
2. Causal mechanism signals: GEP1 counts were source-only, **not** financially qualified.
3. Predictive and positive adverse-NET candidates: **zero** qualified GEP1; BCF1 did not score anything.
4. Allocations in **one** native EUR300 C# ledger: **zero** accepted from GEP1 or BCF1.
5. Modeled physical units, simultaneous positions, mark-to-market paths and fully closed funded round trips: **none** qualified from either new programme.
6. Eligible HARD21 weeks with >=21 **financed closed** round trips and <=30% continuous global drawdown: **not demonstrated**.

Historical proxy bps must never be translated into broker-certified EUR NET. The 30% risk rule is equity-peak based; the EUR210 scenario is an illustrative static point, not the path-wise stop threshold after later profits/losses.

## Next admissible decision

The existing F2 `prospective_economic_futility` function was added and regression tested **only for future prospectively frozen studies**: actual signed weekly adverse NET and same-clock benchmark series, preregistered multiplicity, fixed three-lag HAC / conservative variance, and an upper plausible-benefit bound before selection. A positive upper bound is NOT evidence of an edge, and missing cost/variance rejects scoring as uninformative. Frozen GEP1 is unchanged.

No new valid hypothesis-source pair can be scored while BCF1 account-view authentication is blocked; no alternate observable independent confirmation reservoir was collected. Keep BCF1 unscored; do not call its time window independent. On a genuinely restored read-only account, verify `SCOPE_VIEW` and exact bound Pepperstone EUR account **before** any fixed source request, use the existing custody, and retain the predeclared economic-futility gate. Do not change the locked GEP1, BCF1 protocol, or F0/F1 native ledger.

# SRO1 — U.S. sector-rotation index and ETF basket response: original-archive reuse

OWNER v2.0, 2026-11-14; SOURCE REUSE / ECONOMICS before implementation.
This is a *new mechanism* distinct from closed ECA1 (index versus **own**
ETF opening disagreement), RNE1 (scheduled gas-storage repricing),
VIA1 (quote intensity) and QPI1 (quote event descriptors). No closed
model is rerun, retuned or inverted. This protocol is FROZEN in its
own Git commit BEFORE SRO1 source decryption, historical scoring,
outcome-derived code changes or price extraction. Retain the full
globally exposed 2026 calendar as DEVELOPMENT, never independence.

## Rationale and alternatives, written before examining SRO1 outcomes

1. Retune the ECA1 ETF-index opposite-first-bar signal, switch its
   direction/horizon or recover its negative output: **REJECT**.
2. More NatGas announcement barriers after RNV1: an opportunistic
   rework of the unqualified exact RNE1: **REJECT**.
3. **SELECT a U.S. sector-rotation information mechanism.** At the
   09:30 NY cash opening, a technology-heavy index and the broad
   U.S. equity index may respond in *opposite directions* to
   stock/sector-specific information, sector ETF flows and rate
   repricing. This explicit breadth-disagreement event implies
   reallocation rather than a uniform market beta shock.
   There are TWO prior-economic alternatives with different
   hypothesized frictions, both precommitted and scored without
   selecting a favorable winner:
   - A: on existing index CFDs `NAS100` / `US500`, institutional
     **sector rotation continuation** from index-futures discovery:
     long the up-first-bar index and short the down-first-bar index,
     equal notional per leg.
   - B: on new original-account ETFs `QQQ.US` / `SPY.US`,
     opening-auction ETF basket imbalance and dealer hedging can
     cause **relative ETF auction-price reversion**: short the
     up-first-bar ETF and long the down-first-bar ETF, equal
     notional per leg. This is ETF-versus-ETF, NOT own-ETF versus
     its index as in ECA1. It is admitted as a separate
     *hypothesis*, not an execution recommendation.
   Alternatives that can invalidate both: genuine persistent
   information may drive ETF *continuation*, cash auction
   prints are not actionable at sampled bar opens, index CFD
   basis dislocates, or combined BID/ASK / commission / slippage
   destroys all gross information. Outcome cannot decide which
   of A/B is called successful after observing returns.

## Exact precommitted original source and no redundant broker calls

Reuse *only* existing ECA1 ORIGINAL encrypted broker source from
read-only Pepperstone EUR Actions run `43498785771`,
artifact `14073147873`, name
`eca1-original-encrypted-source`, sealed
`eca1-original-protected.v2.enc`.
Verify original ciphertext SHA256
`68b45ba2cc4a85bed53617a612384da5115d479f5fedf0abc7eec24f29653aa3`
and original unsealed plaintext SHA256
`e1f6a1c89b5617a1bbf9261c3a911e24aa3e602737fa45b0b35ec49f03bc33c8`.
Use only existing installed custody key in `mxm-r3-custody-v1`
and `unseal_new(...,"43498785771")`, never output original
private prices, account details or original raw proto.
Validate original ECA1 public artifact `14073486785`
JSON SHA256 `22d008a84e8781dbf1f6710cfc5131a3062676675fe66102b7e4ca77850e0b07`
and all immutable ECA1 source statuses.
**NO new authenticated broker requests**, zero changed original
source, zero orders, zero Cloud trading or OAuth.

## Exact economic scoring, 26 fixed historical weeks

Calendar: ALL 26 full Monday-Friday weeks 2026-05-04..2026-10-30,
130 fixed NY weekdays for each of A and B, including holidays
as missing coverage; no dropping unfavorable days.
The original ECA1 tape includes M5 index and ETF trendbar
rows 09:25–10:40 NY for all listed days.
At 09:35 NY only use **completed** 09:30–09:35 bar
Open and Close for BOTH instruments of one pair.
When their log return signs are strictly OPPOSITE and nonzero,
declare an opening sector-reallocation EVENT; otherwise
ABSTAIN. Zero arbitrary magnitude threshold, no
always-on numeric descriptor, and max one event per
market pair/day. The 09:35 signal side is never revised.

At nominal 09:40 entry use 09:40 M5 BAR OPEN,
and at nominal 10:30 fixed exit use 10:30 M5 BAR OPEN.
Require **all consecutive 5-minute OHLC bars from 09:30
to 10:35 close** for evidence continuity. A bar open is
an ex-post **gross price proxy**, NOT as-of
BID/ASK, actual fill, available at that exact second
by the cBot, or historical realizable profit.
No modeled adaptive exit or hindsight price crossing.
At 09:35 event, A long instrument with up first bar and
short instrument with down first bar (two legs).
B trade the reverse in the two ETFs (two legs).
Each leg contributes `side*10000*log(exitOpen/entryOpen)/2`
bps to equal-notional **basket** gross; do not multiply
by fictional contract units, imply a euro amount or
native EUR300 funded trade.
Compare each scored pair/event with 3 static same-clock
reference baskets: long NAS100/QQQ and short US500/SPY,
reverse fixed basket, and CASH. Also display exactly
inverted study policy as a *falsification comparator*
that CANNOT be selected for future promotion from
these now-exposed outcomes.
Split exactly first 13 and last 13 weeks; count:
all 130 scheduled, incomplete source, no-event,
candidate events, incomplete forward M5 bars, paired
gross endpoints, and weeks represented.

Decision before results: if the predeclared primary
direction is ≤0 gross pooled or fails to beat both
constant spread baskets and cash robustly in both
chronological halves, it is **not eligible for expensive
new source collection merely to save it**.
If a primary gross outcome is nontrivially positive and
incremental by these predeclared comparisons in both
halves, a LATER separate frozen cost program may
collect 09:40 and 10:30 original paired BID/ASK+EURUSD
where already ECA1 tape lacks them. Never use existing
ECA1 quote samples as a cherry-picked subset of SRO1
signals; only source-complete same-event comparisons
may support financial claims.

Result labels must be `GROSS_ORIGINAL_M5_PROXY_ONLY`,
no EUR NET, no real fills, no physical original
spread/slippage, no funded native C# ledger, no
risk-floating path, no 12-month validation, no
genuine independent confirmation, no HARD21
certification or portfolio promotion. Both fixed
hypotheses retain verdicts even when one is negative.

Cloud feasibility: first M5 completed bars for indices
and ETFs are accessible through native market subscriptions
when original broker-symbol availability is maintained;
historical actual live close availability and broker
minimum volume/paired-financing remain operational
unknowns. No HTTP, online news, third party API or
permanent Python in final cBot.

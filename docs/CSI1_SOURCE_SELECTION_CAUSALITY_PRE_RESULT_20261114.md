# CSI1 source-selection causality audit — PRE-RESULT observation, 2026-11-14

OWNER v2.0. This file is an independent technical audit raised while the ORIGINAL
CSI1 protected run #43639342108 is still collecting; before any original
source/economic outcome receipt is opened or scored by this auditor.
DO NOT change the CSI1 frozen signal hypothesis or reinterpret closed protocols.

## Specific defect (under original executable code)

In `research/csi1_company_gap_original_eur.py` inside the daily
collection, `rec["bars"][name]` is set to `None` whenever EITHER
(1) morning 09:25..11:10 NY M5 response is unavailable/truncated OR
(2) SAME DAY afternoon 15:50..16:05 response is unavailable/truncated.
But `causal_event(day,original["dates"])` is invoked as a
**09:35** decision and requires `rec["bars"][name]`.
So future 15:50..16:05 **availability** can suppress a valid morning
09:35 causal event, and also suppress later matched quote requests.
The problem occurs even though the direction formula itself only
reads 09:30–09:35 candles.

This is a source/decision timestamp defect, not a reason to reverse, retune,
modify the universe, select a different target, alter costs or ignore missing
observations. It cannot be justified by claiming no future prices were used,
because future SOURCE AVAILABILITY can bias selection.
An earlier same-calendar reference to prior-day late closing bars is causally
valid; the same-day late closing bars are not.

## Immutable original evidence and limits

Keep full original SCOPE_VIEW run #43639342108, all original encrypted
request/reply protobuf and first financial receipt immutable, including any
missingness and quote-request omissions. Do not silently replace/relabel
the original results. No new broker request, no redeployment of orders.
If no valid event survived, classify source/economic evidence insufficient,
not zero economic opportunities in reality.

A purely technical, pre-result frozen F1 **cold readback only** may
reconstruct morning and afternoon original windows *separately* from original
protected protobuf and compare 09:35 causal-event intent on all 260
prespecified evaluation weekdays, independent of afternoon availability.
It must preserve the ORIGINAL four-week past surprise threshold,
fixed AMD/INTC/NAS100, entry 09:40, exits 10:20/11:00, all fees,
benchmarks, no access to PnL to choose corrections, and must count
newly recognized but never-quoted events as **UNKNOWN**.
A cold readback cannot manufacture missing historical BID/ASK and
must not claim a complete financially priced candidate set or
independent validation. If the source lacks enough provenance to
reconstruct, report `SOURCE_SELECTION_NOT_AUDITABLE`.
No automatic re-collection of 56 full weeks; new read-only source data,
if genuinely necessary, must be separately justified and frozen.

This protects an unbiased economic interpretation while reusing
immutable original evidence. It does not turn a negative subset
into a new positive model.

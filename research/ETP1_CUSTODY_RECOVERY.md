# ETP1 — original-custody technical recovery, 12 November 2026

OWNER v2.0 authorizes a bounded technical recovery. **Do not rerun source
collection**. Original Pepperstone execution #43242754053 finished FAILURE
after collecting and sealing its authentic 8-week ETP1 source. This failed
workflow remains immutable and is not relabeled SUCCESS.

Original encrypted artifact: #13956980229, original runner entry
`etp1-native-tape.v2.enc`. Source ZIP SHA256
`42e5876e43fa68b441b924d4341508cde90c301ff25b28963c747bc31c2416ea`;
envelope entry SHA256
`d7e28d2d2a22cd78353fd85c8b2a383b5d43cd6d976448340e6075687b29528b`.
Original envelope v2 binds workflow run ID `43242754053`. Validate
authenticated decryption **inside existing custody** and compute raw tape
SHA256 there, without exposing raw tape or cryptographic private key.

Exact observed failure: `KeyError: 'Receipt'`, line 601 of
`research/native_original_openapi_product_replay.py`. The ETP1 native C#
output has root `Study: ETP1`, `Joint`, `LeaderOnly`, `FollowerOnly`,
`Long`, `Short`, `Fixed90`, `Cash`. The collector read the legacy
nested `Receipt` **before** its profile-specific return. This is a
Python schema adaptation error, not a financial failure. Preserve all
legacy profile `Receipt` behavior.

Recovery rules: (1) verify original envelope SHA and run-binding in
custody; (2) validate original ETP1 source label, exact AUDIT-relevant
universe AAPL.US-24/GOOG.US-24/EURUSD, original bars, quote marks and
economically complete replay; (3) execute ONLY the frozen existing C#
`--native-etp1` from the sealed raw tape once; (4) validate direct
result schema, finite financial results, fixed-control exit reasons,
unresolved positions, and recovered replay SHA; (5) publish a separate
public receipt with original run/artifact/envelope/tape SHA and correction
run provenance. No fee or price imputation, no alternate source, no rerun
of PDR1/AEX1, no new broker requests, no OAuth use, no orders or Cloud.

Economical hypothesis remains frozen at `research/ETP1.md`, original
commit `490e9644d33fe916203ff8f3ab7b279f235e0ab4`.
Dates, instruments, features, entry triggers, forecast, protective
Chandelier/M15 policies, margin, EUR300 common book, funded comparators
and 90-minute *actual* fixed control are unchanged. No retrospective
retuning or independent confirmation claim.

**Fail closed** if source decrypt/identity/hash verification fails,
if any financial book is incomplete, or if the quote/mark path cannot
support its claims. Any failure is a new correction-run result, never
proof of profitability. Evaluate only on exposed development; continue
new economic discovery separately.

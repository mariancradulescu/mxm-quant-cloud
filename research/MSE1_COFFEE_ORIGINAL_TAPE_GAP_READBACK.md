# MSE1 Coffee — immutable original tape custody gap-stage audit

This checks why the **original** 2026-09-02 17:00, 17:10 and
17:15 UTC Coffee quote clocks were missing, despite a separate later
Pepperstone tick diagnostic #43373150241 finding fresh Coffee BID/ASK at
17:15. The published raw tick diagnostic is **new evidence** but does not
replace original evidence.

Decryption and hash attestation are restricted to the preinstalled
`mxm-r3-custody-v1` environment; original public and encrypted artifacts
are downloaded using read-only GitHub Actions token from #43366399346.
No Pepperstone requests, stop/fill simulator, score/rerun or trade orders.

The readback inspects, at predeclared clocks only:
- `RawPairClocks["Coffee"]` — original source paired-BID/ASK stage.
- `RawPairClocks["EURUSD"]` — original EUR conversion paired source.
- `Marks` Coffee and EURUSD — original model-ready mark after all source gates.

It checks ciphertext SHA256, plaintext SHA256, original public receipt SHA,
source label and original total mark count. Public output includes only
source-stage booleans and provenance hashes, never original price values,
account identity or raw protobuf. If a raw Coffee pair is absent, this
cannot distinguish broker historical changes, data retrieval differences
or extraction defects. No stop execution is certified.

One-shot authorized main commit subject:
`OWNER_MSE1_COFFEE_ORIGINAL_TAPE_GAP_READBACK_ONCE`.

All original MSE1/YRC1 results and configurations remain unchanged.

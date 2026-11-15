# GCR1 A2 — bounded postcollection technical readback recovery, 2026-11-15

Authority: docs/OWNER_SPEC.md OWNER v2.0, 2026-11-11
postclosure technical-diagnostic clarification. **Not** a new
GCR1 configuration, retune, repeat broker collection or result-based edit.
Initial GCR1, A1 and A2 protocols remain byte-identical.

Original protected OWNER run:
https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43723906148
Verify, custody and ORIGINAL Pepperstone read-only collection SUCCESS.
Original encrypted source artifact #14165348903 and original source
public artifact #14165079629 are retained and not overwritten.
Original BDP1 run #41724643418 encrypted sealed-source artifact
#13273950911 remains intact.

The readback job failed BEFORE GCR1 financial scoring after successful
BDP1 source audit. Exact parser error: JSONDecodeError: Extra data,
line 25 column 2. Original public-source collector wrote exactly
two escaped trailing characters (backslash + n) after the complete
pretty-printed JSON object instead of a newline byte.

**Outcome-blind F1 formatting recovery:** validate the ORIGINAL public
receipt bytes against only the known exact appended escaped-newline
defect, reconstruct a parser-only view by replacing that terminal
two-character escape with a true newline, and verify the canonical
pretty JSON serialization matches byte for byte otherwise.
Record the original raw SHA256, transformation classification and
source artifact references. Reject any other trailing contents,
modified fields, original ciphertext digest mismatch, source run
binding mismatch or original-account mismatch. NEVER overwrite the
original public metadata or encrypted source evidence.

The new readback-only protected workflow uses a NEW GitHub run id
for the COMPOSITE custody envelope. The old ORIGINAL GCR1 source
ciphertext must be unsealed using ORIGINAL run id 43723906148,
not the new workflow id. Preserve both distinct ids in the final
receipt. The original BDP1 ciphertext is separately unsealed using
its own original 41724643418 run id and audited cryptographically.

Zero new broker requests, no OAuth reauthorization, no trading orders,
no Cloud activation, no new services. Protected readback is gated to
OWNER main and a one-shot commit-title marker, with repository artifact
read permission and the existing custodian environment.

No economic-policy mutation: same 780 calendar clocks, two single-metal
reference signals, original combined signal, entry/exit, quote freshness,
current contract cost, 26/26 exposed halves, shared-capital and hard
unknown/data rules. Publication of GCR1 financial results after recovery
is developmental conditional-current-tariff EUR, not native financed
NET, broker-realized profit or independent confirmation.

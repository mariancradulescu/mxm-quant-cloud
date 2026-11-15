# GCR1 A2 F2 — strictly technical original-input join once per day

OWNER v2.0 and postclosure technical correction; continuation of F1,
no new original broker source or economic policy change.

Original encrypted 4,428-request GCR1 run #43723906148, original
BDP1 run #41724643418, 780 fixed clocks, fees and predictor unchanged.

F1 readback-only protected run
[#43725959198](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/43725959198)
successfully loaded and audited BOTH authentic encrypted sources and
strictly recovered the exact two-character original-public JSON suffix,
then stopped BEFORE GCR1 EUR scoring with
GCR1_A2_DUPLICATE_GOLD_OR_AUD_NEW_SOURCE.

Cause: source provenance guard required Copper-only input in every
hour of a given day, while the hourly iterator itself had already
attached the original AUDUSD and XAUUSD BDP1 M5 bar maps at the first
hour. The second hour found the intentionally attached maps and
misclassified them as an unpermitted new collection.

**Outcome-blind F2**: move Copper-only original-source verification
into a once-per-day pass, attach original verified BDP1 AUDUSD and
XAUUSD M5 maps ONCE per day, then compute the 08/12/16 UTC immutable
intents across all 780 fixed clocks from that same prepared day.
Assert 260 distinct calendar days and 780 immutable clocks. No
source rows, decisions, cohorts, costs, stops, finance or selective
availability filters are changed. Add synthetic regression spanning
three scheduled decisions within the same weekday and duplicate
source guard tests.

Retain F1 original JSON formatting-only reconciliation and distinct
source vs recovery-run original ciphertext identities. Launch only
the preexisting protected source-readback workflow with the same
original GitHub artifacts; zero Pepperstone network calls, no
LIVE/DEMO/Cloud, no independent or financed-performance claim.

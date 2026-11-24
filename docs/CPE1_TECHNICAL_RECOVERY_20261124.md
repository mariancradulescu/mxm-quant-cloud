# CPE1 technical recovery

## Original attempt

[Actions run 45334211971](https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/45334211971) remains `CPE1_ORIGINAL_ATTEMPT_1_TIMEOUT_NO_ECONOMIC_VERDICT`. Its head was `cf6d830ee8c8c9866332af3cd96ac9f7ac22987d`. Verification, source recovery and compilation completed. The Python subprocess timed out after 8,400 seconds in Mxm.Replay. GitHub lists zero artifacts for attempt 1.

The frozen protocol SHA-256 is `029360e68f6940d25daa0fe46ded797f625e15bdf280d475ef763ec0eefbb07c`.

## Measured performance

The bounded fixture drives the real Replay command and all nine funded books. It uses generated inputs for technical comparison. Timings are from one Release trial per size on the same host with .NET SDK 8.0.428. Allocations are cumulative managed allocation volume from a separately instrumented original build.

| M5 clocks | Original | Recovery | Original checkpoint/restore calls | Original checkpoint/restore allocations |
| ---: | ---: | ---: | ---: | ---: |
| 512 | 10.23 s | 1.01 s | 6,648 | 7.93 GB |
| 1,024 | 32.70 s | 1.74 s | 12,813 | 29.80 GB |
| 2,048 | 117.53 s | 2.43 s | 25,116 | 114.31 GB |

At 2,048 clocks the profiled original spent 115.81 of 119.92 internal seconds serializing, hashing, parsing and restoring the ledger. The nine-book loop called the engine 18,432 times. The ledger summaries took 0.35 s across 86,043 calls. The historical lower-bound calculation took 0.11 s across 5,757 calls. Held-position management took 0.12 s across 10,356 calls.

The recovery applies one fact atomically on the owned model ledger with bounded live-state copies and a commit of validated journal entries. It reuses incremental settlement totals, derives them from the original checkpoint format on restart, and updates causal history by family on each eligible close. The frozen two-pass lower bound is recomputed in the original order when eligible history changes. The runner reuses completed bar windows and still advances each of the nine books on every source clock.

## Technical parity and EPM1

Run both commands from the repository root.

```bash
python -m research.cpe1_recovery_benchmark --baseline-profile
python -m research.cpe1_recovery_benchmark
```

The second command compares native result files byte for byte and compares digests of per-frame decisions, ordered ledger facts, settlement fragments and complete checkpoints. It covers Held + Pending and a rejected repriced fill, known nonzero financing, unknown swap with a protective close, observation gaps, and restart before and after causal family calibration. GitHub CI also runs the native accounting and recovery suite. All these checks have a technical scope.

Recovery logs emit `EPM1` records as source and financing authentication begin, as C# finishes source clocks and each book's ledger reconciliation, and as the report is written. Initial and terminal records for each measured phase are flushed immediately. Python relays validated progress from the running child process. On failure it logs the native stage, diagnostic code and subprocess exit code. On timeout it reports the last live stage and terminates the child. The private stderr capture is ephemeral. The ordinary native result serialization contains no progress fields.

## Authorization for a single recovery

1. Review the technical PR and its CI artifact. Obtain independent verification of the exact recovery implementation before proceeding.
2. Integrate the changes and verify successful technical parity on the resulting `main` head. The OWNER enrolls the independent reviewer's distinct numeric GitHub account ID in the repository Actions variable `CPE1_INDEPENDENT_AUDITOR_ACCOUNT_ID`. The independent reviewer posts a new comment on [Issue #393](https://github.com/mariancradulescu/mxm-quant-cloud/issues/393) with the exact reviewed SHA and CI run ID. GitHub's comment author ID must match the enrolled account. The shared repository account and copied or edited comments are ineligible.

   ```text
   CPE1_TECHNICAL_RECOVERY_1_INDEPENDENT_APPROVAL <main-head-sha> <technical-ci-run-id>
   ```

3. After the final audit and explicit OWNER decision, the single-file commit on that same `main` adds `ops/cpe1-recovery-1-owner-authorization.json` with subject `OWNER_CPE1_TECHNICAL_RECOVERY_1`. Replace the sample values with the verified head SHA, technical CI run ID and independent audit comment ID.

   ```json
   {
     "RecoveryIdentity": "CPE1_TECHNICAL_RECOVERY_1",
     "OriginalRunId": 45334211971,
     "OriginalAttempt": 1,
     "OriginalDisposition": "CPE1_ORIGINAL_ATTEMPT_1_TIMEOUT_NO_ECONOMIC_VERDICT",
     "ReviewedHead": "<main-head-sha>",
     "TechnicalCiRunId": 1,
     "IndependentAuditCommentId": 1
   }
   ```

4. Before the marker is added, the OWNER configures the secret-free GitHub environment `cpe1-recovery-1-owner-review` for `main` with `mariancradulescu` as the required reviewer and administrator bypass disabled. Allow the OWNER to review the run initiated by their marker. The OWNER approves this exact workflow run in GitHub's deployment review. The workflow reads the approval from GitHub and requires the OWNER account ID `322088485` for that environment. It fails closed if the environment has no recorded approval. Only the OWNER should hold credentials that can approve the environment. The DIRECTOR's repository workflow and marker writes do not provide an approval record.
5. `cpe1-recovery-1.yml` validates the first use of the recovery marker, exact reviewed head, green technical CI, independent reviewer, original timeout disposition and BDP1 authenticated preflight. After the OWNER review, the protected job loads the original sealed BDP1, AIP1, HXC1, XMH2 and P05 sources and uses the same source/funding bridge, frozen configuration and 8,400-second native timeout. It retains EUR300 shared within each book, the same controls, HARD21 accounting and the existing drawdown rules. Admission is limited to the first attempt. The job runs in historical Replay with zero broker writes, LIVE/DEMO orders or Cloud activation.
6. Check live EPM1 records in the recovery job. A completed, reconciled result is published under `cpe1-technical-recovery-1-authentic-csharp-eur300`. The separate receipt links the run ID, original attempt, authorization and review. A failed recovery has a diagnostic log and no economic verdict.

# CPE1 source-only preflight recovery — OWNER 2026-11-24

PR #443 remains unmerged. Run 45331798304 job 138234775536 failed with zero recorded steps, no artifact and no downloadable job log. GitHub returned two check annotations, but this connection cannot retrieve their content or environment policy. Main-only deployment restriction is a plausible diagnosis, not a verified exact annotation. No missing broker contract field has been inferred from this failure.

This main-only workflow installs the isolated original-source recovery module, reuses the existing authenticated BDP1 custody reader and existing environment protections. It checks the original envelope hash, account, raw responses and bars; publishes only EURUSD/GBPUSD contract field presence/values and public proof. No broker call, secrets mutation, economic engine, order, Cloud runtime or prior economic evaluator is invoked. No PR code is checked out inside the protected job.

The separate source-only marker does not authorize the economic workflow. Original economic marker remains absent until OWNER's technical gate and source readback have passed. No changes to the frozen CPE1 economic protocol.

> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# GitHub preconfiguration and transfer assessment — 2026-11-02

## Completed and read back in the GitHub UI
- Public repository: mariancradulescu/mxm-quant-cloud.
- mxm-r3-pepperstone-v1, environment ID 26008507326.
- mxm-r3-custody-v1, environment ID 26008572223.
- Both: selected branches/tags policy, exactly one Branch rule `main`, zero tags, administrator bypass disabled, no required reviewers or timers.
- Both environments contain no secrets at time of verification. No placeholder secret values were installed.
- Actions policy restricts third-party actions to checkout, setup-dotnet, setup-python, upload-artifact and download-artifact under actions/. GitHub also permits owner-authored actions under this policy.
- Full-length SHA pinning is required by repository policy and implemented in the single workflow.
- Default workflow token is read-only; creating/approving pull requests via Actions is disabled.
- External fork contributors require workflow approval; ordinary owner dispatch is not given a repetitive manual gate.

Commit 58e99e781c62d80da87002cd8f160642dc0e83e2 pinned all five action dependencies. Run https://github.com/mariancradulescu/mxm-quant-cloud/actions/runs/41434759964 completed successfully. Existing collect and custody jobs remain explicit main-only dispatch, without trading paths.

## Secure transfer assessment
GitHub source UI confirmed these existing environment secret NAMES, never values:
- mxm-r3-pepperstone-v1: R3_CTRADER_CLIENT_ID, R3_CTRADER_CLIENT_SECRET, R3_CTRADER_ACCESS_TOKEN, R3_CTRADER_REFRESH_TOKEN.
- mxm-r3-custody-v1: R3_CUSTODY_PRIVATE_KEY_PEM.
- Other historical issuer environments: O04_ACCEPTOR_APP_PRIVATE_KEY, O04_CUSTODY_CANARY, SUCCESSOR_APP_PRIVATE_KEY.
- Repository-level secrets: none displayed.

The source repository lists ChatGPT Codex Connector and MXM O04 Staging Acceptor 20261016. Destination lists only ChatGPT Codex Connector. The historical issuer source explicitly mints a contents-write token for old repository ID 1374181010, with only contents/metadata permissions. That token cannot install environment secrets in the destination.

GITHUB_TOKEN is scoped to its workflow repository. GitHub secret GET endpoints expose metadata, not stored values. The available connector exposes neither environment/secret administration nor its credentials. No existing cross-repository secret-writer credential was identified in the available configuration.

The installation-level settings page additionally requested GitHub sudo reconfirmation; no reauthentication or permission expansion was performed. Consequently transfer was not executed under existing access. This is a limitation of the observed credentials/permissions, not a claim that GitHub universally prohibits machine-side transfer. Such a transfer would require an appropriately authorized destination writer; none is currently available to this task.

No source workflow was modified or relaunched to export secrets. No values, encrypted secret bundles or credentials were placed in logs, artifacts, code or chat. Old repository unchanged.

## Remaining owner action
Only enter existing values in the prepared environment-secret forms, according to CREDENTIAL_SETUP.md. No environment/rule/workflow setup remains for OWNER. Account-binding fingerprint is existing configuration, not a new authentication identity. No refresh-token rotation occurs in the current collector.

Authenticated collection and custody readback are pending those values. No economic qualification, LIVE/DEMO order or Cloud activation is claimed.

## Official mechanism references
- https://docs.github.com/en/actions/concepts/security/github_token
- https://docs.github.com/en/rest/actions/secrets

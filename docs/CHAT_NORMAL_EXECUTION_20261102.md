# Chat-normal GitHub Actions handoff — 2026-11-02

## Scope and authority

This extends the existing repository; it is not a new strategy, credential, broker identity, order authorization or Cloud activation. The GitHub connector in Chat normal can create GitHub commits, branches and PRs but exposes no direct Actions workflow_dispatch operation. GitHub Actions is the only machine-side runner. No ChatGPT/background agent is implied.

## Explicit push-based request (no Work browser)

The existing **single** `.github/workflows/verify.yml` retains ordinary push/PR verification without secrets. Its privileged jobs additionally accept a GitHub **push to main** only when all requirements hold:

1. GitHub authenticated actor equals the repository OWNER `mariancradulescu`;
2. the normal secret-free verify job checks the last commit subject equals **`MXM_READ_ONLY_SOURCE_ADMISSION`** exactly;
3. that job independently verifies using `git diff-tree` that the last commit adds or modifies **`ops/collect-request.txt`**, and publishes only a boolean job output;
4. the normal verify job succeeds first, and the protected jobs require the boolean output;
5. both existing GitHub environments allow only `main`. Collection and custody jobs use distinct environments.

This Git object verification replaces reliance on the optional `head_commit.added/modified` fields in an event payload, which did not activate the protected jobs in run #41443569152.

For dispatch the same OWNER/main gate additionally requires explicit `collect=true`. Neither PRs, fork code, normal commits, other branches, nor non-owner pushes satisfy the job gates. A request is just a plain-text marker; it MUST contain no credentials, account identifiers, market data or code. Future controlled requests may change the marker, with one new authorized commit each. A regular code merge does not request a capture.

The source collector uses an exact request-type allowlist that excludes orders, closes, cancellations and token refresh. It verifies explicit SCOPE_VIEW, independently bound LIVE identity and Pepperstone broker before source admission. No account identity bypass, token copying or new credential is permitted. The encrypted source is kept only as a sealed artifact; the separate custody job tests the existing recipient independently even if collection fails, and decrypts/replays only after a successful sealed-source upload.

## Explicit limitations

As observed on 2026-11-02, `main` is **not branch protected**, and no repository ruleset was returned by the readable API. The authenticated GitHub connector does not expose a branch protection/ruleset administration operation. The owner-only event gate and environment branch restrictions narrow invocation but are **not equivalent to branch protection**; main writes remain a significant integrity boundary. Do not merge unreviewed workflow edits or grant write access to untrusted collaborators. In particular, do not treat this implementation as proof that a compromised OWNER account cannot access its configured secrets.

Any account-binding failure must halt account selection, even if app/token authentication succeeds. A successful custody-key preflight is not proof of genuine Pepperstone source decryption. The seven-day H1 sample is not the required twelve-month economic test. The native .algo remains observation-only and forbidden from Cloud activation or LIVE/DEMO orders.

The workflow does not schedule repetitive capture: the request is explicit to avoid uncontrolled secret access, cost and source polling. Trigger receipts are read from GitHub run jobs and sealed artifacts, not chat claims.

## 2026-11-02 configuration outcome

Owner-controlled push run #41444054445 verified application authentication and explicit `SCOPE_VIEW` on the existing token, then stopped before account selection with `ACCOUNT_BINDING_INVALID`. Separately, the custody job parsed the configured private key but reported `CUSTODY_EXISTING_RECIPIENT_MISMATCH`. Neither condition authorizes bypassing the bound LIVE account or switching custody identity. No authentic source, decrypted readback or economic replay resulted.

A format-only remediation now accepts a complete 64-hex SHA-256 fingerprint directly, with matching quotes/backticks, optional `sha256:`/`0x` notation, or an exact `ACCOUNT_FINGERPRINT_SHA256 = ...` assignment. The *same exact fingerprint match* remains mandatory; malformed, partial or different values still fail before account authentication. This does not repair a wrong secret value. It does not change the fixed original recipient public key or the verified custody mismatch.

> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# OWNER secret reconciliation — 2026-11-02

This is a **two-value repair**, not an OAuth registration, new keypair, broker request, or a new architecture. No secret values may be committed, emailed, printed, or pasted into chat.

## Existing account fingerprint

The only source of truth is `mariancradulescu/mxm-quant-greenfield` at pinned commit `6a4e56758d985f00020cd13ef264e8dc84fc6a9b`, file `research_core_v4/shallow_m5_support_v2_production.py`, line 49, constant `ACCOUNT_FINGERPRINT_SHA256`. The literal is an exact 64-character SHA-256 hex digest, not a cTrader login number. Its binding formula is the existing SHA256 of ASCII `ctrader-account:<ctidTraderAccountId>`, lines 298–299. This is **not** publicly reproduced in the new repository because it binds to the OWNER account.

The existing new-repository Pepperstone environment is [mxm-r3-pepperstone-v1](https://github.com/mariancradulescu/mxm-quant-cloud/settings/environments/26008507326/edit). Only its existing `R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256` value needs replacement with the historical 64-hex literal. Do not change the cTrader client ID, secret, SCOPE_VIEW token, or account-selection code. Application authentication and the explicit view-only scope already passed in run #41444751489. The collector must still independently prove that exactly one token-listed account matches the fingerprint, is LIVE, authenticates successfully and belongs to Pepperstone.

## Existing custody recipient

Original repository path at the **same pinned historical commit**: `research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem`. Its canonical RSA public SPKI SHA256 fingerprint is `464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11`. It matches the original production constant `PUBLIC_SPKI_SHA256` at line 50, and the public key now committed as `research/custody_public.pem` is byte-equivalent apart from formatting whitespace.

The historical proof `research_core_v4/state/V4_ASYMMETRIC_PRIVATE_KEY_PAIR_PROBE_LATEST.json`, GitHub run [37094044243](https://github.com/mariancradulescu/mxm-quant-greenfield/actions/runs/37094044243), reports PASS, `secret_name=MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM`, valid RSA private-key parse and exactly matching derived public fingerprint. A separate verification at run 37896728730 also reports valid original private key and matching SPKI. **These prove historical availability and pairing, not current ability to read the private value.**

The current destination environment is [mxm-r3-custody-v1](https://github.com/mariancradulescu/mxm-quant-cloud/settings/environments/26008572223/edit). Only `R3_CUSTODY_PRIVATE_KEY_PEM` needs replacement with the **existing original value** of `MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM` from the secure original owner-controlled copy. Preserve PEM BEGIN/END boundaries and all lines. GitHub Actions secrets are write-only; a previously installed secret cannot be retrieved via an Actions read API, and the GitHub Chat-normal connector cannot modify environment secrets. The value is not present in the historical public PASS receipt.

Do not confuse this historical recipient with any of the many different `RECIPIENT_PUBLIC_KEY.pem` files for other historical campaigns. Do not create new keys, swap the public key, or decrypt another user's / another campaign's ciphertext using an unrelated private secret. An original private key that is unavailable from secure escrow cannot be reconstructed from its public counterpart.

## Minimal OWNER action and follow-up

Only two replacements within the **already-configured environments** are required, if OWNER still has the original private value available. No owner GitHub workflows, branches, commits, PRs, deployments, credentials or external correspondence are requested. No authentication run is to be repeated while either value is unchanged.

After both replacements have been confirmed without values being shared in chat, the Director can create a single explicit owner-scoped read-only request commit in normal Chat. Expected machine-side sequence: app auth, explicit SCOPE_VIEW, exact LIVE fingerprint binding, Pepperstone identity, authentic sealed source; separately original custody key preflight, encrypted envelope decryption, C# receipt parity. A failure at any stage remains fail closed. No LIVE/DEMO orders or Cloud activation.

## Main protection

Live GitHub reads on 2026-11-02: default `main` has `protected=false` and the repository rulesets endpoint returned `[]`. The available Chat-normal GitHub connector has source/PR/merge capabilities but **no authorized branch-protection or repository-ruleset write action**. A branch protection policy requiring the `verify` status, PR review for untrusted contributions, and preventing force pushes/deletions is preferable when an authorized administrator route exists, but configuration is not claimed done and no untrusted bypass is introduced.

Until then, all Director code changes should remain isolated in feature branches, pass Actions CI, enter via normal PRs, and be merged using expected-head leases. The protected source request must be exactly an owner/main Git commit changing **only** `ops/collect-request.txt` with fixed intent subject; neither generic pushes nor PRs may receive Pepperstone/custody secrets. This is defense in depth, not a substitute for a GitHub ruleset.

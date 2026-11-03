> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

> **Updated 2026-11-02 — new-source v2 supersedes the two historical-repair requirements below.** For **new** Pepperstone data collection, the source identity is now pinned to the exact original account via a double-SHA256 commitment in code; `R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256` is no longer read. The existing RSA private secret `R3_CUSTODY_PRIVATE_KEY_PEM` is used as installed to derive a **different, run-bound new-source public recipient**; it need not decrypt historical archives. No new credentials or keys and no OWNER secret changes are requested for the new-source pipeline. Historical decryption still requires the corresponding original private key. Read [new-source v2 decision](NEW_SOURCE_CUSTODY_AND_ECONOMICS_20261102.md) before following older setup steps.

# Existing credentials: owner setup, no values in chat

The new repository cannot inherit repository/environment secrets from the old repository. GitHub does not reveal saved values. Re-enter the EXISTING values from your secure original copy. Do not create a new OAuth application, token identity or custody keypair.

The Director has created and verified both environments. OWNER does not need to create environments, branch rules or workflows. Each environment permits only the branch `main` (zero tags); administrator bypass is disabled; no manual reviewer/timer gate was added.

Direct prepared pages:
- Pepperstone: https://github.com/mariancradulescu/mxm-quant-cloud/settings/environments/26008507326/edit
- Custody: https://github.com/mariancradulescu/mxm-quant-cloud/settings/environments/26008572223/edit

Open the relevant page, scroll to Environment secrets and select Add environment secret. Only enter the existing values under the names below.

| Environment | Secret name | Existing value to enter |
|---|---|---|
| mxm-r3-pepperstone-v1 | R3_CTRADER_CLIENT_ID | Existing cTrader Open API application client ID |
| mxm-r3-pepperstone-v1 | R3_CTRADER_CLIENT_SECRET | Existing application client secret |
| mxm-r3-pepperstone-v1 | R3_CTRADER_ACCESS_TOKEN | Existing token with explicit SCOPE_VIEW |
| mxm-r3-pepperstone-v1 | R3_CTRADER_ACCOUNT_FINGERPRINT_SHA256 | Existing ACCOUNT_FINGERPRINT_SHA256 constant from research_core_v4/shallow_m5_support_v2_production.py at old commit 6a4e56758d985f00020cd13ef264e8dc84fc6a9b; copy privately into the secret field |
| mxm-r3-custody-v1 | R3_CUSTODY_PRIVATE_KEY_PEM | Existing private key corresponding to research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem; include existing PEM delimiters and line breaks |

For each entry: Environment secrets → Add secret → enter the exact name above → paste the existing value directly into GitHub → Add secret. Do not paste values in issues, workflow inputs, source files, screenshots or chat.

The account fingerprint is a selection constraint, not a new credential. Formula retained unchanged from the existing collector: SHA256 of ASCII `ctrader-account:<internal ctidTraderAccountId>`. Do not substitute the visible account login number. Its value is deliberately absent from this public repository and report.

The existing public key has SPKI SHA256 `464d2429313b8a417d26e478dab32aa1fa606471db1239a9fcfc6daa3329cb11`. Only its public half is committed. The private key remains in the custody environment and never enters the collection job.

Do not install R3_CTRADER_REFRESH_TOKEN yet: the current workflow never refreshes tokens. A refresh must preserve the existing application and atomically retain the rotated pair in secure storage before use; that write-back mechanism is not enabled. If the existing access token has expired, report only the error code, not the token. Normal rotation remains permitted but no blind refresh occurs.

After configuration, tell the Director only that setup is complete. The Director can initiate the existing single workflow using workflow_dispatch with collect=true on main. No orders, Cloud activation or trading permission is requested. Do not start the `.algo` artifact.

The two environments isolate distinct jobs. No additional sandbox is required: the historical sandbox's identity is still unconfirmed. Do not label either environment as sandbox.

Expected receipts: authenticated collection → sealed-source artifact → separate custody decrypt → C# receipt comparison → custody-public-receipt artifact. Any failure leaves economic qualification false. The seven-day H1 integration sample is not a twelve-month validation dataset and is not a final instrument restriction.

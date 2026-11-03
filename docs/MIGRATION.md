> Historical/technical record. Current OWNER requirements and methodology: [OWNER_SPEC.md](OWNER_SPEC.md). Frozen results retain their original rules.

# Selective migration manifest — 2026-11-02

Source: mariancradulescu/mxm-quant-greenfield, isolated commit `6a4e56758d985f00020cd13ef264e8dc84fc6a9b`; official historical branch `467fb68a965305c935806e28c08f0465620ccb45`. This repository currently contains newly written foundation code, not a completed port of the components below.

| Candidate | Disposition and required verification |
|---|---|
| m6/ctrader_transport.py and ctrader_proto | Extract TLS framing/correlation/heartbeat; retain Spotware license; refresh schema against official protocol |
| m6/ctrader_capture.py require_read_only_request | Extract allowlist only; tests must reject every trading request |
| research_core_v4/shallow_m5_support_v2_production.py | Extract scope/account authentication and encryption; never publish account identity configuration |
| laboratory/mxm_be_new_pepperstone_bidask_20261101.py | Extract signed cumulative time/price decoder; preserve zero timestamp deltas |
| laboratory/mxm_be_new_october_m5_20261101.py | Extract bar decoding only after schema/completeness corrections |
| native_tick_replay_v1/csharp | Review cost, FX, financing, inventory and causal-intent primitives individually; exclude strategy coupling |
| operational/MxmReferenceProductBot.cs | Native inventory patterns only; exclude Desktop fence and historical strategy |
| Historical encrypted corpora and rejection evidence | Preserve at source with hashes and evidence links; no plaintext migration into public repository |

Paths abbreviated after research_core_v4 where applicable. Excluded: 322-workflow accumulation, mxm_runtime contract/operation historical caps and injected execution assumptions, MxmOwnerEntryEnvelope, desktop checkpoint stores, rejected models as active strategies, successor GitHub App issuer.

Historical evidence: source runs 41311440117 (authenticated read-only ticks), 41064167701 (annual C# replay), 41408489996 (secretless isolated verification), 41408613378 (collection did not execute successfully). None proves this new repository's authenticated end-to-end path. Rejected experiments remain in the old repository and the migration audit; no strategy is promoted here.

## Existing credential roles — names only

| Existing names | Role / boundary |
|---|---|
| R3_CTRADER_CLIENT_ID, R3_CTRADER_CLIENT_SECRET | Same existing cTrader OAuth application |
| R3_CTRADER_ACCESS_TOKEN | Existing read-only authorization; actual scope must be checked |
| R3_CTRADER_REFRESH_TOKEN | Existing application refresh; historical reference, presence not yet verified |
| CTRADER_CLIENT_ID / CLIENT_SECRET / ACCESS_TOKEN / REFRESH_TOKEN | Historical aliases, not a request for another identity |
| R3_CUSTODY_PRIVATE_KEY_PEM | Existing custody decryption key; separate protected job, never public output |
| MXM_V4_INPUT_BUNDLE_PRIVATE_KEY_PEM | Historical custody alias; establish exact key mapping first |

Existing environments referenced by source are mxm-r3-pepperstone-v1 and mxm-r3-custody-v1. References do not prove secret presence or current environment policy. Sandbox identity remains unconfirmed; no sandbox role is assigned. SUCCESSOR_APP_PRIVATE_KEY is a historical GitHub issuer key, not cTrader credentials; excluded by default.

OWNER will enter existing values directly in GitHub protected environments when the read-only collector and custody boundary are ready. Do not send values through chat or copy them in code. No refresh is performed by current CI. Future token refresh must use a single writer because rotation can invalidate the previous pair; secure storage of the replacement must be established before refresh is enabled. No new OAuth application is required.

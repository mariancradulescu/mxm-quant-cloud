# Selective migration implemented

Historical source pin: mariancradulescu/mxm-quant-greenfield@6a4e56758d985f00020cd13ef264e8dc84fc6a9b.

- m6/ctrader_transport.py (blob 447e24ba8b8a1319a36f603c66aaf5180c7aad1c) → research/ctrader_transport.py. TLS/correlation/heartbeat retained. New strict concrete-message allowlist, payload-type validation, bounded batches, minimum 0.21-second pacing and non-disclosing exception details.
- shallow_m5_support_v2_production.py::authenticate_segment → research/collect.py::authenticate. Explicit SCOPE_VIEW, live-account binding and prefixed account fingerprint retained; hardcoded account identity moved to protected configuration. Added brokerName verification.
- laboratory/mxm_be_new_pepperstone_bidask_20261101.py::decode_side → research/decode.py. Signed cumulative time/price deltas and zero-millisecond deltas preserved.
- Existing custody public key copied unchanged from research_core_v4/keys/MXM_V4_INPUT_BUNDLE_PUBLIC_KEY.pem. No new recipient identity. New versioned AES-256-GCM/RSA-OAEP-SHA256 envelope; this is NOT the old OpenPGP container format. Legacy artifacts remain at source and require the legacy decoder, not the new decoder.
- Protobuf updated against official spotware/openapi-proto-messages@3fd8bddfbe0cfc2ecfda079623dc4e498af11e66. Source `.proto` and MIT license retained; generated with grpcio-tools 1.71.0, relative imports patched. This fixes missing trendbar hasMore field; deprecated response timestamp is not required.

No rejected predictive mechanism migrated. No old 2/80/120 EUR or single-position limits copied. Current cBot remains unchanged and has no execution path. The C# net settlement ledger is a primitive, not a complete funded replay engine. Mxm.Replay currently validates source admission only; its name does not certify economic replay.

Public outputs contain encrypted source data and fixed-status/hash receipts only. Auth responses containing tokens are never retained. Originals, account identity, symbol contracts and C# detailed source receipts remain inside the encrypted envelope. Raw request credentials never enter subprocess arguments.

Technical tests cover the new trust boundaries, not strategy optimization. Authenticated integration, existing-key readback, historical cost sufficiency and economic performance remain unverified until actual execution and appropriate data are available.

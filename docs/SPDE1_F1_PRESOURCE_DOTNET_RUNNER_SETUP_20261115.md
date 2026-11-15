# SPDE1 F1 — strictly technical pre-source runner correction

OWNER 2026-11-15 systemic OHLCV discovery. Original protocol first frozen
at 78126e3b3f1829ea81fc026e5e345a6ce9085685; unchanged.

Original attempt #43737304206 passed specialized CI but protected research job
FAILED before checkout, broker original artifact download/decryption,
feature computation, and ANY financial label. The runner could not
resolve actions/setup-dotnet at the accidentally supplied invalid Git
commit hash d4b0f63c456f71f60dc7b7ef596dcda22579ca62.

F1 changes ONLY that action's SHA to
67a3573c9a986a3f9c594539f4ab511d57bb3ce9, the existing
repository's native verify.yml SHA-pinned actions/setup-dotnet v4.
No model, features, hyperparameters, target, costing, calendar, source,
closed strategy, volume, capital, or scores change.
Run the original source-only BDP1+AIP1 receipt workflow exactly once
after F1 CI, with no new Pepperstone requests, orders or Cloud.
No previous SPDE1 original outcome exists to select on.

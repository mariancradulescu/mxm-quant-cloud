# F1 synthetic native event and Decimal parity boundary

This is a reference MODEL_REPLAY fixture, not Pepperstone fills or a
PVE1/PVE2 Python Book parity certificate. `research/fixtures/f1_native_events.json`
contains exactly one EUR300 initial book, two simultaneous distinct symbols,
physical units, long and short BID/ASK pricing, slippage, EUR conversion,
commissions, signed financing, partial closure and final round trips.
`research.test_native_financial_parity` invokes EXISTING C# NativeFundedLedger
via Mxm.Replay.ReceiveFacts; it compares individual IDs, units, close flags
and Decimal-modeled financial results (EUR tolerance 0.000000001), restarts at
every event, repeats identical events and rejects conflicting/late/corrupt
facts. Expected +2.256 EUR is SYNTHETIC settlement, not economic alpha.
Two complete trips in one UTC week do NOT pass HARD21.
The native summary cannot certify global continuous drawdown, a live broker
identity/cash, independent time-series performance or Cloud continuation.
Legacy EUR200 evidence and authentic PVE1/PVE2 remain untouched. No orders.

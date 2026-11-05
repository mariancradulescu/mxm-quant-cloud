# Prospective F1 economic-to-native-financial parity boundary

This is an executed *synthetic* single-account 300 EUR lifecycle check, not a scored market predictor.
`tests/Mxm.Checks/ProspectiveIntegratedChecks.cs` directly connects **NativeCausalWarmup** to
a deterministic test-only drift-sign predictor, causal benchmark/cost evidence,
`NativeFundedSession.DecideProspective`, `ResearchSpecialistAdmission`,
`OpportunityOrchestrator`, and unchanged `NativeFundedLedger` model facts.
It exercises successful two-symbol simultaneous allocation, pending margin,
entry BID/ASK and slippage, entry/exit commissions, signed financing,
EUR conversion, loss-time floating equity and sampled drawdown, partial/full
close, cash reconciliation, full-trip count, checkpoint restart, duplicate
idempotence and deliberate missing-cost/benchmark/gross/no-gate rejection.

The native final expected *synthetic* cash is EUR302.256; full modeled NET
+EUR2.256, two trips, not 21. Exact closed fragment NET:
A partial EUR0.795, A final EUR0.795, B final EUR0.666.
Those numeric values are from a literal physically sized Decimal oracle
(`research.test_native_financial_parity`); *not* recovered broker trades.
The synthetic evidence flags are harness inputs, never authenticated forecasts.

Legacy `research/rcp1_portfolio.py` `Book` uses
`side * notional_eur * log(exit_mid / entry_mid)`; native C# uses
`side * physical_units * (liquidation_bidask - execution_bidask)`
then current quote EUR conversion, entry/exit fees and signed financing.
For a ZERO-COST mid-price 100→102 move, notional=1000 EUR and physical
units=10, the historic log convention gives ~EUR19.8026273 whereas native
physical simple-return settlement gives EUR20, a **~EUR0.1973727 discrepancy**.
With spread, slippage, margin or FX the models diverge further. This
is intentionally NOT reconciled by expanding monetary tolerances or changing
closed historic studies: legacy Python Book remains exploratory ONLY; native
C# is financial authority for future proposed funded outcomes. The native
cost gate treats `PricesAlreadyContainBidAsk` as an explicit mutually
exclusive cost-basis choice; only one representation can justify each expense.
Future broker facts must prove the price/cost attribution and volume grid.

Coverage limits: tests do not establish authentic edge, 12-month independent
confirmation, HARD21 capacity, continuous global peak/DD, broker fact
recovery, or runtime Cloud behavior. No orders/Cloud, no retrospective scoring.

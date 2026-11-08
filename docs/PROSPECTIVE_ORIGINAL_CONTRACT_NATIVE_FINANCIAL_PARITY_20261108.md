# OWNER 2026-11-08 — Real contract source, independent Decimal/native C# financial parity

The **CMA1** and **CMA2** original Pepperstone EUR-account contracts
(`docs/CMA1_AUTHENTIC_CONTRACT_TERMS_20261108.json` and
`docs/CMA2_AUTHENTIC_COST_SURFACE_20261108.json`) are the authentic source
for instrument, minimum tradable volume, observed minimum margin,
current per-side variable/minimum commission and swap wire magnitudes.
Five distinct cases are in
`research/fixtures/prospective_original_contract_cost_parity_20261108.json`:
EURJPY long over Wednesday 22UTC triple rollover, AUDJPY short intraday,
AMD.US fraction with real **USD 0.02 minimum commission per side**,
NatGas zero variable commission but nonzero spread and USDX high-margin CFD.

**Crucial evidence limit:** the actual bid/ask **levels**, their entrance/exit
timestamps in the case, the FX routes to EUR, slippage in price units,
CMA1 pip-position and SWAP-skip structural example settings are explicitly
illustrative. For CMA2 we calibrate illustrative symmetric sides to the
**authentic published source spread values** NatGas 11.104942bps, USDX
4.917823bps and AMD.US 15.011258bps, not to any hidden genuine quote
side. These examples are **NOT authentic historical broker fills** and
their resulting EUR NET is **synthetic only**.

`src/Mxm.Replay/Program.cs --prospective-native-contract-ledger-parity`
calls the SINGLE existing Cloud-linked `Mxm.Core.NativeBrokerContractCosts`
and the SINGLE existing `NativeFundedLedger`. It applies real-as-of
contract fee by physical units and minimum, quote-specific buy/sell,
BID/ASK price execution, separate slippage, signed EUR conversion, exact
broker-contract PIPS rollover for the registered intraday/Wednesday
scenario, minimum margin, gross and cash/closed-net reconciliation,
round-trip completion, and checkpoint/restore parity.

An **independent** Python `decimal.Decimal` oracle in
`research/test_prospective_original_contract_parity.py` compares the
native output for ALL five cases: entry and exit current tariff EUR,
gross, spread, slippage, financing, conversion residual, exact EUR NET,
cash and finance/margin/round-trip/restart state at 1e-9 EUR tolerance.
Missing EUR/USD conversion or required rollover-clock facts fail closed.
CMA source contract fields are asserted independently against the
immutable original evidence files before any arithmetic.

This is *calculation parity*, not original broker filled-order parity,
historical tariff certification, actual capital deployment or a
qualified predictive trading system. Original XUA1/SFX1/other rejected
research is not recomputed. No LIVE or DEMO order and no Cloud activation.

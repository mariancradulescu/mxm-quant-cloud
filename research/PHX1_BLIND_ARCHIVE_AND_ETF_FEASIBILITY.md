# PHX1 — blind archive availability and ETF feasibility, no outcomes

OWNER v2.0 / 2026-11-13 continuation. This source-only, strictly
read-only diagnostic is frozen **BEFORE any PHX1 account call, output,
price outcome, historical signal or benchmark inspection**. RNE1 remains
frozen, no 2026-05..10 reexecution. No study is promoted here.

## Reasons before implementation

**RNE1 history:** The original 2026-05-07..10-29 Thursday research has
exposed all 26 results. Project global evidence covers additional
2025-11..2026-11 calendars for many instruments, so a second sample
inside that range is NOT independent by default. We cannot claim
older 2024–2025 NatGas history is unexposed simply because this
registry has no explicit record of its exact NatGas symbols: global
history and design exposures across all sources must be reconciled.
Older predevelopment dates, even if completely unseen, are an
**earlier blind historical stress test**, NOT forward-in-time
postdevelopment confirmation of a rule selected in late 2026.
First verify whether the original Pepperstone account serves
historical NatGas M5 bars for these exact *six outcome-free*
one-hour archive windows: 
2024-06-06, 2024-11-07, 2025-02-06, 2025-04-03,
2025-07-10, 2025-10-23, 09:25–10:55 New York.
No same-day returns, signs, shock score, economic performance or
strategy evaluation. Preserve even empty/truncated responses as
coverage truth, never loosen a source gate because the data look
unfavorable. These windows exclude known official EIA exceptions
and are diagnostic only; not a hand-picked trading sample.

**New market and new causal mechanism:** Compare two alternatives:
1. A further EIA price-threshold variant is banned: the exposed
   RNE1 configuration is fixed, no new economic mechanism.
2. A generic ETF momentum or interval-frequency score alone has
   no proposed economic informational friction.
3. The **US index CFD vs ETF cash-opening price-discovery
   discrepancy** is a different mechanism: the index CFD reacts to
   overnight information before the underlying ETF cash opening.
   Auction/creation-redemption/inventory hedging around 09:30 ET
   may temporarily leave the ETF cash first completed M5 move
   misaligned with the concurrent index. Prices are available from
   cBot MarketData.GetBars(TimeFrame.Minute5,symbol), no online
   news, HTTP, neural API or external calendar.
   Competing explanation: the ETF captures idiosyncratic or
   stock basket information, both markets are already efficient,
   index/ETF tracking spread+commission and spread-open
   slippage destroy any advantage. This mechanism requires
   separate economics at original-account minimum volume; no
   assumption that stock/ETF CFDs are tradable with EUR300.

Only discover exact current original Pepperstone roster + contract
snapshot for:
- established index CFD `US500`, ETF candidate `SPY.US`;
- established index CFD `NAS100`, ETF candidate `QQQ.US`.
Exact names are **not asserted to exist**. Unavailable symbols
are marked unavailable without substitutes. No result-conditioned
ETF choice. Observe original account current symbol enabled flag,
quote asset, trading mode, minimum volume and step, current
minimum-margin long and short, and explicit tariff presence.
These are CURRENT facts, not historical availability.
No opening performance or historical M5 data are requested
for ETF symbols in this PHX1 source-only phase.

## Execution and provenance

Existing original Pepperstone Europe EUR account, read-only SCOPE_VIEW
and original cTrader Open API only. Authenticate once through existing
binding, no new OAuth. Record original protobuf requests/responses
and full contract details **privately**, seal with the installed
RSA/AES-GCM custody recipient before any public output. Public output
may state symbol name and aggregate current contract eligibility,
no original account identifiers, token, symbol IDs, raw historical
prices, private key or server endpoint. All no-result and errors
remain explicit. Hard cap 32 post-auth read-only API requests.
If any historical request is hasMore/truncated, classify unknown,
do NOT replace it. No raw source, price target sign or outcome
appears in the public availability document.

This PHX1 probe cannot prove independent chronology or actual
cost, spread or execution. A later new original study must freeze
an exact economic policy BEFORE its first data collection,
evaluate original BID/ASK/FX, commission, margin and broad
benchmarks, and report underfunded/unpriced separately. RNE1
holiday exceptions cannot be inferred in Cloud using HTTP:
cTrader Cloud HTTP sends no requests, so a safe future strategy
must treat unverified release dates as UNKNOWN/ABSTAIN. No
automatically known 2027 holiday schedule is assumed.
No LIVE/DEMO orders, no Cloud activation or account mutation.

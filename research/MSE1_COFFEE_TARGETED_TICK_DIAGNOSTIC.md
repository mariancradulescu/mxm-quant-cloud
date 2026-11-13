# MSE1 Coffee targeted tick source diagnosis — frozen postclosure scope

Purpose: inspect **new original Pepperstone bid and ask tick provenance** for
the three unresolved in-window MSE1 Coffee clock gaps, the intraday session
closure, next-session opening and the delayed model exit. This diagnostic is
postclosure: NEVER a new calibration, selection, rescue, adjusted MSE1 P&L,
broker fill, or independent holdout.

Original intact: main SHA `39055893248a250fc129c353c91b00f83c3c3613`,
original #43366399346, original economic artifact #14010653603,
original encrypted tape #14010693489.

One original authenticated Pepperstone EUR account, read-only Open API
allowlist, existing protected credentials, no new OAuth consent, no token
refresh. **Only Coffee**, no other market and no economic scoring.
Fixed windows, all UTC:
- Sep 2, 2026 16:45–17:45, to cover original gaps 17:00, 17:10, 17:15
  and the scheduled 17:29 close / protective 17:35 deadline.
- Sep 3, 2026 08:00–09:00, to assess first quotes near 08:15 reopen.
- Sep 3, 2026 13:40–14:20, to audit the 14:00 request / 14:05 model fill.
These windows are fixed BEFORE broker source retrieval; partition into
<=20-minute fully bounded BID and ASK requests with bounded pagination.
One protected source bundle holds **every request and response protobuf**,
encrypted using existing original custody RSA recipient; public report has
timings, tick counts and freshness statuses only, never prices or account IDs.

The diagnostic compares actual latest-before-clock tick timestamp for each
side to original <=30s freshness. A no-quote window is unknown or
broker-reported NO_QUOTES; never a synthetic fill. Contemporary broker session
metadata is not proof historical Sep 2026 sessions were identical. Even if
both quote sides show contemporaneous ticks, this does **not** establish
broker-side Stop Loss execution, order submission or realizable slip.
Original MSE1 original net, margin, exit and drawdown remain unchanged.
No LIVE/DEMO orders, no Cloud trading activation, no new connected service.

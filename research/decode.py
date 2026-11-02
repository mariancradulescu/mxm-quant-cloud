from .guard import CaptureContractError

def need(condition, code):
    if not condition:
        raise CaptureContractError(code)

def decode_side(ticks, start, end):
    """Migrated signed cumulative deltas; equal-millisecond events preserved."""
    out = []
    stamp = price = None
    for i, tick in enumerate(ticks):
        dt, dp = int(tick.timestamp), int(tick.tick)
        stamp = dt if i == 0 else stamp + dt
        price = dp if i == 0 else price + dp
        need(price > 0 and start <= stamp <= end and (i == 0 or dt <= 0), "TICK_GEOMETRY")
        out.append([stamp, price])
    return list(reversed(out))

def decode_bars(bars, start, end, period_minutes):
    rows = []
    seen = set()
    for bar in bars:
        need(all(bar.HasField(f) for f in ["utcTimestampInMinutes", "low", "deltaOpen", "deltaClose", "deltaHigh"]), "BAR_FIELDS_MISSING")
        t = int(bar.utcTimestampInMinutes) * 60000
        low = int(bar.low)
        o, h, c = [low + int(getattr(bar, f)) for f in ["deltaOpen", "deltaHigh", "deltaClose"]]
        need(start <= t <= end and t not in seen and low > 0 and low <= o <= h and low <= c <= h and bar.volume >= 0, "BAR_GEOMETRY")
        seen.add(t)
        # Exclude forming bars. Features only available after close.
        if t + period_minutes * 60000 <= end:
            rows.append([t, t + period_minutes * 60000, o, h, low, c, int(bar.volume)])
    return sorted(rows)

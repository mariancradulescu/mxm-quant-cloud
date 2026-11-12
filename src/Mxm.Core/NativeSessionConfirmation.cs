namespace Mxm.Core;

// Session geometry consumes a causal prefix of the same completed M5 bars
// available to Algo. Entry and invalidation use separate executable marks.
public static class NativeSessionConfirmation
{
    public sealed record Signal(int Direction, bool Confirmed, decimal? Invalidation);

    public static Signal? Observe(string symbol, long entryClock,
        IReadOnlyDictionary<long, NativeClosedMarketBar> barsByOpen)
    {
        const long hour = 3600000L, day = 24 * hour, m5 = 300000L;
        long midnight = entryClock / day * day;
        if (entryClock != midnight + 14 * hour + 1500 || symbol is not ("GBPUSD" or "NatGas"))
            return null;

        NativeClosedMarketBar[]? Range(long date, int from, int to)
        {
            var range = new NativeClosedMarketBar[(to - from) * 12];
            for (int i = 0; i < range.Length; i++)
            {
                long open = date + from * hour + i * m5;
                if (!barsByOpen.TryGetValue(open, out var bar) || bar.OpenAt != open ||
                    bar.CloseAt != open + m5 || bar.CloseAt >= entryClock)
                    return null;
                range[i] = bar;
            }
            return range;
        }

        NativeClosedMarketBar[]? prior = null;
        for (int offset = 1; offset <= 4 && prior is null; offset++)
        {
            long date = midnight - offset * day;
            if (DateTimeOffset.FromUnixTimeMilliseconds(date).DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)
                continue;
            // Do not skip a partially observed session to select an older range.
            if (Enumerable.Range(0, 72).Any(i => barsByOpen.ContainsKey(date + 14 * hour + i * m5)))
            {
                prior = Range(date, 14, 20);
                break;
            }
        }
        if (prior is null) return null;
        if (symbol == "GBPUSD")
        {
            var morning = Range(midnight, 8, 12);
            if (morning is null) return null;
            int direction = Math.Sign(prior[^1].Close - prior[0].Open);
            return direction == 0 ? null : new(direction,
                direction * (morning[^1].Close - morning[0].Open) > 0m, null);
        }
        var lastHour = Range(midnight, 13, 14);
        if (lastHour is null) return null;
        int side = Math.Sign(lastHour[^1].Close - lastHour[0].Open);
        if (side == 0) return null;
        decimal edge = side > 0 ? prior.Max(b => b.High) : prior.Min(b => b.Low);
        bool confirmed = side * (lastHour[5].Close - edge) > 0m &&
            side * (lastHour[^1].Close - edge) > 0m;
        return new(side, confirmed, confirmed ? edge : null);
    }

    public static bool Invalidated(Signal signal, LedgerQuote quote) =>
        signal.Invalidation is decimal level &&
        (signal.Direction > 0 ? quote.Bid <= level : quote.Ask >= level);
}

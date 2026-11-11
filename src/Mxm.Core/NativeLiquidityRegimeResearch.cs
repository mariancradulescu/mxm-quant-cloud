namespace Mxm.Core;

internal static class NativeLiquidityRegimeResearch
{
    internal const string Absorption = "WFG1_LOCAL_FX_ABSORPTION";
    internal const string Release = "WFG1_COMMODITY_COMPRESSION_RELEASE";
    internal static bool IsFx(string symbol) => symbol is "AUDUSD" or "GBPUSD" or "NZDUSD";

    internal static (int Side, decimal Magnitude, string Mechanism) Forecast(
        NativeProductMarket market, NativeProductMarket? euro, long at)
    {
        const long delay = 1500L;
        var clock = DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minute = clock.Hour * 60 + clock.Minute;
        if (at % 300000L != delay || clock.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)
            return default;
        if (IsFx(market.Symbol) && minute >= 915 && minute <= 1065 && euro is not null)
        {
            var own = market.M5.TakeLast(14).ToArray();
            var reference = euro.M5.TakeLast(14).ToArray();
            if (!Complete(own, 14, at - delay) || !Complete(reference, 14, at - delay))
                return default;
            var range = own.Take(12).ToArray();
            decimal high = range.Max(x => x.High), low = range.Min(x => x.Low);
            var sweep = own[^2];
            decimal last = own[^1].Close;
            bool above = sweep.High > high, below = sweep.Low < low;
            var refRange = reference.Take(12).ToArray();
            if (above == below || sweep.Close <= low || sweep.Close >= high ||
                last <= low || last >= high ||
                reference[^2].High > refRange.Max(x => x.High) ||
                reference[^2].Low < refRange.Min(x => x.Low))
                return default;
            int side = above ? -1 : 1;
            decimal distance = side * (range.Average(x => x.Close) - last) / last;
            return side * (last - sweep.Close) > 0m && distance > 0m
                ? (side, distance, Absorption) : default;
        }
        if (market.Symbol is not ("XAUUSD" or "SpotBrent") ||
            minute < 930 || minute > 1050 || at % 1800000L != delay)
            return default;
        var bars = market.M15.TakeLast(16).ToArray();
        if (!Complete(bars, 16, at - delay))
            return default;
        var compressed = bars.Skip(8).Take(4).ToArray();
        decimal ceiling = compressed.Max(x => x.High), floor = compressed.Min(x => x.Low);
        if (ceiling - floor >= Width(bars.Take(4)) ||
            ceiling - floor >= Width(bars.Skip(4).Take(4)) ||
            bars[14].TickVolume + bars[15].TickVolume <= bars[12].TickVolume + bars[13].TickVolume)
            return default;
        decimal close = bars[^1].Close;
        if (close > ceiling && bars[^2].Close > ceiling)
            return (1, (close - floor) / close, Release);
        if (close < floor && bars[^2].Close < floor)
            return (-1, (ceiling - close) / close, Release);
        return default;
    }

    private static decimal Width(IEnumerable<NativeClosedMarketBar> bars) =>
        bars.Max(x => x.High) - bars.Min(x => x.Low);

    private static bool Complete(NativeClosedMarketBar[] bars, int count, long end) =>
        bars.Length == count && bars[^1].CloseAt == end &&
        bars.Zip(bars.Skip(1)).All(x => x.First.CloseAt == x.Second.OpenAt);
}

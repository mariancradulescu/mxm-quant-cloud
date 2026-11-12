namespace Mxm.Core;

// AEX1: new, prespecified economic hypotheses on completed 5-minute bars.
// All features are causal at the original +1500ms observed-quote decision clock.
internal static class NativeAdaptiveExitResearch
{
    internal const string Fx = "AEX1_SYNC_USD_RANGE_RELEASE";
    internal const string Commodity = "AEX1_COMMODITY_ACTIVITY_IMPULSE";
    internal static bool IsFx(string symbol) =>
        symbol is "AUDUSD" or "GBPUSD" or "NZDUSD";

    internal static (int Side, decimal Magnitude, string Mechanism) Forecast(
        NativeProductMarket market, NativeProductMarket? euro, long at)
    {
        var utc = DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minute = utc.Hour * 60 + utc.Minute;
        if (utc.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday ||
            minute < 930 || minute > 990 || at % 900000L != 1500L)
            return default;
        bool fx = IsFx(market.Symbol);
        if (!fx && market.Symbol is not ("XAUUSD" or "SpotBrent"))
            return default;
        var b = Window(market, at);
        if (b is null) return default;
        decimal ret4 = Return(b, 12, 15);
        if (ret4 == 0m) return default;
        int side = Math.Sign(ret4);
        if (fx)
        {
            if (euro is null) return default;
            var context = Window(euro, at);
            if (context is null) return default;
            decimal euroChange = Return(context, 12, 15);
            var range = b.Take(12).ToArray();
            decimal high = range.Max(x => x.High);
            decimal low = range.Min(x => x.Low);
            bool accepted = side > 0 ? b[15].Close > high : b[15].Close < low;
            long current = b.Skip(12).Sum(x => x.TickVolume);
            long baseline = b.Skip(8).Take(4).Sum(x => x.TickVolume);
            if (!accepted || side * euroChange <= 0m ||
                current <= baseline) return default;
            decimal magnitude = Math.Min(Math.Abs(ret4), Math.Abs(euroChange));
            return magnitude > 0m ? (side, magnitude, Fx) : default;
        }

        decimal prior4 = Return(b, 8, 11);
        if (side * prior4 <= 0m) return default;
        decimal old1 = Return(b, 0, 3);
        decimal old2 = Return(b, 4, 7);
        decimal threshold = (Math.Abs(old1) + Math.Abs(old2)) / 2m;
        long recentVolume = b.Skip(12).Sum(x => x.TickVolume);
        long priorVolume = b.Skip(8).Take(4).Sum(x => x.TickVolume);
        if (recentVolume <= priorVolume || Math.Abs(ret4) <= threshold)
            return default;
        return (side, Math.Abs(ret4) / 2m, Commodity);
    }

    private static NativeClosedMarketBar[]? Window(NativeProductMarket m, long at)
    {
        var bars = m.M5.TakeLast(16).ToArray();
        return bars.Length == 16 && bars[^1].CloseAt == at - 1500L &&
            bars.All(x=>x.CloseAt - x.OpenAt == 300000L) &&
            bars.Zip(bars.Skip(1)).All(p=>p.First.CloseAt == p.Second.OpenAt)
            ? bars : null;
    }

    private static decimal Return(NativeClosedMarketBar[] b,int start,int end) =>
        b[end].Close / b[start].Open - 1m;
}

namespace Mxm.Core;

internal static class NativeFactorExhaustionResearch
{
    internal const string Factor = "FCE1_COMMON_USD_REPRICING";
    internal const string Exhaustion = "FCE1_COMMODITY_EFFORT_EXHAUSTION";

    internal static bool IsFx(string symbol) => symbol is "GBPUSD" or "AUDUSD" or "NZDUSD";

    internal static (int Side, decimal Magnitude, string Mechanism) Forecast(
        NativeProductMarket market, NativeProductMarket? dollarContext, long at)
    {
        const long quarter = 900000L;
        const long delay = 1500L;
        var utc = DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minute = utc.Hour * 60 + utc.Minute;
        if (utc.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday ||
            minute < 915 || minute > 1035 || at % quarter != delay)
            return default;

        if (IsFx(market.Symbol) && dollarContext is not null)
        {
            var own = market.M15.TakeLast(9).ToArray();
            var context = dollarContext.M15.TakeLast(9).ToArray();
            if (!Complete(own, 9, at - delay) || !Complete(context, 9, at - delay))
                return default;
            decimal ownMove = EfficientMove(own);
            decimal contextMove = EfficientMove(context);
            return Math.Sign(ownMove) * Math.Sign(contextMove) == 1
                ? (Math.Sign(ownMove), Math.Min(Math.Abs(ownMove), Math.Abs(contextMove)), Factor)
                : default;
        }

        if (market.Symbol is not ("XAUUSD" or "SpotBrent"))
            return default;
        var bars = market.M15.TakeLast(11).ToArray();
        if (!Complete(bars, 11, at - delay))
            return default;
        var impulse = bars[^3];
        var second = bars[^2];
        var retrace = bars[^1];
        decimal body = impulse.Close - impulse.Open;
        decimal nextBody = second.Close - second.Open;
        int side = Math.Sign(body);
        if (Math.Abs(body) <= bars.Take(8).Average(b => b.High - b.Low) ||
            side * nextBody <= 0m || Math.Abs(nextBody) >= Math.Abs(body) ||
            second.TickVolume <= impulse.TickVolume ||
            side * (second.Close - impulse.Close) <= 0m ||
            side * (retrace.Close - second.Open) >= 0m)
            return default;
        decimal equilibrium = bars.TakeLast(8).Average(b => b.Close);
        decimal distance = -side * (equilibrium - retrace.Close) / retrace.Close;
        return distance > 0m ? (-side, distance, Exhaustion) : default;
    }

    private static decimal EfficientMove(NativeClosedMarketBar[] bars)
    {
        decimal current = bars[8].Close - bars[4].Close;
        decimal previousReturn = bars[4].Close / bars[0].Close - 1m;
        decimal currentReturn = current / bars[4].Close;
        decimal travel = bars.Skip(4).Zip(bars.Skip(5))
            .Sum(pair => Math.Abs(pair.Second.Close - pair.First.Close));
        if (Math.Abs(currentReturn) < Math.Abs(previousReturn) ||
            3m * Math.Abs(current) < 2m * travel ||
            current * (bars[8].Close - bars[7].Close) <= 0m)
            return 0m;
        return currentReturn;
    }

    private static bool Complete(NativeClosedMarketBar[] bars, int length, long end) =>
        bars.Length == length && bars[^1].CloseAt == end &&
        bars.Zip(bars.Skip(1)).All(pair => pair.First.CloseAt == pair.Second.OpenAt);
}

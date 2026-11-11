using System;
using System.Linq;

namespace Mxm.Core;

internal static class NativePullbackRangeResearch
{
    internal const string Pullback = "PRR1_US2000_BROAD_PULLBACK_RESUMPTION";
    internal const string Rejection = "PRR1_CRUDE_BALANCE_REJECTION";

    internal static (int Side, decimal Magnitude, string Mechanism) Forecast(
        NativeProductMarket market, NativeProductMarket? broad, long at)
    {
        const long interval = 900000L;
        const long observationDelay = 1500L;
        var utc = DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minutes = utc.Hour * 60 + utc.Minute;
        if (utc.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday ||
            minutes < 870 || minutes > 1050 || at % interval != observationDelay)
            return default;

        var bars = market.M15.TakeLast(14).ToArray();
        if (!Complete(bars, at - observationDelay))
            return default;

        if (market.Symbol == "US2000" && broad is not null)
        {
            var context = broad.M15.TakeLast(14).ToArray();
            if (!Complete(context, bars[^1].CloseAt))
                return default;
            decimal broadImpulse = Return(context, 8, 11);
            decimal baseline = (Math.Abs(Return(context, 0, 3)) +
                Math.Abs(Return(context, 4, 7))) / 2m;
            decimal targetImpulse = Return(bars, 8, 11);
            int side = Math.Sign(broadImpulse);
            var pullback = bars[^2];
            if (baseline <= 0m || Math.Abs(broadImpulse) <= baseline ||
                side * targetImpulse <= 0m ||
                side * (pullback.Close - pullback.Open) >= 0m ||
                (side > 0 ? bars[^1].Close <= pullback.High : bars[^1].Close >= pullback.Low))
                return default;
            return (side, Math.Abs(targetImpulse), Pullback);
        }

        if (market.Symbol == "SpotCrude")
        {
            var balance = bars.Take(12).ToArray();
            var breakout = bars[^2];
            decimal ceiling = balance.Max(x => x.High);
            decimal floor = balance.Min(x => x.Low);
            decimal close = bars[^1].Close;
            if (close <= floor || close >= ceiling ||
                breakout.TickVolume <= balance.Average(x => (decimal)x.TickVolume))
                return default;
            int side = breakout.Close > ceiling ? -1 : breakout.Close < floor ? 1 : 0;
            decimal equilibrium = bars.TakeLast(8).Average(x => x.Close);
            decimal distance = side * (equilibrium - close) / close;
            return distance > 0m ? (side, distance, Rejection) : default;
        }
        return default;
    }

    private static bool Complete(NativeClosedMarketBar[] bars, long end) =>
        bars.Length == 14 && bars[^1].CloseAt == end &&
        bars.Zip(bars.Skip(1)).All(pair => pair.First.CloseAt == pair.Second.OpenAt);

    private static decimal Return(NativeClosedMarketBar[] bars, int first, int last) =>
        bars[last].Close / bars[first].Open - 1m;
}

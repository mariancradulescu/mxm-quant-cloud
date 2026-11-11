namespace Mxm.Core;

internal static class NativeCashTransmissionResearch
{
    internal const string Acceptance = "SCT1_CASH_RANGE_GAP_ACCEPTANCE";
    internal const string Transmission = "SCT1_DELAYED_EQUITY_TO_OIL";
    internal static bool IsIndex(string symbol) => symbol is "US2000" or "US500";

    internal static (int Side, decimal Magnitude, string Mechanism) Forecast(
        NativeProductMarket market, IReadOnlyDictionary<string, NativeProductMarket> available,
        long at)
    {
        const long interval = 900000L, delay = 1500L;
        if (at % interval != delay)
            return default;
        var time = DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        if (time.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)
            return default;
        if (IsIndex(market.Symbol) && time.Hour == 14 && time.Minute == 15)
        {
            var previous = time.Date.AddDays(time.DayOfWeek == DayOfWeek.Monday ? -3 : -1);
            long open = new DateTimeOffset(previous.AddHours(13.5)).ToUnixTimeMilliseconds();
            long close = open + 26 * interval;
            var prior = market.M15.Where(x => x.OpenAt >= open && x.CloseAt <= close).ToArray();
            var current = market.M15.TakeLast(3).ToArray();
            if (!Complete(prior, 26, close) || !Complete(current, 3, at - delay))
                return default;
            decimal ceiling = prior.Max(x => x.High), floor = prior.Min(x => x.Low);
            int side = current[0].Open > ceiling ? 1 : current[0].Open < floor ? -1 : 0;
            decimal boundary = side > 0 ? ceiling : floor;
            if (side == 0 || current.Any(x => side * (x.Close - boundary) <= 0m) ||
                side * (current[^1].Close - current[^2].Close) <= 0m)
                return default;
            return (side, Math.Abs(current[^1].Close - boundary) / current[^1].Close, Acceptance);
        }

        int minute = time.Hour * 60 + time.Minute;
        if (market.Symbol != "SpotCrude" || minute < 900 || minute > 1050 ||
            at % (2 * interval) != delay || !available.TryGetValue("US500", out var equity))
            return default;
        var own = market.M15.TakeLast(12).ToArray();
        var broad = equity.M15.TakeLast(12).ToArray();
        if (!Complete(own, 12, at - delay) || !Complete(broad, 12, at - delay))
            return default;
        var oilPrior = Enumerable.Range(0, 4).Select(i => Move(own, 2 * i, 2 * i + 2)).ToArray();
        var stockPrior = Enumerable.Range(0, 4).Select(i => Move(broad, 2 * i, 2 * i + 2)).ToArray();
        decimal oilMean = oilPrior.Average(), stockMean = stockPrior.Average();
        if (oilPrior.Zip(stockPrior).Sum(p => (p.First - oilMean) * (p.Second - stockMean)) <= 0m)
            return default;
        decimal baseStock = stockPrior.Average(v => Math.Abs(v));
        decimal impulse = Move(broad, 8, 10);
        if (baseStock <= 0m || Math.Abs(impulse) <= 2m * baseStock)
            return default;
        int direction = Math.Sign(impulse);
        decimal expected = Math.Abs(impulse) * oilPrior.Average(v => Math.Abs(v)) / baseStock;
        decimal last = Move(own, 10, 11);
        if (Math.Abs(Move(own, 8, 10)) >= expected / 2m || direction * last <= 0m)
            return default;
        decimal remaining = expected - direction * Move(own, 8, 11);
        return remaining > 0m ? (direction, remaining, Transmission) : default;
    }

    private static decimal Move(NativeClosedMarketBar[] bars, int start, int end) =>
        bars[end].Close / bars[start].Close - 1m;

    private static bool Complete(NativeClosedMarketBar[] bars, int length, long end) =>
        bars.Length == length && bars[^1].CloseAt == end &&
        bars.Zip(bars.Skip(1)).All(x => x.First.CloseAt == x.Second.OpenAt);
}

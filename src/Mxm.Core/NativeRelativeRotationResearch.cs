namespace Mxm.Core;

internal static class NativeRelativeRotationResearch
{
    internal const string Rotation = "JRS1_REGIONAL_FX_ROTATION";
    internal const string Repricing = "JRS1_COMMODITY_SPECIFIC_REPRICING";

    internal static bool IsFx(string symbol) => symbol is "AUDUSD" or "NZDUSD";

    internal static bool IsDecisionClock(long at)
    {
        var utc = DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        int minutes = utc.Hour * 60 + utc.Minute;
        return minutes >= 930 && minutes <= 1050 && at % 1800000L == 1500L &&
            utc.DayOfWeek is not (DayOfWeek.Saturday or DayOfWeek.Sunday);
    }

    internal static (int Side, decimal Magnitude, string Mechanism) Forecast(
        NativeProductMarket market, IReadOnlyDictionary<string, NativeProductMarket> available,
        long at)
    {
        if (!IsDecisionClock(at) || !available.TryGetValue("EURUSD", out var euro))
            return default;

        if (IsFx(market.Symbol))
        {
            string peerName = market.Symbol == "AUDUSD" ? "NZDUSD" : "AUDUSD";
            if (!available.TryGetValue(peerName, out var peer))
                return default;
            var own = Window(market, 17, at);
            var other = Window(peer, 17, at);
            var context = Window(euro, 9, at);
            if (own is null || other is null || context is null)
                return default;
            decimal move = Return(own, 8, 16), peerMove = Return(other, 8, 16);
            decimal spread = Math.Abs(move - peerMove);
            decimal baseline = Enumerable.Range(0, 8).Average(i =>
                Math.Abs(Return(own, i, i + 1) - Return(other, i, i + 1)));
            if (move * peerMove >= 0m || Math.Abs(move) <= Math.Abs(peerMove) ||
                spread <= Math.Max(baseline, Math.Abs(Return(context, 0, 8))) ||
                move * Return(own, 15, 16) <= 0m)
                return default;
            return (Math.Sign(move), Math.Min(Math.Abs(move), spread / 2m), Rotation);
        }

        if (market.Symbol is not ("XAUUSD" or "SpotBrent") ||
            !available.TryGetValue(market.Symbol == "XAUUSD" ? "SpotBrent" : "XAUUSD",
                out var otherCommodity))
            return default;
        var target = Window(market, 13, at);
        var reference = Window(otherCommodity, 13, at);
        var fx = Window(euro, 13, at);
        if (target is null || reference is null || fx is null)
            return default;
        decimal impulse = Return(target, 8, 12);
        if (Math.Abs(impulse) <= 2m * Baseline(target) ||
            Math.Abs(Return(reference, 8, 12)) > Baseline(reference) ||
            Math.Abs(Return(fx, 8, 12)) > Baseline(fx) ||
            impulse * Return(target, 11, 12) <= 0m)
            return default;
        long latest = target.Skip(9).Sum(x => x.TickVolume);
        if (latest <= Math.Max(target.Skip(1).Take(4).Sum(x => x.TickVolume),
                              target.Skip(5).Take(4).Sum(x => x.TickVolume)))
            return default;
        return (Math.Sign(impulse), Math.Abs(impulse) / 2m, Repricing);
    }

    private static NativeClosedMarketBar[]? Window(NativeProductMarket market, int count, long at)
    {
        var bars = market.M15.TakeLast(count).ToArray();
        return bars.Length == count && bars[^1].CloseAt == at - 1500L &&
            bars.Zip(bars.Skip(1)).All(pair => pair.First.CloseAt == pair.Second.OpenAt)
            ? bars : null;
    }

    private static decimal Return(NativeClosedMarketBar[] bars, int start, int end) =>
        bars[end].Close / bars[start].Close - 1m;

    private static decimal Baseline(NativeClosedMarketBar[] bars) =>
        (Math.Abs(Return(bars, 0, 4)) + Math.Abs(Return(bars, 4, 8))) / 2m;
}

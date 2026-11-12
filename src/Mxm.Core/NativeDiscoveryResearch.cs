namespace Mxm.Core;

// DCP1 uses completed bars for features and keeps price marks in the
// existing cost and execution path. HIGH/LOW are confirmation states.
public static class NativeDiscoveryResearch
{
    public const string Profile = "DCP1";
    public static readonly long SelectionStart = Utc(3);
    public static readonly long EvaluationStart = Utc(31);
    private static long Utc(int day) =>
        new DateTimeOffset(2026, 8, day, 0, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();

    public static bool IsSlot(long at)
    {
        long minute = at / 60000L % 1440;
        return minute % 15 == 0 && minute / 60 is 8 or 14;
    }

    public static string Exit(string symbol) => symbol == "Copper"
        ? NativeCausalExitResearch.EquilibriumReversion : NativeCausalExitResearch.Chandelier;

    public static (int Side, string? Cohort) Observe(NativeProductMarket market, NativeProductMarket[] markets)
    {
        string? family = NativeConditionalResearch.Family(market.Symbol);
        if (family is null) return (0, null);
        int length = family == "FX" ? 5 : 9;
        var bars = market.M15.TakeLast(length).ToArray();
        if (bars.Length != length || !bars.Zip(bars.Skip(1)).All(x => x.First.CloseAt == x.Second.OpenAt))
            return (0, null);

        var last = bars[^1];
        var prior = bars[..^1];
        decimal high = prior.Max(b => b.High), low = prior.Min(b => b.Low);
        int side;
        bool confirmed;
        if (family == "FX")
        {
            side = last.Close > high ? 1 : last.Close < low ? -1 : 0;
            var peer = markets.FirstOrDefault(x =>
                x.Symbol == (market.Symbol == "AUDUSD" ? "NZDUSD" : "AUDUSD"));
            if (side == 0 || peer is null || peer.M15.Length < 2 ||
                peer.M15[^1].CloseAt != last.CloseAt ||
                peer.M15[^2].CloseAt != last.OpenAt) return (0, null);
            confirmed = side * (peer.M15[^1].Close - peer.M15[^2].Close) > 0m;
        }
        else
        {
            bool upperFailure = last.High > high && last.Close < high && last.Close > low;
            bool lowerFailure = last.Low < low && last.Close > low && last.Close < high;
            if (upperFailure == lowerFailure || last.TickVolume <= 0) return (0, null);
            side = lowerFailure ? 1 : -1;
            confirmed = last.TickVolume >= prior.Average(b => (decimal)b.TickVolume);
        }

        return (side, family + (confirmed ? "/HIGH" : "/LOW"));
    }
}

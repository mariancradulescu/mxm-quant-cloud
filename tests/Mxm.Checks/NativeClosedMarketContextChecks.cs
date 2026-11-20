using Mxm.Core;

internal static class NativeClosedMarketContextChecks
{
    public static void Run(Action<bool, string> check)
    {
        foreach (var requirement in NativeClosedMarketContext.CoverageWindows)
        {
            long width = NativeClosedMarketContext.Duration(requirement.Timeframe);
            long boundary = 20_000L * width;
            long at = boundary + 15_000L;
            var rows = Enumerable.Range(-requirement.Count - 2, requirement.Count + 5).Select(index =>
                new NativeClosedMarketBar(boundary + index * width, boundary + (index + 1) * width,
                    100m, 102m, 99m, 101m, index + requirement.Count + 2)).ToArray();
            var platform = rows.Where(x => x.OpenAt <= boundary).ToArray();
            NativeBarWindow Replay(NativeClosedMarketBar[] history, long? witness)
                => NativeClosedMarketContext.History(requirement, at, witness, "ORIGINAL_TEST_BROKER_DATA", history);
            NativeBarWindow Platform(NativeClosedMarketBar[] bars, long decision, long? witness)
                => NativeClosedMarketContext.Platform(requirement, decision, witness, bars.Length,
                    index => bars[index].OpenAt, index => bars[index]);

            var historic = Replay(rows, boundary + 2);
            var cloud = Platform(platform, at, boundary + 2);
            check(historic.Ready && cloud.Ready && historic.Bars.Length == requirement.Count &&
                historic.Bars.SequenceEqual(cloud.Bars) && historic.ValuesSha256() == cloud.ValuesSha256(),
                "Replay and Cloud previous-bar values agree for all seven periods with the same market witness");
            check(historic.Bars[^1].CloseAt == boundary &&
                Replay(rows.Select(x => x.OpenAt >= boundary ? x with { High = 900m } : x).ToArray(), boundary + 2)
                    .ValuesSha256() == historic.ValuesSha256(),
                "ongoing and future price mutations cannot affect the decision prefix");
            check(Platform(platform[..^1], at, boundary + 2).Status == NativeBarStatus.LatestBarMissing,
                "the platform bar is ineligible until the collection publishes its successor");
            bool nativeAnchor = requirement.Timeframe is NativeBarTimeframe.H4 or NativeBarTimeframe.D1;
            check((nativeAnchor ? Replay(rows, boundary - 1).ExpectedCloseAt < boundary :
                    Replay(rows, boundary - 1).Status == NativeBarStatus.CloseUnobserved) &&
                Replay(rows, at + 1).Status == NativeBarStatus.CloseUnobserved,
                "nominal closure alone and a future quote are both insufficient");
            check(Replay(rows.Where(x => x.CloseAt != boundary).ToArray(), boundary + 2).Status == NativeBarStatus.LatestBarMissing,
                "an older bar cannot replace the expected last closed interval");
            check(Replay(rows.Where(x => x.CloseAt != boundary - width).ToArray(), boundary + 2).Status == NativeBarStatus.MissingInterval,
                "a gap within a full lookback is identified without padding the window");
            check(Replay(rows.Where(x => x.OpenAt >= boundary - (requirement.Count - 1) * width).ToArray(),
                boundary + 2).Status == NativeBarStatus.InsufficientHistory,
                "one missing warmup bar prevents ready");
            check(Replay(rows.Select(x => x.CloseAt == boundary ? x with { High = 98m } : x).ToArray(),
                boundary + 2).Status == NativeBarStatus.InvalidBar,
                "an impossible OHLC in a verified window is rejected");
            check(Platform(platform, boundary, boundary).ExpectedCloseAt == boundary - width,
                "at the exact boundary only independently witnessed earlier bars are eligible");
            if (nativeAnchor)
            {
                long shift = 3_600_000L;
                var shifted = rows.Select(bar => bar with { OpenAt = bar.OpenAt + shift, CloseAt = bar.CloseAt + shift }).ToArray();
                var source = NativeClosedMarketContext.History(requirement, at + shift, boundary + shift + 2,
                    "NATIVE_BROKER_BOUNDARY", shifted);
                var observed = Platform(shifted.Take(platform.Length).ToArray(), at + shift, boundary + shift + 2);
                check(source.Ready && source.ExpectedCloseAt == boundary + shift &&
                    source.ValuesSha256() == observed.ValuesSha256(),
                    "H4 and D1 use the broker's observed opening anchor");
            }
        }
        check(NativeClosedMarketContext.QuoteWitness(50_000, 45_000, 50_001, 30_000) is null &&
            NativeClosedMarketContext.QuoteWitness(50_000, 19_999, 49_000, 30_000) is null &&
            NativeClosedMarketContext.QuoteWitness(50_000, 48_000, 49_000, 30_000) == 49_000,
            "paired evidence requires both causal sides and a qualified maximum age");
        check(NativeClosedMarketContext.LatestClock(65_000, 30_000, 15_000) == 45_000 &&
            NativeClosedMarketContext.LatestClock(75_000, 30_000, 15_000) == 75_000,
            "a poll before the next offset still processes the last elapsed decision clock");
    }
}

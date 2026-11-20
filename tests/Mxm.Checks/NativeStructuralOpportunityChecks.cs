using Mxm.Cloud;
using Mxm.Core;

internal static class NativeStructuralOpportunityChecks
{
    public static void Run(Action<bool, string> check)
    {
        long trigger = new DateTimeOffset(2026, 11, 9, 10, 0, 0, TimeSpan.Zero).ToUnixTimeMilliseconds();
        var contract = new NativeObservedContractTerms("EURUSD", "USD", trigger - 1, .25m, .25m, 100m, 100m,
            2, 0, 2, 0, null, 0, 0, 0m, 0m, 2, 24, 1320, 3, false, 0, true, false);

        Ucp1Frame Frame(long clock, bool platform, bool range = false, bool noActivity = false)
        {
            var windows = NativeClosedMarketContext.CoverageWindows.Select(requirement =>
            {
                var period = requirement.Timeframe;
                long width = NativeClosedMarketContext.Duration(period);
                long boundary = clock / width * width;
                var rows = Enumerable.Range(-requirement.Count, requirement.Count + 1).Select(index =>
                {
                    long open = boundary + index * width, close = open + width;
                    if (period == NativeBarTimeframe.M5 && close == trigger)
                        return range ? new NativeClosedMarketBar(open, close, 99.6m, 100m, 98.8m, 99.4m, 30) :
                            new NativeClosedMarketBar(open, close, 100m, 100.7m, 99.9m, 100.6m, 30);
                    if (period == NativeBarTimeframe.M5)
                        return new(open, close, 100m, 100.3m, 99.7m, 100m, 20);
                    if (period == NativeBarTimeframe.M1)
                    {
                        decimal value = range && close <= trigger && close >= trigger - 120_000L ?
                            99.4m - (trigger - close) / 60_000L * .2m : 100m;
                        return new(open, close, value, value + .1m, value - .1m, value,
                            !noActivity && close > trigger - 300_000L && close <= trigger ? 10 : 2);
                    }
                    decimal finish = period == NativeBarTimeframe.M15 ?
                        range ? 99.8m : close > trigger ? 100.2m : 100.6m : 101.5m;
                    decimal begin = period == NativeBarTimeframe.M15 ? 100m : 99.5m;
                    return new NativeClosedMarketBar(open, close, begin,
                        period == NativeBarTimeframe.H1 ? 104m : 102m, 99m, finish, 10);
                }).ToArray();
                return platform
                    ? NativeClosedMarketContext.Platform(requirement, clock, clock - 2L, rows.Length,
                        i => rows[i].OpenAt, i => rows[i])
                    : NativeClosedMarketContext.History(requirement, clock, clock - 2L, "SYNTHETIC_BROKER", rows);
            }).ToArray();
            var context = new NativeBarContext(clock, windows);
            decimal bid = range ? 99.4m : 100.5m;
            decimal ask = bid + .05m;
            var market = new Ucp1MarketFrame("EURUSD", new("EURUSD", clock, bid, ask, .8m, .9m, .01m, 0m, 15m),
                contract, context.For(NativeBarTimeframe.M5).Bars, context.For(NativeBarTimeframe.M15).Bars,
                .01m, "SYNTHETIC", new(context.For(NativeBarTimeframe.H1).Bars,
                    new[] { new NativeObservedVolume(.25m, 3.75m, 3.75m) }, true, .01m,
                    new(bid, bid, ask, ask, true))) { ClosedBars = context };
            return new(clock, new[] { market });
        }

        long first = trigger + 15_000L;
        var seed = Frame(first, false);
        var breakout = NativeStructuralOpportunity.Describe(seed.Markets[0]);
        check(breakout?.Signal is { Family: NativeStructuralOpportunity.Compression, Side: 1 } &&
            breakout.Thesis.ReclaimedBoundary == 100.3m,
            "closed H1/M15 alignment, local escape and real M1 activity produce one sided thesis");
        check(NativeStructuralOpportunity.Describe(Frame(first, false, noActivity: true).Markets[0]) is null,
            "a clock and price geometry without closed M1 confirmation do not create an offer");
        check(NativeStructuralOpportunity.Describe(Frame(first, false, range: true).Markets[0])?.Signal is
            { Family: NativeStructuralOpportunity.Rejection, Side: 1 },
            "a closed failed sweep with M1 recapture produces the separate rejection thesis");

        string policy = NativeStructuralOpportunity.Prefix + "FIRST";
        var replay = new NativeUnifiedPortfolioEngine(policy);
        var cloud = new NativeUnifiedCloudParityAdapter(policy);
        bool parity = true;
        for (long clock = first; clock <= first + 930_000; clock += 30_000)
            parity &= replay.Advance(Frame(clock, false)) == cloud.Observe(Frame(clock, true));
        var trip = replay.CompleteModelTrips.SingleOrDefault();
        check(parity && trip is { ExitReason: "MODEL_UNTRANSMITTED_INTEGRATED_NEW_M15_THESIS_INVALIDATION" } &&
            trip.Integrated?.Thesis?.InvalidatingM15CloseAt == trigger + 900_000 &&
            replay.ModelSummary.CashEur == 300m + trip.NetEur,
            "real adapter prefix contract agrees to the cent and new M15 invalidation settles on a later mark");
        check(replay.OriginalModelEvents.Where(e => e.Kind is "REQUEST_CLOSE" or "CLOSE_FILL")
            .Select(e => e.At).SequenceEqual(new[] { first + 900_000L, first + 930_000L }),
            "structural invalidation is never settled as a same-observation fill");
    }
}

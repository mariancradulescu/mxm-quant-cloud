using Mxm.Cloud;
using Mxm.Core;

internal static class NativeImpulseExhaustionChecks
{
    public static void Run(Action<bool,string> check)
    {
        long barEnd = new DateTimeOffset(2026, 11, 9, 10, 0, 0,
            TimeSpan.Zero).ToUnixTimeMilliseconds();
        var contract = new NativeObservedContractTerms("EURUSD", "USD", barEnd - 1,
            .25m,.25m,100m,100m,2,0,2,0,null,0,0,0m,0m,2,24,1320,3,
            false,0,true,false);

        Ucp1Frame Frame(long at, bool fastActivity = false)
        {
            var requirements = NativeClosedMarketContext.CoverageWindows
                .Where(r => NativeClosedMarketContext.Duration(r.Timeframe) <= 3_600_000L);
            var windows = requirements.Select(req =>
            {
                long width = NativeClosedMarketContext.Duration(req.Timeframe);
                var bars = Enumerable.Range(0,req.Count+2).Select(i =>
                {
                    long open = barEnd - (req.Count + 1L - i) * width;
                    long close = open + width;
                    bool trigger = close == barEnd;
                    if (req.Timeframe == NativeBarTimeframe.M5)
                        return trigger
                            ? new NativeClosedMarketBar(open,close,100.8m,101.3m,100.4m,100.7m,10)
                            : new NativeClosedMarketBar(open,close,100.5m,101m,100m,100.5m,20);
                    if (req.Timeframe == NativeBarTimeframe.M1)
                    {
                        decimal last = trigger ? 100.7m :
                            close == barEnd - 60_000L ? 100.9m : 100.8m;
                        long volume = close > barEnd - 300_000L && close <= barEnd
                            ? fastActivity ? 30 : 5 : 20;
                        return new NativeClosedMarketBar(open,close,last,last+.1m,last-.1m,last,volume);
                    }
                    if (req.Timeframe == NativeBarTimeframe.M15)
                        return new NativeClosedMarketBar(open,close,99m,102m,98.5m,
                            trigger?100.7m:100.6m,20);
                    if (req.Timeframe == NativeBarTimeframe.M30)
                        return new NativeClosedMarketBar(open,close,99m,102m,99.5m,
                            trigger?100.7m:100.6m,20);
                    return new NativeClosedMarketBar(open,close,99m,104m,98.5m,
                        trigger?100.7m:100.6m,20);
                }).ToArray();
                return NativeClosedMarketContext.History(req, at, at-2,
                    "SYNTHETIC_TEST_ONLY",bars);
            }).ToArray();
            var context = new NativeBarContext(at,windows);
            var quote = new LedgerQuote("EURUSD",at,100.60m,100.65m,.8m,.9m,.01m,0m,15m);
            var integrated = new NativeIntegratedMarket(context.For(NativeBarTimeframe.H1).Bars,
                new[]{new NativeObservedVolume(.25m,3.75m,3.75m)},true,.01m,
                new NativeObservedQuotePath(100.60m,100.60m,100.65m,100.65m,true));
            var market = new Ucp1MarketFrame("EURUSD",quote,contract,
                context.For(NativeBarTimeframe.M5).Bars,
                context.For(NativeBarTimeframe.M15).Bars,
                .01m,"SYNTHETIC_TEST_ONLY",integrated){ClosedBars=context};
            return new Ucp1Frame(at,new[]{market});
        }

        var first = Frame(barEnd+15_000L);
        var setup = NativeImpulseExhaustionResearch.Describe(first.Markets[0]);
        check(setup?.Signal is { Family: NativeImpulseExhaustionResearch.Family, Side: -1 } &&
            setup.Signal.Stop > first.Markets[0].Quote.Ask &&
            setup.Signal.Target < first.Markets[0].Quote.Bid,
            "closed H1/M15 impulse, failed M5 sweep and waning M1 activity admit bearish exhaustion");
        check(NativeImpulseExhaustionResearch.Describe(Frame(barEnd+15_000L,true).Markets[0]) is null,
            "ongoing high M1 activity cancels exhaustion without retroactive tuning");

        string policy = NativeStructuralOpportunity.Prefix + "EXHAUSTION";
        var replay = new NativeUnifiedPortfolioEngine(policy);
        var cloud = new NativeUnifiedCloudParityAdapter(policy);
        var a = replay.Advance(first);
        var b = cloud.Observe(first);
        check(a == b && a.Proposed >= 1,
            "new option enters the same native funded engine and observation-only adapter");
        var next = Frame(barEnd+45_000L);
        check(replay.Advance(next) == cloud.Observe(next),
            "post-decision 30-second quote updates preserve event/ledger parity");
        check(replay.ModelSummary.ClosedNetEur == 0m &&
            !replay.ModelSummary.OrdersEnabled,
            "proposed and/or filled simulations do not imply realized NET or orders");
    }
}

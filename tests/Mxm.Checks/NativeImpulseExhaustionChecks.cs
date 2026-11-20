using System.Text.Json;
using Mxm.Cloud;
using Mxm.Core;

internal static class NativeImpulseExhaustionChecks
{
    internal static Ucp1Frame Frame(long barEnd, long at, bool fastActivity = false)
    {
        var contract = new NativeObservedContractTerms("EURUSD", "USD", barEnd - 1,
            .25m, .25m, 100m, 100m, 2, 0, 2, 0, null, 0, 0, 0m, 0m, 2, 24, 1320, 3,
            false, 0, true, false);

        var requirements = NativeClosedMarketContext.CoverageWindows
            .Where(r => NativeClosedMarketContext.Duration(r.Timeframe) <= 3_600_000L);
        var windows = requirements.Select(req =>
        {
            long width = NativeClosedMarketContext.Duration(req.Timeframe);
            long boundary = barEnd / width * width;
            var bars = Enumerable.Range(0, req.Count + 2).Select(i =>
            {
                long open = boundary - (req.Count + 1L - i) * width;
                long close = open + width;
                bool trigger = close == barEnd;
                if (req.Timeframe == NativeBarTimeframe.M5)
                    return trigger
                        ? new NativeClosedMarketBar(open, close, 100.8m, 101.3m, 100.4m, 100.7m, 10)
                        : new NativeClosedMarketBar(open, close, 100.5m, 101m, 100m, 100.5m, 20);
                if (req.Timeframe == NativeBarTimeframe.M1)
                {
                    decimal last = trigger ? 100.7m : close == barEnd - 60_000L ? 100.9m : 100.8m;
                    long volume = close > barEnd - 300_000L && close <= barEnd
                        ? fastActivity ? 30 : 5 : 20;
                    return new NativeClosedMarketBar(open, close, last, last + .1m, last - .1m, last, volume);
                }
                decimal finish = trigger ? 100.7m : 100.6m;
                if (req.Timeframe == NativeBarTimeframe.M15)
                    return new NativeClosedMarketBar(open, close, 99m, 102m, 98.5m, finish, 20);
                if (req.Timeframe == NativeBarTimeframe.M30)
                    return new NativeClosedMarketBar(open, close, 100m, 102m, 99.5m, finish, 20);
                return new NativeClosedMarketBar(open, close, 99m, 104m, 98.5m, finish, 20);
            }).ToArray();
            return NativeClosedMarketContext.History(req, at, at - 2, "SYNTHETIC_TEST_ONLY", bars);
        }).ToArray();
        var context = new NativeBarContext(at, windows);
        var quote = new LedgerQuote("EURUSD", at, 100.60m, 100.65m, .8m, .9m, .01m, 0m, 15m);
        var integrated = new NativeIntegratedMarket(context.For(NativeBarTimeframe.H1).Bars,
            new[] { new NativeObservedVolume(.25m, 3.75m, 3.75m) }, true, .01m,
            new NativeObservedQuotePath(100.60m, 100.60m, 100.65m, 100.65m, true));
        var market = new Ucp1MarketFrame("EURUSD", quote, contract,
            context.For(NativeBarTimeframe.M5).Bars, context.For(NativeBarTimeframe.M15).Bars,
            .01m, "SYNTHETIC_TEST_ONLY", integrated) { ClosedBars = context };
        return new Ucp1Frame(at, new[] { market });
    }

    public static void Run(Action<bool, string> check)
    {
        long barEnd = new DateTimeOffset(2026, 10, 26, 10, 0, 0,
            TimeSpan.Zero).ToUnixTimeMilliseconds();
        var first = Frame(barEnd, barEnd + 15_000L);
        var setup = NativeImpulseExhaustionResearch.Describe(first.Markets[0]);
        check(setup?.Signal is { Family: NativeImpulseExhaustionResearch.Family, Side: -1 } &&
            setup.Signal.Stop > first.Markets[0].Quote.Ask &&
            setup.Signal.Target < first.Markets[0].Quote.Bid,
            "closed H1/M15 impulse, failed M5 sweep and waning M1 activity admit bearish exhaustion");
        check(NativeImpulseExhaustionResearch.Describe(Frame(barEnd, barEnd + 15_000L, fastActivity: true).Markets[0]) is null,
            "ongoing high M1 activity cancels exhaustion without retroactive tuning");

        string policy = NativeStructuralOpportunity.Prefix + "EXHAUSTION";
        var replay = new NativeUnifiedPortfolioEngine(policy);
        var cloud = new NativeUnifiedCloudParityAdapter(policy);
        var a = replay.Advance(first);
        var b = cloud.Observe(first);
        check(a == b && a.Proposed >= 1,
            "new option enters the same native funded engine and observation-only adapter");
        var next = Frame(barEnd, barEnd + 45_000L);
        check(replay.Advance(next) == cloud.Observe(next),
            "post-decision 30-second quote updates preserve event/ledger parity");
        check(replay.ModelSummary.ClosedNetEur == 0m &&
            !replay.ModelSummary.OrdersEnabled,
            "proposed and/or filled simulations do not imply realized NET or orders");

        CheckCompetition(first, next, check);
        CheckDevelopment(check);
    }

    static NativeStructuralSetup Legacy(Ucp1MarketFrame m, decimal target = 100.9m, decimal stop = 99.9m)
        => new(new(NativeStructuralOpportunity.Compression, 1, stop, target, 1m, m.M5[^1].CloseAt),
            new(NativeStructuralOpportunity.Compression, 100.3m, m.M15[^1].CloseAt), new decimal[6]);

    internal static Ucp1MarketFrame Reprice(Ucp1MarketFrame market, decimal bid, string symbol = "EURUSD",
        decimal marginPerUnit = 15m, decimal minimumUnits = .25m)
    {
        decimal ask = bid + .05m;
        decimal margin = marginPerUnit * minimumUnits;
        return market with
        {
            Symbol = symbol,
            Quote = market.Quote with { Symbol = symbol, Bid = bid, Ask = ask, MarginPerUnit = marginPerUnit },
            Contract = market.Contract with { Symbol = symbol, MinimumUnits = minimumUnits },
            Integrated = market.Integrated! with
            {
                Volumes = new[] { new NativeObservedVolume(minimumUnits, margin, margin) },
                Path = new(bid, bid, ask, ask, true)
            }
        };
    }

    static JsonElement Reasons(NativeUnifiedPortfolioEngine engine)
        => JsonSerializer.SerializeToElement(engine.OriginalOutcomeReport(0, 0, 0, long.MaxValue,
            "SYNTHETIC_TEST_ONLY", includeTrace: false)).GetProperty("reasons");

    static void CheckCompetition(Ucp1Frame first, Ucp1Frame next, Action<bool, string> check)
    {
        const string policy = NativeStructuralOpportunity.Prefix + NativeStructuralOpportunity.Combined;
        const string oldFamily = "FAMILY/" + NativeStructuralOpportunity.Compression;
        const string newFamily = "FAMILY/" + NativeImpulseExhaustionResearch.Family;
        var combined = new NativeUnifiedPortfolioEngine(policy);
        // The frozen production predicates are disjoint on this frame. Supply a
        // simultaneous legacy proposal to exercise the actual shared allocator.
        var decision = combined.Advance(first, m => Legacy(m), NativeImpulseExhaustionResearch.Describe);
        var reasons = Reasons(combined);
        check(decision.Proposed == 2 && decision.Admitted == 1 && decision.Pending == 1 &&
            reasons.GetProperty("CLOCK_WITH_COMPETING_FAMILIES_SAME_SYMBOL").GetInt32() == 1 &&
            reasons.GetProperty(oldFamily + "/EURUSD/FINANCEABLE_NOT_SELECTED").GetInt32() == 1 &&
            reasons.GetProperty(newFamily + "/EURUSD/ADMITTED").GetInt32() == 1,
            "both proposals on one symbol are funded alternatives and exhaustion can win");
        var fill = combined.Advance(next);
        check(fill.Held == 1 && combined.OriginalModelEvents.Single(e => e.Kind == "OPEN_FILL").Side == -1,
            "the selected family's own side and thesis reach a later funded fill");

        var betterLegacy = new NativeUnifiedPortfolioEngine(policy);
        betterLegacy.Advance(first, m => Legacy(m, target: 104m), NativeImpulseExhaustionResearch.Describe);
        check(betterLegacy.OriginalModelEvents.Single(e => e.Kind == "REQUEST_OPEN").Side == 1,
            "the legacy offer wins when its predecision net payoff per reserved risk is higher");

        var unfundedLegacy = new NativeUnifiedPortfolioEngine(policy);
        unfundedLegacy.Advance(first, m => Legacy(m, target: 104m, stop: 60m), NativeImpulseExhaustionResearch.Describe);
        check(Reasons(unfundedLegacy).GetProperty(oldFamily + "/EURUSD/JOINT_RISK_BUDGET").GetInt32() == 1 &&
            unfundedLegacy.OriginalModelEvents.Single(e => e.Kind == "REQUEST_OPEN").Side == -1,
            "a more distant stop fails its own risk check while the other same-symbol offer can be admitted");

        var shared = new NativeUnifiedPortfolioEngine(policy);
        var gold = Reprice(first.Markets[0], 100.60m, "XAUUSD", marginPerUnit: 600m);
        shared.Advance(first with { Markets = new[] { gold } }, m => Legacy(m), _ => null);
        var frame = next with { Markets = new[]
        {
            Reprice(next.Markets[0], 100.60m, "XAUUSD", marginPerUnit: 600m),
            Reprice(next.Markets[0], 100.60m, "GBPUSD", marginPerUnit: 400m),
            next.Markets[0]
        } };
        var withExposure = shared.Advance(frame, m => Legacy(m, target: m.Symbol == "GBPUSD" ? 104m : 100.9m),
            NativeImpulseExhaustionResearch.Describe);
        check(withExposure.Held == 1 && withExposure.ModelBook.UsedMarginEur == 150m &&
            withExposure.Pending == 1 && shared.OriginalModelEvents.Last(e => e.Kind == "REQUEST_OPEN").Symbol == "EURUSD" &&
            Reasons(shared).GetProperty(oldFamily + "/GBPUSD/RESERVED_MARGIN_BUDGET").GetInt32() == 1 &&
            Reasons(shared).GetProperty(newFamily + "/GBPUSD/RESERVED_MARGIN_BUDGET").GetInt32() == 1,
            "both GBPUSD families are rejected by the occupied common margin while EURUSD remains financeable");

        var random = new NativeUnifiedPortfolioEngine(NativeStructuralOpportunity.Prefix + NativeStructuralOpportunity.CombinedRandom);
        var randomDecision = random.Advance(first, m => Legacy(m), NativeImpulseExhaustionResearch.Describe);
        check(randomDecision.Proposed == 2 && randomDecision.Admitted == 1 &&
            Reasons(random).GetProperty("CLOCK_WITH_COMPETING_FAMILIES_SAME_SYMBOL").GetInt32() == 1,
            "the fixed-hash control draws from both financeable families");
        var ablation = new NativeUnifiedPortfolioEngine(
            NativeStructuralOpportunity.Prefix + NativeStructuralOpportunity.CombinedWithoutExhaustion);
        var ablated = ablation.Advance(first, m => Legacy(m), NativeImpulseExhaustionResearch.Describe);
        check(ablated.Proposed == 1 && ablation.OriginalModelEvents.Single(e => e.Kind == "REQUEST_OPEN").Side == 1 &&
            NativeStructuralOpportunity.Variants.SequenceEqual(new[] { "CASH", "FIRST", "RANDOM", "TREND",
                "REJECTION", "POOLED", "RANK", "SELECT" }),
            "the matched ablation removes only exhaustion and the frozen W46 roster stays intact");
    }

    static void CheckDevelopment(Action<bool, string> check)
    {
        const long start = 1792972800000L;
        long week = NativeCompletePolicy.Week;
        long boundary = start + 2 * week;
        long lastBar = boundary - 300_000L;
        Ucp1Frame Observation(long bar, long offset, decimal bid = 100.60m, decimal minUnits = .25m)
        {
            var frame = Frame(bar, bar + offset);
            return frame with { Markets = new[] { Reprice(frame.Markets[0], bid, minimumUnits: minUnits) } };
        }
        Ucp1Frame[] Lifecycle(long bar) => new[]
        {
            Observation(bar, 15_000L), Observation(bar, 45_000L),
            Observation(bar, 75_000L, 99.40m), Observation(bar, 105_000L, 99.40m)
        };
        JsonElement Report(Ucp1Frame[] frames)
        {
            var contracts = frames[0].Markets.ToDictionary(m => m.Symbol, m => m.Contract);
            return JsonSerializer.SerializeToElement(NativeStructuralResearch.RunExhaustionDevelopment(
                frames, start, start + 3 * week, contracts));
        }
        static JsonElement Book(JsonElement report, string scenario, string policy)
            => report.GetProperty(scenario).GetProperty("Books").GetProperty(policy);

        var frames = Enumerable.Range(1, 11).SelectMany(hour => Lifecycle(start + hour * 3_600_000L))
            .Concat(Enumerable.Range(1, 10).SelectMany(hour => Lifecycle(start + week + hour * 3_600_000L)))
            .ToArray();
        var report = Report(frames);
        foreach (string friction in new[] { "Central", "Adverse" })
        {
            var book = Book(report, friction, "COMBINED");
            var weekly = book.GetProperty("CompletedTradesByWeek");
            var financial = book.GetProperty("Financial");
            check(weekly.GetProperty("2026-W44").GetInt32() == 11 && weekly.GetProperty("2026-W45").GetInt32() == 10 &&
                book.GetProperty("WeeksWithHard21").GetInt32() == 0 && !book.GetProperty("BothWeeksHard21").GetBoolean() &&
                !financial.TryGetProperty("Hard21", out _),
                friction + " counts 11 + 10 complete funded closes as zero passing ISO weeks");
            check(financial.GetProperty("LedgerReconciled").GetBoolean() &&
                financial.GetProperty("CompleteModeledNetEur").GetDecimal() ==
                financial.GetProperty("Boundary").GetProperty("EquityEur").GetDecimal() - 300m &&
                report.GetProperty(friction).GetProperty("FullBookExhaustionAblation").GetProperty("Comparator").GetString() ==
                NativeStructuralOpportunity.CombinedWithoutExhaustion,
                friction + " reconciles flat cash and equity and uses the matched full-book ablation");
        }

        var oneWeek = Book(Report(Enumerable.Range(1, 21).SelectMany(hour => Lifecycle(start + hour * 3_600_000L))
            .ToArray()), "Central", "COMBINED");
        check(oneWeek.GetProperty("WeeksWithHard21").GetInt32() == 1 &&
            oneWeek.GetProperty("Hard21ByWeek").GetProperty("2026-W44").GetBoolean() &&
            oneWeek.GetProperty("CompletedTradesByWeek").GetProperty("2026-W45").GetInt32() == 0 &&
            !oneWeek.GetProperty("Hard21ByWeek").GetProperty("2026-W45").GetBoolean(),
            "exactly 21 funded closes pass W44 while W45 remains explicit with zero closes");

        foreach (string suffix in new[] { "", "_ADVERSE" })
        {
            string policy = NativeStructuralOpportunity.Prefix + NativeStructuralOpportunity.Combined + suffix;
            var replay = new NativeUnifiedPortfolioEngine(policy);
            var cloud = new NativeUnifiedCloudParityAdapter(policy);
            bool parity = true;
            foreach (var frame in Lifecycle(start + 3_600_000L))
                parity &= replay.Advance(frame) == cloud.Observe(frame);
            check(parity && replay.ModelSummary == cloud.ModelBook && replay.CompleteModelTrips.Length == 1,
                "identical combined-policy observations preserve intent, fill, close, cash and event hash parity " + suffix);
        }

        // A position partly reduces before W45 ends. The remaining position
        // and its later closing intent both fall outside the observed lifecycle.
        var partial = new[]
        {
            Observation(lastBar, 15_000L, minUnits: .5m),
            Observation(lastBar, 45_000L, minUnits: .5m),
            Observation(lastBar, 75_000L, 99.94m),
            Observation(lastBar, 105_000L, 99.94m),
            Observation(lastBar, 135_000L, 99.40m),
            new Ucp1Frame(boundary, Array.Empty<Ucp1MarketFrame>())
        };
        var censoredReport = Report(partial);
        var censored = Book(censoredReport, "Central", "COMBINED");
        var money = censored.GetProperty("Financial");
        var end = money.GetProperty("Boundary");
        check(end.GetProperty("RightCensored").GetBoolean() &&
            end.GetProperty("OpenPositions").GetArrayLength() == 1 &&
            end.GetProperty("PendingIntents")[0].GetProperty("Kind").GetString() == "REQUEST_CLOSE" &&
            end.GetProperty("EquityEur").ValueKind == JsonValueKind.Null &&
            end.GetProperty("LastSampledEquityEur").ValueKind == JsonValueKind.Number &&
            end.GetProperty("LastSampledAt").GetInt64() < boundary &&
            censoredReport.GetProperty("W46AdvancedClocks").GetInt32() == 0,
            "W45 leaves the partially open position and unfilled closing intent censored");
        check(money.GetProperty("RealizedFragments").GetArrayLength() == 1 &&
            money.GetProperty("RealizedFromStillOpenPositionsEur").GetDecimal() != 0m &&
            money.GetProperty("CompletedTripNetEur").GetDecimal() == 0m &&
            censored.GetProperty("CompletedTradesByWeek").GetProperty("2026-W45").GetInt32() == 0 &&
            end.GetProperty("CashEur").GetDecimal() == 300m + money.GetProperty("RealizedLedgerNetEur").GetDecimal() +
                money.GetProperty("RemainingOpenCashAdjustmentsEur").GetDecimal() &&
            censoredReport.GetProperty("Central").GetProperty("FullBookExhaustionAblation")
                .GetProperty("CompleteModeledNetDifferenceEur").ValueKind == JsonValueKind.Null,
            "partial cash reconciles without crediting a complete trip or publishing a complete economic delta");

        var openingOnly = Book(Report(new[] { Observation(lastBar, 15_000L) }), "Central", "COMBINED")
            .GetProperty("Financial").GetProperty("Boundary");
        check(openingOnly.GetProperty("RightCensored").GetBoolean() &&
            !openingOnly.GetProperty("CompleteModeledComparisonAvailable").GetBoolean() &&
            openingOnly.GetProperty("PendingIntents")[0].GetProperty("Kind").GetString() == "REQUEST_OPEN" &&
            openingOnly.GetProperty("EquityEur").GetDecimal() == 300m,
            "an unfilled entry is censored without turning known flat equity into a loss or a fill");
    }
}

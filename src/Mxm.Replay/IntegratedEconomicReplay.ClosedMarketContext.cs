using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    static AdditionalBars? ContextSource(SourceMarket market, NativeBarTimeframe timeframe)
        => timeframe switch
        {
            NativeBarTimeframe.M5 => new("INTEGRATED_OPEN_API_NATIVE_M5", market.M5),
            NativeBarTimeframe.M15 => new("INTEGRATED_OPEN_API_NATIVE_M15", market.M15),
            NativeBarTimeframe.H1 => new("INTEGRATED_OPEN_API_NATIVE_H1", market.H1),
            _ => market.AdditionalTimeframes?.GetValueOrDefault(timeframe.ToString())
        };

    static NativeBarContext HistoricalContext(SourceMarket market, SourceQuote quote)
    {
        long? witness = NativeClosedMarketContext.QuoteWitness(quote.At, quote.BidAt, quote.AskAt, 30_000L);
        return new(quote.At, NativeClosedMarketContext.CoverageWindows.Select(requirement =>
        {
            var series = ContextSource(market, requirement.Timeframe);
            return NativeClosedMarketContext.History(requirement, quote.At, witness,
                series?.Source ?? "UNAVAILABLE", series?.Bars);
        }).ToArray());
    }

    public static int RunStructural(string inputFile, string outputFile)
    {
        using var input = File.OpenRead(inputFile);
        var source = JsonSerializer.Deserialize<Source>(input, Json)
            ?? throw new ArgumentException("CLOSED_MARKET_ORIGINAL_SOURCE_MISSING");
        if (source.SourceRun != "44687919474" || source.Start != 1792972800000L ||
            source.End - source.Start != 3 * NativeCompletePolicy.Week || source.ProtocolSha256.Length != 64 ||
            source.Markets.Select(x => x.Name).Distinct(StringComparer.Ordinal).Count() != source.Markets.Length)
            throw new ArgumentException("CLOSED_MARKET_ORIGINAL_SOURCE_BOUNDARY");
        var markets = source.Markets.Select(m => new MarketStream(m)).ToArray();
        var fx = markets.Single(m => m.Source.Name == "EURUSD");
        var frames = new List<Ucp1Frame>();
        for (long at = source.Start + NativeIntegratedEconomicPolicy.ClockOffsetMs; at < source.End;
             at += NativeIntegratedLifecycle.IntervalMs)
        {
            var conversion = fx.At(at);
            var observed = conversion is null ? Array.Empty<Ucp1MarketFrame>() :
                markets.Select(m => m.Frame(at, conversion, closedContext: true)).OfType<Ucp1MarketFrame>().ToArray();
            frames.Add(new(at, observed));
        }
        var result = NativeStructuralResearch.Run(frames.ToArray(), source.Start, source.End,
            source.Markets.ToDictionary(x => x.Name, x => x.Contract, StringComparer.Ordinal));
        using var output = File.Create(outputFile);
        JsonSerializer.Serialize(output, new { source.SourceRun, source.ProtocolSha256,
            Coverage = markets.Select(m => new { m.Source.Name, m.Source.Class, m.Source.Contract.ObservedAtUtcMs,
                SourceMarks = m.Source.Quotes.Length, m.AcceptedMarks }).ToArray(), Result = result }, Json);
        return 0;
    }

    // New post-415 causal economic development: only W44-W45, never W46.
    // The underlying sealed source is recovered in the protected workflow,
    // but no broker order or re-execution of frozen W46 is performed.
    public static int RunExhaustionDevelopment(string inputFile, string outputFile)
    {
        using var input = File.OpenRead(inputFile);
        var source = JsonSerializer.Deserialize<Source>(input, Json)
            ?? throw new ArgumentException("POST415_ORIGINAL_SOURCE_MISSING");
        if (source.SourceRun != "44687919474" || source.Start != 1792972800000L ||
            source.End - source.Start != 3 * NativeCompletePolicy.Week ||
            source.ProtocolSha256.Length != 64 ||
            source.Markets.Select(m => m.Name).Distinct(StringComparer.Ordinal).Count() != source.Markets.Length)
            throw new ArgumentException("POST415_ORIGINAL_SOURCE_BOUNDARY");
        var markets = source.Markets.Select(m => new MarketStream(m)).ToArray();
        var fx = markets.Single(m => m.Source.Name == "EURUSD");
        var frames = new List<Ucp1Frame>();
        long developmentEnd = source.Start + 2 * NativeCompletePolicy.Week;
        for (long at = source.Start + NativeIntegratedEconomicPolicy.ClockOffsetMs;
             at < developmentEnd; at += NativeIntegratedLifecycle.IntervalMs)
        {
            var conversion = fx.At(at);
            var observed = conversion is null ? Array.Empty<Ucp1MarketFrame>() :
                markets.Select(m => m.Frame(at, conversion, closedContext: true))
                    .OfType<Ucp1MarketFrame>().ToArray();
            frames.Add(new(at, observed));
        }
        var result = NativeStructuralResearch.RunExhaustionDevelopment(frames.ToArray(),
            source.Start, source.End,
            source.Markets.ToDictionary(m => m.Name, m => m.Contract, StringComparer.Ordinal));
        using var output = File.Create(outputFile);
        JsonSerializer.Serialize(output, new { source.SourceRun, source.ProtocolSha256,
            DevelopmentScope = "EXPOSED_W44_W45_ONLY_NO_W46_FRAMES",
            Coverage = markets.Select(m => new { m.Source.Name, m.Source.Class,
                m.Source.Contract.ObservedAtUtcMs, SourceMarks = m.Source.Quotes.Length,
                m.AcceptedMarks }).ToArray(), Result = result }, Json);
        return 0;
    }

    public static int RunContextAudit(string inputFile, string outputFile)
    {
        using var input = File.OpenRead(inputFile);
        var source = JsonSerializer.Deserialize<Source>(input, Json)
            ?? throw new ArgumentException("CLOSED_CONTEXT_SOURCE_MISSING");
        if (source.Start <= 0 || source.End <= source.Start || source.ProtocolSha256.Length != 64 ||
            source.SourceRun.Length == 0 || !source.SourceRun.All(char.IsAsciiDigit))
            throw new ArgumentException("CLOSED_CONTEXT_SOURCE_SCOPE");

        var markets = source.Markets.Select(m => new
        {
            m.Name, m.Class, m.ActiveHours, m.RequestedTickHours,
            ObservedAccountTermsAt = m.Contract.ObservedAtUtcMs,
            CompleteQuoteIntervals = m.Quotes.Count(q => q.Path.Complete),
            QuoteClocks = m.Quotes.Length,
            SynchronizedDecisionContexts = m.Quotes.Count(q =>
            {
                var context = HistoricalContext(m, q);
                return context.Windows.Where(w => NativeClosedMarketContext.Duration(w.Timeframe) <= 3_600_000L)
                    .All(w => w.Ready) && context.For(NativeBarTimeframe.M1).ExpectedCloseAt ==
                    context.For(NativeBarTimeframe.M5).ExpectedCloseAt;
            }),
            Timeframes = NativeClosedMarketContext.CoverageWindows.Select(requirement =>
            {
                var series = ContextSource(m, requirement.Timeframe);
                var bars = series?.Bars;
                if (bars is not null && bars.Zip(bars.Skip(1)).Any(pair => pair.First.OpenAt >= pair.Second.OpenAt))
                    throw new ArgumentException("CLOSED_CONTEXT_UNSORTED_SOURCE_HISTORY");
                var counts = new Dictionary<string, int>();
                object? first = null, last = null;
                long lastRecordedClose = 0L;
                foreach (var quote in m.Quotes)
                {
                    if (quote.At < source.Start || quote.At >= source.End) continue;
                    long? witness = NativeClosedMarketContext.QuoteWitness(quote.At, quote.BidAt, quote.AskAt, 30_000L);
                    var window = NativeClosedMarketContext.History(requirement, quote.At, witness,
                        series?.Source ?? "UNAVAILABLE", bars);
                    string status = window.Status.ToString();
                    counts[status] = counts.GetValueOrDefault(status) + 1;
                    if (!window.Ready || window.ExpectedCloseAt == lastRecordedClose) continue;
                    lastRecordedClose = window.ExpectedCloseAt;
                    last = new { quote.At, quote.BidAt, quote.AskAt, window.WitnessAt, window.ExpectedCloseAt,
                        FirstOpenAt = window.Bars[0].OpenAt, UsedBars = window.Bars.Length,
                        Sha256 = window.ValuesSha256() };
                    first ??= last;
                }
                return new { Timeframe = requirement.Timeframe.ToString(), requirement.Count,
                    Source = series?.Source ?? "UNAVAILABLE", Collected = bars?.Length ?? 0,
                    FirstCollectedOpen = bars?.FirstOrDefault()?.OpenAt, LastCollectedClose = bars?.LastOrDefault()?.CloseAt,
                    StatusCounts = counts, FirstReady = first, LastReady = last };
            }).ToArray()
        }).ToArray();
        using var output = File.Create(outputFile);
        JsonSerializer.Serialize(output, new { source.SourceRun, source.ProtocolSha256, source.Start, source.End,
            Markets = markets, MarketAccountTerms = "CAPTURE_DATE_SNAPSHOT", Chronology = "EXPOSED",
            EconomicEvaluations = 0, BrokerOrders = 0, CloudActivated = false }, Json);
        return 0;
    }

    public static int RunFundedActionValue(string inputFile, string outputFile)
    {
        using var input = File.OpenRead(inputFile);
        var inputHash = Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(input)).ToLowerInvariant();
        input.Position = 0;
        var source = JsonSerializer.Deserialize<Source>(input, Json)
            ?? throw new ArgumentException("FUNDED_ACTION_SOURCE_MISSING");
        if (source.Start != NativeFundedActionResearch.Start || source.End != NativeFundedActionResearch.End ||
            source.End > DateTimeOffset.UtcNow.ToUnixTimeMilliseconds() ||
            source.SourceRun.Length == 0 || !source.SourceRun.All(char.IsAsciiDigit) ||
            source.ProtocolSha256.Length != 64 || !source.ProtocolSha256.All(Uri.IsHexDigit) ||
            source.Markets.Select(m => m.Name).Distinct(StringComparer.Ordinal).Count() != source.Markets.Length ||
            source.Markets.Any(m => !NativeFundedActionResearch.Universe.Contains(m.Name, StringComparer.Ordinal)))
            throw new ArgumentException("FUNDED_ACTION_PROSPECTIVE_SOURCE_SCOPE");
        var markets = source.Markets.Select(m => new MarketStream(m)).ToArray();
        var currency = markets.SingleOrDefault(m => m.Source.Name == "EURUSD")
            ?? throw new ArgumentException("FUNDED_ACTION_EUR_CONVERSION_SOURCE_MISSING");
        var frames = new List<Ucp1Frame>();
        for (long at = source.Start + NativeIntegratedEconomicPolicy.ClockOffsetMs; at < source.End;
             at += NativeIntegratedLifecycle.IntervalMs)
        {
            var fx = currency.At(at);
            var observations = fx is null || NativeClosedMarketContext.QuoteWitness(at, fx.BidAt, fx.AskAt, 30_000L) is null
                ? Array.Empty<Ucp1MarketFrame>()
                : markets.Where(m => m.Source.Contract.ObservedAtUtcMs > 0 && m.Source.Contract.ObservedAtUtcMs <= at)
                    .Select(m => m.Frame(at, fx, closedContext: true)).OfType<Ucp1MarketFrame>().ToArray();
            frames.Add(new(at, observations));
        }
        if (frames.All(f => f.Markets.Length == 0))
            throw new ArgumentException("FUNDED_ACTION_CAUSAL_QUOTE_AND_CONTRACT_COVERAGE_MISSING");
        var result = NativeFundedActionResearch.Run(frames.ToArray(),
            source.Markets.ToDictionary(m => m.Name, m => m.Contract, StringComparer.Ordinal));
        using var output = File.Create(outputFile);
        JsonSerializer.Serialize(output, new { source.SourceRun, source.ProtocolSha256, InputSha256 = inputHash,
            Coverage = markets.Select(m => new { m.Source.Name, m.Source.Class, m.Source.Contract.ObservedAtUtcMs,
                SourceMarks = m.Source.Quotes.Length, m.AcceptedMarks }).ToArray(), Result = result }, Json);
        return 0;
    }
}

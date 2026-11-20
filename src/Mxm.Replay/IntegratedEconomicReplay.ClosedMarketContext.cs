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
}

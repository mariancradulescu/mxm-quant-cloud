using System.Text.Json;
using Mxm.Core;

internal static partial class Cpe1OriginalIntegratedRunner
{
    sealed record FundingAuditBook(string Policy,decimal Stress,int Detected,int UnknownChecks,
        long LastClose,Ucp1Episode[] UnpricedEpisodes);

    // Recover timestamps from witnessed source frames and immutable positions.
    // This path never constructs or advances a portfolio engine.
    internal static int AuditFundingSource(string sourceFile,string originalFile,string outputFile)
    {
        var sourceInput=JsonSerializer.Deserialize<Cpe1SourceInput>(File.ReadAllText(sourceFile),Json)
            ??throw new InvalidDataException("CPE1_AUDIT_SOURCE_MISSING");
        using var original=JsonDocument.Parse(File.ReadAllBytes(originalFile));
        var result=original.RootElement;
        if(!result.GetProperty("OriginalSourceRuns").EnumerateArray().Select(x=>x.GetString())
            .SequenceEqual(sourceInput.Tape.SourceRuns))
            throw new InvalidDataException("CPE1_AUDIT_ORIGINAL_SOURCE_BINDING");
        var books=result.GetProperty("BookSummaries").EnumerateArray().Select(book=>{
            if(book.GetProperty("Held").GetInt32()!=0 || book.GetProperty("Pending").GetInt32()!=0)
                throw new InvalidDataException("CPE1_AUDIT_REQUIRES_CLOSED_ORIGINAL_BOOK");
            var report=book.GetProperty("ConditionalFullEngineReport");
            var unknownChecks=report.GetProperty("reasons")
                .TryGetProperty("CPE1_FINANCING_UNKNOWN_RISK_STILL_HELD",out var checks)?checks.GetInt32():0;
            var episodes=book.GetProperty("IndividualEpisodes").Deserialize<Ucp1Episode[]>(Json)
                ??throw new InvalidDataException("CPE1_AUDIT_ORIGINAL_EPISODES");
            if(episodes.Any(x=>x.EconomicEvidence is null || x.Integrated?.PartialReduction!=false))
                throw new InvalidDataException("CPE1_AUDIT_REQUIRES_ORIGINAL_WHOLE_EPISODES");
            return new FundingAuditBook(book.GetProperty("Policy").GetString()!,
                book.GetProperty("Stress").GetDecimal(),report.GetProperty("proposed").GetInt32(),
                unknownChecks,episodes.Select(x=>x.CloseAt).DefaultIfEmpty().Max(),
                episodes.Where(x=>x.EconomicEvidence!.ConditionalNetKnown==false).ToArray());
        }).ToArray();
        var recovered=sourceInput.Funding.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        var sources=sourceInput.Tape.Markets.ToDictionary(x=>x.Symbol,x=>new Source(x),StringComparer.Ordinal);
        var contracts=sources.Values.Select(source=>(Source:source,Contract:Contract(source.Market.Terms,recovered)))
            .Where(x=>x.Contract is not null).ToDictionary(x=>x.Source.Market.Symbol,
                x=>(x.Source,x.Contract!),StringComparer.Ordinal).OrderBy(x=>x.Key,StringComparer.Ordinal).ToArray();
        var times=sources.Values.SelectMany(x=>x.M5Bars.Select(b=>b.OpenAt)).Distinct().Order().ToArray();
        if(times.Length!=result.GetProperty("GenuineM5SourceClocks").GetInt32())
            throw new InvalidDataException("CPE1_AUDIT_CANNOT_RECONCILE_SOURCE_CLOCK_COUNT");
        var unknownTimes=new Dictionary<(decimal Stress,string Id),List<long>>();
        var detectedByClock=new List<(long Clock,int Detected)>();
        var lastSignalBar=new Dictionary<string,long>(StringComparer.Ordinal);
        var unknownQuotes=new Dictionary<string,int>(StringComparer.Ordinal);
        foreach(long at in times)
        {
            foreach(var source in sources.Values)source.Advance(at);
            if(!sources["EURUSD"].OpenM5.TryGetValue(at,out var fx))continue;
            var frame=SourceFrame(at,fx,1m,contracts,unknownQuotes);
            int detected=0;
            foreach(var market in frame.Markets)
            {
                var signals=Ucp1CausalSignals.Describe(market,at);
                if(signals.Length==0 || lastSignalBar.GetValueOrDefault(market.Symbol)>=signals[0].LastCompletedM5At)
                    continue;
                lastSignalBar[market.Symbol]=signals[0].LastCompletedM5At;
                detected+=signals.Length;
            }
            if(detected>0)detectedByClock.Add((at,detected));
            foreach(var book in books)
            foreach(var episode in book.UnpricedEpisodes)
            {
                if(at<=episode.OpenAt || at>episode.CloseAt)continue;
                var market=frame.Markets.FirstOrDefault(x=>x.Symbol==episode.Symbol);
                if(market is null)continue;
                // The exact frozen funding availability predicate only uses these FX values for
                // validated conversion. Positive, ordered conversion remains true in every stress.
                if(NativeUnifiedPortfolioEngine.Cpe1ObservedFunding(market.Contract,market.Quote,
                    episode.OpenAt,episode.Side,episode.Units,at) is not null)continue;
                if(!unknownTimes.TryGetValue((book.Stress,episode.PositionId),out var clocks))
                    unknownTimes.Add((book.Stress,episode.PositionId),clocks=new());
                clocks.Add(at);
            }
        }
        int allDetected=detectedByClock.Sum(x=>x.Detected);
        if(unknownQuotes.Count!=0 || result.GetProperty("UnknownCurrentCostQuotes").EnumerateObject().Any()
            || books.Any(book=>book.Detected!=allDetected))
            throw new InvalidDataException("CPE1_AUDIT_CANNOT_RECONCILE_ORIGINAL_DETECTOR");
        var audit=books.Select(book=>{
            var episodes=book.UnpricedEpisodes.Select(e=>{
                var clocks=unknownTimes[(book.Stress,e.PositionId)];
                return new {e.PositionId,e.Symbol,e.Side,e.Units,e.OpenAt,e.CloseAt,
                    FirstUnknownAt=clocks[0],LastUnknownAt=clocks[^1],UnknownChecks=clocks.Count};
            }).OrderBy(x=>x.FirstUnknownAt).ThenBy(x=>x.OpenAt).ThenBy(x=>x.PositionId,StringComparer.Ordinal)
                .ToArray();
            if(episodes.Sum(x=>x.UnknownChecks)!=book.UnknownChecks)
                throw new InvalidDataException("CPE1_AUDIT_CANNOT_RECONCILE_ORIGINAL_UNKNOWN_CHECKS");
            long? first=episodes.FirstOrDefault()?.FirstUnknownAt;
            return new {book.Policy,book.Stress,FirstGlobalBlockAt=first,book.LastClose,
                FinancialEligibilityAfterBlock="UNKNOWN_NO_AUTHENTIC_DEBIT_CEILING",
                SuppressedExclusivelyByImplementation=(int?)null,
                DetectedAtBlock=first.HasValue?detectedByClock.Where(x=>x.Clock==first).Sum(x=>x.Detected):(int?)null,
                DetectedAfterBlock=first.HasValue?detectedByClock.Where(x=>x.Clock>first).Sum(x=>x.Detected):(int?)null,
                DetectedAfterFlat=first.HasValue?detectedByClock.Where(x=>x.Clock>book.LastClose).Sum(x=>x.Detected):(int?)null,
                DetectedBeforeBlock=first.HasValue?detectedByClock.Where(x=>x.Clock<first).Sum(x=>x.Detected):(int?)null,
                Episodes=episodes};
        }).ToArray();
        File.WriteAllText(outputFile,JsonSerializer.Serialize(new {
            GenuineSourceClocks=times.Length,AllDetected=allDetected,EvaluatedPolicies=0,
            OriginalUnknownChecksReconciled=true,OriginalDetectorCountsReconciled=true,
            EngineContracts=contracts.Select(x=>x.Value.Item2).ToArray(),
            Books=audit,BrokerRequests=0,OrderRequests=0,CloudActivated=false},Json)+"\n");
        return 0;
    }
}

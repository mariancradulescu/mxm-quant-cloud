using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    // Inspect conditional evidence usability, without advancing any portfolio.
    public static int RunFundingCoverage(string sourcePath,string tapePath,string planPath,string outputPath)
    {
        if(File.Exists(outputPath))throw new InvalidDataException("FUNDING_COVERAGE_OUTPUT_EXISTS");
        byte[] raw=File.ReadAllBytes(sourcePath);
        var input=JsonSerializer.Deserialize<EerInput>(raw,Json)!;
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=new EerProtectionTape(tapePath)};
        using var plan=JsonDocument.Parse(File.ReadAllBytes(planPath));
        var rows=new List<object>();int supported=0,unresolved=0;
        foreach(var target in plan.RootElement.GetProperty("Targets").EnumerateArray())
        {
            string name=target.GetProperty("Symbol").GetString()!,side=target.GetProperty("Side").GetString()!;
            long at=target.GetProperty("At").GetInt64();
            var dependencies=target.GetProperty("DependentSymbols").EnumerateArray().Select(x=>x.GetString()!)
                .Distinct(StringComparer.Ordinal).Select(symbol=>
                {
                    var terms=input.Markets.Single(x=>x.Market.Name==symbol).Market.DatedDevelopment!;
                    var quote=source.Charge(symbol,terms.Contract.QuoteAsset,at);
                    bool ready=(terms.Contract.SwapCalculationType!=1||quote.Bid.HasValue)&&quote.QuoteToEur is not null;
                    return new {Symbol=symbol,QuoteAsset=terms.Contract.QuoteAsset,ConditionallyUsable=ready};
                }).ToArray();
            bool ready=dependencies.Length>0&&dependencies.All(x=>x.ConditionallyUsable);
            if(ready)supported++;else unresolved++;
            rows.Add(new {Symbol=name,At=at,Side=side,Dependencies=dependencies,
                Status=ready?"CONDITIONAL_NATIVE_MARKET_TIME_EVIDENCE":"UNRESOLVED_NATIVE_EVIDENCE",
                FreshQuoteAtClosedMarketInvented=false});
        }
        File.WriteAllBytes(outputPath,JsonSerializer.SerializeToUtf8Bytes(new
        {
            SourceSha256=GeneralSha(raw),ConservativeAgeTargets=rows.Count,
            ConditionallySupportedTargets=supported,UnresolvedTargets=unresolved,Rows=rows,
            PoliciesExecuted=0,SourceBrokerRequests=0,Orders=0,CloudActivated=false,
            HistoricalTariffCertified=false,EconomicPromotionCertified=false
        },Json));
        Console.WriteLine($"NATIVE_PREVENTIVE_COVERAGE supported={supported} unresolved={unresolved}");
        return 0;
    }
}

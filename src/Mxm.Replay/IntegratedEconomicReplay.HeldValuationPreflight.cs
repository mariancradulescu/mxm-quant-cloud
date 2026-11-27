using System.Text.Json;
using Mxm.Core;
internal static partial class IntegratedEconomicReplay
{
    public static int RunHeldValuationPreflight(string sourcePath,string tapePath,string registryPath,string scope,string output)
    {
        var sb=File.ReadAllBytes(sourcePath);var rb=File.ReadAllBytes(registryPath);
        string sha=GeneralSha(sb),registrySha=GeneralSha(rb);
        if(registrySha!="576df0e4662e70ad8fb9d9cd8f2720ef71d67aa1936f6503680d92d496044155")
            throw new InvalidDataException("HELD_PREFLIGHT_DEMAND_SHA");
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        using var doc=JsonDocument.Parse(rb);
        var report=doc.RootElement.GetProperty("ScopeReports").EnumerateArray()
            .Single(x=>x.GetProperty("Scope").GetString()==scope);
        if(report.GetProperty("SourceSha256").GetString()!=sha)
            throw new InvalidDataException("HELD_PREFLIGHT_ORIGINAL_SOURCE_SHA");
        var demands=new Dictionary<(string Symbol,long At),HashSet<string>>();
        foreach(var row in report.GetProperty("Rows").EnumerateArray())
        {
            string symbol=row.GetProperty("Symbol").GetString()!,reason=row.GetProperty("Reason").GetString()!;
            int count=0;
            foreach(var range in row.GetProperty("ObservedIntervals").EnumerateArray())
            {
                long first=range.GetProperty("First").GetInt64(),last=range.GetProperty("Last").GetInt64();
                int n=range.GetProperty("Count").GetInt32();
                if(n<=0||first<input.Start||last>input.End||last-first!=(n-1)*EurStep)
                    throw new InvalidDataException("HELD_PREFLIGHT_INTERVAL");
                for(int i=0;i<n;i++)
                {
                    var key=(symbol,first+i*EurStep);
                    if(!demands.TryGetValue(key,out var reasons))demands.Add(key,reasons=new(StringComparer.Ordinal));
                    if(!reasons.Add(reason))throw new InvalidDataException("HELD_PREFLIGHT_DUPLICATE");
                    count++;
                }
            }
            if(count!=row.GetProperty("DistinctClocks").GetInt32())throw new InvalidDataException("HELD_PREFLIGHT_COUNT");
        }
        var evidence=new EerEvidence(input){MarketTimeFx=true,ValuationTape=new EerProtectionTape(tapePath)};
        var rows=new List<object>();var counts=new Dictionary<string,int>();int resolved=0;
        foreach(var (key,reasons) in demands.OrderBy(x=>x.Key.At).ThenBy(x=>x.Key.Symbol,StringComparer.Ordinal))
        {
            evidence.BeginHistoricalClock();
            var result=evidence.InspectHeldMark(key.Symbol,key.At);
            counts[result.Status]=counts.GetValueOrDefault(result.Status)+1;
            if(result.EvidenceSha256 is not null)resolved++;
            rows.Add(new {result.Symbol,result.At,result.Status,result.BidAt,result.AskAt,result.EvidenceSha256,
                result.RequiredAsset,result.OfficialRouteSymbols,OriginalReasons=reasons.Order(StringComparer.Ordinal).ToArray()});
        }
        File.WriteAllBytes(output,JsonSerializer.SerializeToUtf8Bytes(new{
            Study="OWNER_HELD_VALUATION_PREFLIGHT_1",Scope=scope,OriginalSourceSha256=sha,RegistrySha256=registrySha,
            DistinctSymbolClocks=demands.Count,ResolvedConditionalMarks=resolved,Unresolved=demands.Count-resolved,
            StatusCounts=counts,Rows=rows,SourceBrokerRequests=0,OriginalPoliciesReplayed=0,
            EquityRecovered=false,NoNewAdmissionCertified=true,Orders=0,CloudActivated=false},Json));
        return 0;
    }
}

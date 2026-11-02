using System.Text.Json;
using System.Security.Cryptography;
if (args.Length != 2) return 2;
try
{
    var bytes = File.ReadAllBytes(args[0]);
    using var doc = JsonDocument.Parse(bytes);
    var root = doc.RootElement;
    if (root.GetProperty("source").GetString() != "Pepperstone-cTrader-OpenAPI" || !root.GetProperty("readOnly").GetBoolean()) return 3;
    var seen = new HashSet<(string,long)>();
    int count=0;
    foreach (var bar in root.GetProperty("bars").EnumerateArray())
    {
        var symbol=bar.GetProperty("symbol").GetString() ?? throw new Exception();
        var t=bar.GetProperty("openTime").GetInt64();
        var available=bar.GetProperty("availableTime").GetInt64();
        var o=bar.GetProperty("open").GetInt64(); var h=bar.GetProperty("high").GetInt64();
        var l=bar.GetProperty("low").GetInt64(); var c=bar.GetProperty("close").GetInt64();
        if (!seen.Add((symbol,t)) || available!=t+3600000 || available>root.GetProperty("end").GetInt64() ||
            t<root.GetProperty("start").GetInt64() || l<=0 || o<l || o>h || c<l || c>h || bar.GetProperty("tickVolume").GetInt64()<0) return 4;
        count++;
    }
    if (count==0) return 5;
    // A distinct native C# causal H1 research mechanism runs on source-admitted
    // bars in chronological per-symbol order, never emits orders and never
    // treats candidate counts as NET performance or independent confirmation.
    var bundleSha=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
    var researchers=new Dictionary<string,Mxm.Core.CausalRangePressureResearch>();
    int causalForecastCount=0;
    foreach(var bar in root.GetProperty("bars").EnumerateArray()
        .OrderBy(x=>x.GetProperty("symbol").GetString(),StringComparer.Ordinal)
        .ThenBy(x=>x.GetProperty("openTime").GetInt64()))
    {
        var name=bar.GetProperty("symbol").GetString()!;
        if(!researchers.TryGetValue(name,out var researcher))
        {
            researcher=new Mxm.Core.CausalRangePressureResearch();
            researchers.Add(name,researcher);
        }
        var open=DateTimeOffset.FromUnixTimeMilliseconds(
            bar.GetProperty("openTime").GetInt64()).UtcDateTime;
        var available=DateTimeOffset.FromUnixTimeMilliseconds(
            bar.GetProperty("availableTime").GetInt64()).UtcDateTime;
        var candidate=researcher.Observe(new Mxm.Core.CompletedH1Candle(
            name,open,available,
            bar.GetProperty("open").GetDecimal(),
            bar.GetProperty("high").GetDecimal(),
            bar.GetProperty("low").GetDecimal(),
            bar.GetProperty("close").GetDecimal(),
            bar.GetProperty("tickVolume").GetInt64(),bundleSha));
        if(candidate!=null)causalForecastCount++;
    }
    File.WriteAllText(args[1],JsonSerializer.Serialize(new { sourceSha256=bundleSha,bars=count,causalResearchForecasts=causalForecastCount,causalResearchStatus=Mxm.Core.CausalRangePressureResearch.ResearchOnly,
        status="SOURCE_VALIDATED_NOT_EXECUTION_REPLAY",economicQualification=false,
        missing="Historical executable spreads, costs, FX, financing, margin and qualified strategy" }));
    return 0;
}
catch { return 1; }

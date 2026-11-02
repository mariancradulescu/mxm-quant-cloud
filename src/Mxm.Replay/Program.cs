using System.Text.Json;
using System.Security.Cryptography;
if (args.Length == 3 && args[2] == "--economic-source")
{
    try
    {
        using var economic=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var sourceReceipt=Mxm.Core.EconomicSourceAdmission.ReadReceipt(economic.RootElement);
        File.WriteAllText(args[1],JsonSerializer.Serialize(sourceReceipt));
        return 0;
    }
    catch { return 6; }
}
if (args.Length != 2 && !(args.Length == 3 && args[2] == "--score-causal")) return 2;
var scoreOnly = args.Length == 3;
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
    var actualSourceClocks=new List<Mxm.Core.SourceBarClock>();
    var pending=new Dictionary<string,Mxm.Core.ResearchForecast>();
    var lastCloses=new Dictionary<string,decimal>();
    var scorer=new Mxm.Core.CausalForecastScoreLedger();
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
        actualSourceClocks.Add(new Mxm.Core.SourceBarClock(
            name,open,available,TimeSpan.FromHours(1),bundleSha));
        var close=bar.GetProperty("close").GetDecimal();
        // Score only predictions made BEFORE this target completed.
        // A missing interval is never converted into an invented outcome.
        if (scoreOnly && pending.TryGetValue(name,out var prior) &&
            prior.TargetBarEndsUtc==available &&
            lastCloses.TryGetValue(name,out var priorClose))
        {
            var target=close>priorClose?1m:close<priorClose?0m:.5m;
            scorer.Score(prior.ProbabilityUp,target);
        }
        var candidate=researcher.Observe(new Mxm.Core.CompletedH1Candle(
            name,open,available,
            bar.GetProperty("open").GetDecimal(),
            bar.GetProperty("high").GetDecimal(),
            bar.GetProperty("low").GetDecimal(),
            bar.GetProperty("close").GetDecimal(),
            bar.GetProperty("tickVolume").GetInt64(),bundleSha));
        if(candidate!=null)causalForecastCount++;
        if (scoreOnly)
        {
            pending.Remove(name);
            if (candidate is not null) pending[name]=candidate;
            lastCloses[name]=close;
        }
    }
    var calendar=Mxm.Core.CausalSourceCalendar.Assess(actualSourceClocks);
    if(scoreOnly)
    {
        var score=scorer.Summarize();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            schema="mxm.causal-range-pressure-authentic-observation-only.v1",
            forecastScored=score.Count,
            publicScoreAdmitted=score.Count>=100,
            meanBrier=score.Count>=100 ? (decimal?)score.MeanBrier : null,
            neutralMeanBrier=score.Count>=100 ? (decimal?)score.BaselineMeanBrier : null,
            brierSkill=score.Count>=100 ? (decimal?)score.BrierSkillVersusNeutral : null,
            qualification=score.Qualification,
            sourceBars=count,
            sourceObservedWeeks=calendar.DistinctObservedIsoWeeks,
            netEurQualified=false,
            hard21BrokerOrders=0,
            twelveMonthsIndependentConfirmation=false,
            ordersSubmitted=0
        }));
        return 0;
    }
    File.WriteAllText(args[1],JsonSerializer.Serialize(new {
        sourceSha256=bundleSha,bars=count,
        observedCalendarWeeks=calendar.DistinctObservedIsoWeeks,
        observedCalendarDiscontinuities=calendar.DiscontinuitiesBetweenSuccessiveSameSymbolBars,
        twelveCalendarMonthsObserved=calendar.TwelveCalendarMonthsObservedForAnySymbol,
        calendarStatus=calendar.Status,
        causalResearchForecasts=causalForecastCount,causalResearchStatus=Mxm.Core.CausalRangePressureResearch.ResearchOnly,
        status="SOURCE_VALIDATED_NOT_EXECUTION_REPLAY",economicQualification=false,
        missing="Historical executable spreads, costs, FX, financing, margin and qualified strategy" }));
    return 0;
}
catch { return 1; }

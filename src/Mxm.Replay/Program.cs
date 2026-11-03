using System.Text.Json;
using System.Security.Cryptography;
if (args.Length == 3 && args[2] == "--holding-market-context")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.HoldingPortfolioRisk.MarketContext(d.RootElement)));return 0;
    } catch { return 18; }
}
if (args.Length == 3 && args[2] == "--assess-holding-risk")
{
    try {
        var r=JsonSerializer.Deserialize<Mxm.Core.HoldingRiskInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.HoldingPortfolioRisk.Assess(r)));return 0;
    } catch { return 17; }
}
if (args.Length == 3 && args[2] == "--value-portfolio-source")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.MultiAssetValuation.Assess(d.RootElement)));
        return 0;
    } catch { return 16; }
}
if (args.Length == 3 && args[2] == "--estimate-portfolio-opportunities")
{
    try {
        var r=JsonSerializer.Deserialize<Mxm.Core.ResearchOrchestrationRequest>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.OpportunityOrchestrator.Estimate(r)));
        return 0;
    } catch { return 14; }
}
if (args.Length == 3 && args[2] == "--economic-portfolio-plan")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var bars=Mxm.Core.RegimeDiscovery.Read(d.RootElement);
        var plan=Mxm.Core.JointOpportunityResearch.Describe(bars)
            .Select(r=>new {r.Candidate,r.Symbol,r.Clock,r.Exit,r.Side});
        File.WriteAllText(args[1],JsonSerializer.Serialize(plan));return 0;
    } catch { return 15; }
}
if (args.Length == 3 && args[2] == "--orchestrate-opportunities")
{
    try {
        var r=JsonSerializer.Deserialize<Mxm.Core.OrchestrationRequest>(File.ReadAllBytes(args[0]), new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.OpportunityOrchestrator.Select(r.Clock,r.Account,r.Baseline,r.Opportunities)));
        return 0;
    } catch { return 13; }
}
if (args.Length == 3 && args[2] == "--joint-opportunity-research")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.JointOpportunityResearch.Assess(d.RootElement)));
        return 0;
    } catch { return 12; }
}
if (args.Length == 3 && args[2].StartsWith("--neighbour-"))
{
    try {using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        object result=args[2] switch {
            "--neighbour-plan"=>Mxm.Core.NeighbourFxResearch.MakePlan(d.RootElement).Plans,
            "--neighbour-confirm-plan"=>Mxm.Core.NeighbourFxResearch.MakePlan(d.RootElement,true).Plans,
            "--neighbour-selection"=>Mxm.Core.NeighbourFxResearch.Evaluate(d.RootElement),
            "--neighbour-confirmation"=>Mxm.Core.NeighbourFxResearch.Evaluate(d.RootElement,true),
            _=>throw new ArgumentException()};
        File.WriteAllText(args[1],JsonSerializer.Serialize(result));return 0;
    }catch{return 11;}
}
if (args.Length == 3 && args[2] == "--regime-discovery")
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.RegimeDiscovery.Assess(d.RootElement)));
        return 0;
    } catch { return 11; }
}
if (args.Length == 3 && args[2].StartsWith("--flow-"))
{
    try {
        using var d=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        object result=args[2] switch {
            "--flow-plan"=>Mxm.Core.CausalFlowResearch.Propose(d.RootElement),
            "--flow-confirm-plan"=>Mxm.Core.CausalFlowResearch.Propose(d.RootElement,true),
            "--flow-selection"=>Mxm.Core.CausalFlowResearch.Evaluate(d.RootElement),
            "--flow-confirmation"=>Mxm.Core.CausalFlowResearch.Evaluate(d.RootElement,true),
            _=>throw new ArgumentException()};
        File.WriteAllText(args[1],JsonSerializer.Serialize(result));return 0;
    } catch { return 10; }
}
if (args.Length == 3 && (args[2] == "--intraday-plan" || args[2] == "--intraday-net"))
{
    try {
        using var d=System.Text.Json.JsonDocument.Parse(System.IO.File.ReadAllBytes(args[0]));
        object r=args[2]=="--intraday-plan" ? Mxm.Core.IntradayReversalNet.Propose(Mxm.Core.IntradayReversalNet.Bars(d.RootElement)) : Mxm.Core.IntradayReversalNet.Assess(d.RootElement);
        System.IO.File.WriteAllText(args[1],System.Text.Json.JsonSerializer.Serialize(r));
        return 0;
    } catch { return 9; }
}
if (args.Length == 3 && args[2] == "--economic-net-coverage")
{
    try
    {
        using var doc=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var result=Mxm.Core.AuthenticatedNetCoverage.Examine(doc.RootElement);
        File.WriteAllText(args[1],JsonSerializer.Serialize(result));
        return 0;
    }
    catch { return 8; }
}
if (args.Length == 3 && args[2] == "--economic-screen")
{
    try
    {
        using var input=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var root=input.RootElement;
        _=Mxm.Core.EconomicSourceAdmission.ReadReceipt(root);
        var contracts=root.GetProperty("brokerContract");
        var groups=root.GetProperty("bars").EnumerateArray()
            .GroupBy(x=>(
                symbol:x.GetProperty("symbol").GetString()!,
                resolution:x.GetProperty("resolution").GetString()!,
                duration:x.GetProperty("periodMinutes").GetInt32()
            )).ToArray();
        var results=new List<object>();
        foreach(var g in groups.OrderBy(x=>x.Key.symbol,StringComparer.Ordinal)
                                .ThenBy(x=>x.Key.resolution,StringComparer.Ordinal))
        {
            var contract=contracts.GetProperty(g.Key.symbol);
            var pip=contract.GetProperty("pipPosition");
            if(pip.ValueKind!=JsonValueKind.Number)
                throw new ArgumentException("UNAVAILABLE_BROKER_PIP_SCALE");
            var bars=g.Select(b=>new Mxm.Core.PriceOnlyBar(
                g.Key.symbol,g.Key.resolution,
                DateTimeOffset.FromUnixTimeMilliseconds(b.GetProperty("openTime").GetInt64()).UtcDateTime,
                DateTimeOffset.FromUnixTimeMilliseconds(b.GetProperty("availableTime").GetInt64()).UtcDateTime,
                g.Key.duration,b.GetProperty("open").GetInt64(),
                b.GetProperty("high").GetInt64(),b.GetProperty("low").GetInt64(),
                b.GetProperty("close").GetInt64()));
            var gross=Mxm.Core.EconomicBreakoutProbe.Assess(bars,pip.GetInt32());
            // Never claim qualified trades or prefer one profitable instrument.
            bool admitted=gross.Episodes>=20;
            results.Add(new {
                symbol=g.Key.symbol,resolution=g.Key.resolution,
                priceOnlyCompleteProxies=gross.Episodes,
                observedWeeksWithProxies=gross.ObservedExitWeeks,
                weeksWith21PriceOnlyProxies=gross.WeeksWith21Proxies,
                meanGrossPips=admitted?gross.MeanGrossPips:null,
                medianGrossPips=admitted?gross.MedianGrossPips:null,
                positiveFraction=admitted?gross.PositiveFraction:null,
                earlySliceGrossPips=admitted?gross.EarlySliceGrossPips:null,
                middleSliceGrossPips=admitted?gross.MiddleSliceGrossPips:null,
                lateSliceGrossPips=admitted?gross.LateSliceGrossPips:null,
                status=admitted?gross.Verdict:"INSUFFICIENT_PRICE_ONLY_EPISODES"
            });
        }
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {
            schema="mxm-new-fixed-breakout-price-only-v1",
            sourceRunId=41476636915L,
            modelFrozen="PR11_FIXED_12_BAR_CLOSE_BREAKOUT_NEXT_BAR_OPEN_FOUR_BAR_CLOSE",
            developmentOnly=true,
            reportedPerSymbolNotCherryPicked=true,
            results,
            historicalBidAskNotAnExecutionPrice=true,
            netInEur=null as decimal?,
            funded200EurProven=false,
            hard21BrokerRoundTripsProven=false,
            independentConfirmation=false,
            ordersSubmitted=0
        }));
        return 0;
    }
    catch { return 7; }
}
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

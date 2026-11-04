using System.Text.Json;
using System.Security.Cryptography;
if (args.Length == 3 && args[2] == "--multiscale-conditional-program")
{
    try {
        var input=System.Text.Json.JsonSerializer.Deserialize<Mxm.Core.MultiscaleInput>(File.ReadAllBytes(args[0]),
            new System.Text.Json.JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],System.Text.Json.JsonSerializer.Serialize(Mxm.Core.MultiscaleConditionalResearch.Evaluate(input)));return 0;
    } catch (Exception ex) { Console.Error.WriteLine(ex.GetType().Name);return 30; }
}
if (args.Length == 3 && args[2] == "--carry-cycle-preflight")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.CarryPreflightInput>(File.ReadAllBytes(args[0]),new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.CarryCyclePreflight.Evaluate(input)));return 0;
    } catch { return 28; }
}
if (args.Length == 3 && args[2] == "--native-risk-observations")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.PortfolioRiskMark[][]>(File.ReadAllBytes(args[0]),new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        var output=input.Select(marks=>{
            var session=new Mxm.Core.NativeFundedSession(marks[0].AccountBinding);var results=new List<Mxm.Core.PortfolioRiskReport>();
            foreach(var m in marks){var r=session.ObservePortfolio(m,m.AvailableAt);session=Mxm.Core.NativeFundedSession.Restore(session.Checkpoint(),m.AccountBinding);
                var same=session.ObservePortfolio(m,m.AvailableAt);if(JsonSerializer.Serialize(r)!=JsonSerializer.Serialize(same))throw new ArgumentException("RISK_RESTART_PARITY");results.Add(r);}
            return new {Reports=results,State=session.PortfolioObservation.State,RestartMatched=true};
        }).ToArray();File.WriteAllText(args[1],JsonSerializer.Serialize(output));return 0;
    } catch { return 29; }
}
if (args.Length == 3 && args[2] == "--native-frozen-money-recovery")
{
    try {
        var cases=JsonSerializer.Deserialize<Mxm.Core.FrozenMoneyRecoveryCase[]>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.FrozenMoneyRecoveryReceipt.Receive(cases)));return 0;
    } catch { return 27; }
}
if (args.Length == 3 && args[2] == "--auction-source-support")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.AuctionInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        var episodes=Mxm.Core.AuctionInventoryResearch.Episodes(input);
        File.WriteAllText(args[1],JsonSerializer.Serialize(input.Sessions.Select(s=>new {s.Symbol,FeatureEpisodes=episodes.Count(x=>x.Symbol==s.Symbol),KnownLabels=episodes.Count(x=>x.Symbol==s.Symbol&&x.Outcome.HasValue)})));return 0;
    } catch { return 26; }
}
if (args.Length == 3 && args[2] == "--auction-inventory-program")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.AuctionInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.AuctionInventoryResearch.Evaluate(input)));return 0;
    } catch { return 24; }
}
if (args.Length == 3 && args[2] == "--broker-identity-reception")
{
    try {
        using var root=JsonDocument.Parse(File.ReadAllBytes(args[0]));
        var snapshot=JsonSerializer.Deserialize<Mxm.Core.BrokerIdentitySnapshot>(root.RootElement.GetProperty("Snapshot").GetRawText(),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})!;
        var session=new Mxm.Core.NativeFundedSession(snapshot.AccountBinding);
        decimal? cash=root.RootElement.GetProperty("BrokerCashEur").ValueKind==JsonValueKind.Null?null:decimal.Parse(root.RootElement.GetProperty("BrokerCashEur").GetString()!,System.Globalization.CultureInfo.InvariantCulture);
        var first=session.Observe(snapshot,cash);var resumed=Mxm.Core.NativeFundedSession.Restore(session.Checkpoint(),snapshot.AccountBinding);
        var second=resumed.Observe(snapshot,cash);
        bool same=JsonSerializer.Serialize(first)==JsonSerializer.Serialize(second);
        if(!same)throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(new {Report=first,RestoredReportMatched=same,ActualBrokerCashImported=false,OrdersSubmitted=0}));return 0;
    } catch { return 25; }
}
if (args.Length == 3 && args[2] == "--native-funded-facts")
{
    try {
        var events=JsonSerializer.Deserialize<Mxm.Core.LedgerEvent[]>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString}) ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.NativeFundedLedger.ReceiveFacts(events)));return 0;
    } catch { return 22; }
}
if (args.Length == 3 && args[2] == "--portfolio-discovery-program")
{
    try {
        var input=JsonSerializer.Deserialize<Mxm.Core.DiscoveryInput>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString}) ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.PortfolioDiscoveryProgram.Evaluate(input)));return 0;
    } catch { return 23; }
}
if (args.Length == 3 && args[2] == "--sequence-portfolio-forecasts")
{
    try {
        var blocks=JsonSerializer.Deserialize<Mxm.Core.SequenceFeatureBlock[]>(File.ReadAllBytes(args[0])) ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(Mxm.Core.SequenceOpportunityResearch.Describe(blocks)));return 0;
    } catch { return 21; }
}
if (args.Length == 3 && args[2] == "--assess-holding-risk-batch")
{
    try {
        var inputs=JsonSerializer.Deserialize<Mxm.Core.HoldingRiskInput[]>(File.ReadAllBytes(args[0]),
            new JsonSerializerOptions {NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(inputs.Select(Mxm.Core.HoldingPortfolioRisk.Assess).ToArray()));
        return 0;
    } catch { return 20; }
}
if (args.Length == 3 && args[2] == "--causal-observation-windows")
{
    try {
        var windows=JsonSerializer.Deserialize<Mxm.Core.ObservationWindow[]>(File.ReadAllBytes(args[0]))
            ?? throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(windows.Select(Mxm.Core.CausalObservationClock.First).ToArray()));
        return 0;
    } catch { return 19; }
}
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
if (args.Length == 3 && args[2] == "--estimate-portfolio-opportunities-batch")
{
    try {
        var requests=JsonSerializer.Deserialize<Mxm.Core.ResearchOrchestrationRequest[]>(
            File.ReadAllBytes(args[0]),new JsonSerializerOptions {
                NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString})
            ?? throw new ArgumentException();
        if(requests.Length>5 || requests.Any(r=>
            !(r.Scope=="IPF1_MULTI_HORIZON_CONDITIONAL_RESEARCH_NOT_CERTIFIED" ||
              r.Scope=="RCP1_GLOBAL_RISK_DELAYED_FILL_CONDITIONAL_NOT_CERTIFIED") ||
            r.CommonHorizonMinutes!=0))throw new ArgumentException();
        File.WriteAllText(args[1],JsonSerializer.Serialize(requests.Select(Mxm.Core.OpportunityOrchestrator.Estimate).ToArray()));
        return 0;
    } catch { return 32; }
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


using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    public static int RunCompetitiveFamilies(string protocolPath,string sourcePath,string directory,
        string protectionDirectory,string stressText,bool causalManagementStudy=false,bool estimatorStudy=false,bool earlierEstimatorStudy=false,
        bool boundaryStudy=false)
    {
        var pb=File.ReadAllBytes(protocolPath);var sb=File.ReadAllBytes(sourcePath);
        var p=JsonSerializer.Deserialize<PavMarketPlan>(pb,Json)!;
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        bool costStudy=estimatorStudy&&!earlierEstimatorStudy&&p.Study=="MONETARY_COST_CONTEXT_GEOMETRY_1";
        decimal stress=decimal.Parse(stressText,System.Globalization.CultureInfo.InvariantCulture);
        string planHash=GeneralSha(pb),sourceHash=GeneralSha(sb);
        if(p.Study!=(boundaryStudy?"MONETARY_BOUNDARY_LIFECYCLE_1":costStudy?"MONETARY_COST_CONTEXT_GEOMETRY_1":earlierEstimatorStudy?"MONETARY_EARLIER_LIFECYCLE_ESTIMATION_1":estimatorStudy?"MONETARY_LIFECYCLE_ESTIMATION_1":causalManagementStudy?"MONETARY_CAUSAL_MANAGEMENT_1":"MONETARY_COMPETITIVE_FAMILIES_1")||p.Exposure!=ExposedDevelopment||
            p.Start!=input.Start||p.End!=input.End||p.SourceProtocolSha256!=input.ProtocolSha256||
            p.EvidenceManifestSha256!=input.EvidenceManifestSha256||input.Markets.Length!=(earlierEstimatorStudy?7:29)||
            input.Markets.Select(m=>m.Market.Name).Distinct().Count()!=input.Markets.Length||
            !(p.Start<p.SelectionFrom&&p.SelectionFrom<p.EvaluationFrom&&p.EvaluationFrom<p.End)||
            !p.Stresses.SequenceEqual(new[]{0m,.5m,1m})||!p.Stresses.Contains(stress)||
            p.Variants.Length!=(boundaryStudy?11:costStudy?7:earlierEstimatorStudy?9:estimatorStudy?5:causalManagementStudy?3:2)||p.Variants.Select(v=>v.Id).Distinct().Count()!=p.Variants.Length||
            p.Variants.Any(v=>v.UniverseCount!=input.Markets.Length||!v.Profile.CompeteEconomicFamilies||
                !v.Profile.LearnFromOpportunityEpisodes||!v.Profile.ObserveFamilyDirectionsOnClosedBars||
                !v.Profile.UseMarketTimeFxValuation||!v.Profile.ReserveObservedBarGaps)||
            !p.Variants.Select(v=>v.Profile.EconomicManagement).ToHashSet().SetEquals(
                boundaryStudy?new[]{"TRANSITION_VALUE",NativeEconomicMechanisms.MonetaryReduce,NativeEconomicMechanisms.BoundaryValue,NativeEconomicMechanisms.BoundaryReduce}:
                costStudy?new[]{"TRANSITION_VALUE",NativeEconomicMechanisms.MonetaryReduce,"CAPTURE_VALUE"}:
                new[]{"TRANSITION_VALUE",NativeEconomicMechanisms.MonetaryReduce}))
            throw new InvalidDataException("COMPETITIVE_FAMILY_STUDY_BINDING");
        if(causalManagementStudy&&p.Variants.Count(v=>v.Profile.SelectEconomicManagementCausally)!=1||
            !causalManagementStudy&&p.Variants.Any(v=>v.Profile.SelectEconomicManagementCausally))
            throw new InvalidDataException("CAUSAL_MANAGEMENT_VARIANT_BINDING");
        if(earlierEstimatorStudy&&(!estimatorStudy||input.Markets.Length!=7||
            !p.OriginalInstruments.Order().SequenceEqual(input.Markets.Select(m=>m.Market.Name).Order())))
            throw new InvalidDataException("EARLIER_ESTIMATOR_UNIVERSE_BINDING");
        if(earlierEstimatorStudy&&p.Variants.Count(v=>v.Profile.Pav1CompetitiveForecast is not null)!=3||
            !earlierEstimatorStudy&&!costStudy&&p.Variants.Any(v=>v.Profile.Pav1CompetitiveForecast is not null))
            throw new InvalidDataException("EARLIER_PAV1_FORECAST_ABLATION_BINDING");
        if(costStudy&&(p.Variants.Any(v=>!v.Profile.ReserveMarginForStopRisk)||
            p.Variants.Count(v=>v.Profile.LifecycleEstimator=="CENTERED_COST_CONTEXT")!=6)||
            !costStudy&&!boundaryStudy&&p.Variants.Any(v=>v.Profile.ReserveMarginForStopRisk||v.Profile.LifecycleEstimator=="CENTERED_COST_CONTEXT"))
            throw new InvalidDataException("COST_CONTEXT_GEOMETRY_BINDING");
        if(estimatorStudy&&p.Variants.Any(v=>v.Profile.LifecycleEstimator is null)||
            !estimatorStudy&&p.Variants.Any(v=>v.Profile.LifecycleEstimator is not null))
            throw new InvalidDataException("LIFECYCLE_ESTIMATOR_STUDY_BINDING");
        Directory.CreateDirectory(directory);
        string scenario=EerHash(planHash+"|"+FormattableString.Invariant($"{stress:G29}"));
        var tape=new EerProtectionTape(protectionDirectory);
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=tape,MinimumFundingHorizonMs=boundaryStudy?900_000L:0L};
        var streams=input.Markets.ToDictionary(m=>m.Market.Name,m=>new EerStream(m),StringComparer.Ordinal);
        var sharedObservers=new Dictionary<string,EurOpportunityObserver>(StringComparer.Ordinal);
        EurOpportunityObserver? Observer(NativeEurDevelopmentProfile profile)
        {
            if(profile.SelectEconomicManagementCausally)return null;
            if(!estimatorStudy)return new(profile,scenario,stress,source,tape,streams);
            string key=profile.GeometryIdentity;
            if(!sharedObservers.TryGetValue(key,out var observer))
                sharedObservers.Add(key,observer=new(profile,scenario,stress,source,tape,streams));
            return observer;
        }
        var cases=p.Variants.Select(v=>(v.Id,Profile:v.Profile,
            Observer:Observer(v.Profile),
            Book:new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralSelect,
                fundingScenarioId:scenario,eurDevelopmentProfile:v.Profile))).ToArray();
        var cash=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralCash,
            fundingScenarioId:scenario,eurDevelopmentProfile:p.Variants[0].Profile);
        (string Id,NativeUnifiedPortfolioEngine Book)[] books=cases.Select(c=>(Id:c.Id,Book:c.Book)).Append((Id:"CASH_MARKET_TIME",Book:cash)).ToArray();
        var fits=new List<object>();
        void Observe(long from,long through,bool trade)
        {
            int clocks=0;
            for(long at=from+EurOffset;at<through;at+=EurStep)
            {
                source.BeginHistoricalClock();
                var frame=new Ucp1Frame(at,streams.Values.Select(m=>source.Frame(m,at,scenario,stress,general:true))
                    .OfType<Ucp1MarketFrame>().ToArray());
                if(trade)
                    foreach(var c in books)
                    {
                        tape.Between(c.Book,at-1,source,streams,scenario,stress);
                        source.Advance(c.Book,frame with {Protection=tape.GridCoverage(c.Book,at)},streams,scenario,stress);
                    }
                if(estimatorStudy){foreach(var observer in sharedObservers.Values)observer.Advance(frame);}
                else foreach(var c in cases)c.Observer?.Advance(frame);
                if(++clocks%288==0)Console.WriteLine($"COMPETITIVE_FAMILIES_PROGRESS stress={stress} at={at} trade={trade} observations={clocks}");
            }
        }
        void Fit(long at,bool initial)
        {
            foreach(var c in cases)
            {
                var model=c.Observer?.Export();
                if(model is null)
                {
                    var labels=cases.Where(x=>x.Observer is not null).SelectMany(x=>x.Observer!.Export().Outcomes.Select(o=>o with
                        {PositionId=o.PositionId+"/"+x.Profile.EconomicManagement,EconomicManagement=x.Profile.EconomicManagement}))
                        .OrderBy(o=>o.ClosedAt).ThenBy(o=>o.PositionId,StringComparer.Ordinal).ToArray();
                    model=new NativeEurCalibration(cases.Where(x=>x.Observer is not null).Min(x=>x.Observer!.Export().ObservationThrough),
                        GeneralSha(JsonSerializer.SerializeToUtf8Bytes(labels,Json)),labels)
                    {FundingScenarioId=scenario,OpportunitySchema=NativeUnifiedPortfolioEngine.EurGeneralSchema,
                        DevelopmentGeometry=c.Profile.GeometryIdentity,OpportunityEpisodeLabels=true};
                }
                if(model.ObservationThrough>=at||model.Outcomes.Any(x=>x.AvailableAt>=at))
                    throw new InvalidDataException("COMPETITIVE_FUTURE_CALIBRATION");
                if(initial)c.Book.LoadEurCalibration(model);else c.Book.UpdateEurResearchCalibration(model);
                fits.Add(new {c.Id,AvailableBefore=at,model.ObservationThrough,Outcomes=model.Outcomes.Length,
                    ModelSha256=GeneralSha(JsonSerializer.SerializeToUtf8Bytes(model,Json)),
                    ByFamily=model.Outcomes.GroupBy(x=>new {x.Family,x.Side}).Select(g=>new
                    {g.Key.Family,g.Key.Side,Count=g.Count(),NetEur=g.Sum(x=>x.NetEur)}).ToArray()});
            }
        }
        void Checkpoint(string phase)
        {
            var root=Path.Combine(directory,"checkpoints",phase);Directory.CreateDirectory(root);
            foreach(var c in books)File.WriteAllText(Path.Combine(root,c.Id+".json"),c.Book.HistoricalEurCheckpoint());
            var observers=cases.Where(x=>x.Observer is not null);
            if(estimatorStudy)observers=observers.GroupBy(x=>x.Observer).Select(g=>g.First());
            foreach(var c in observers)File.WriteAllBytes(Path.Combine(root,c.Id+"-observer.json"),
                JsonSerializer.SerializeToUtf8Bytes(c.Observer!.Checkpoint(),NativeHistoricalCheckpointJson.Options));
            Console.WriteLine($"COMPETITIVE_FAMILIES_CHECKPOINT {stress} {phase}");
        }
        Observe(p.Start,p.SelectionFrom,false);
        Fit(p.SelectionFrom,true);
        long current=p.SelectionFrom;object? selection=null;
        while(current<p.End)
        {
            long next=Math.Min(current+7*HistoricalDay,p.End);
            if(current<p.EvaluationFrom&&next>p.EvaluationFrom)next=p.EvaluationFrom;
            Observe(current,next,true);
            if(next==p.EvaluationFrom)
            {
                selection=books.Select(c=>new {c.Id,Result=HistoricalBook(c.Book,new[]{p.SelectionFrom,next}),
                    Monetary=PavCashScore(c.Book,p.SelectionFrom,next)}).ToArray();
                File.WriteAllBytes(Path.Combine(directory,"selection.json"),JsonSerializer.SerializeToUtf8Bytes(selection,Json));
            }
            Checkpoint(next.ToString(System.Globalization.CultureInfo.InvariantCulture));
            current=next;
            if(current<p.End)Fit(current,false);
        }
        if(selection is null)throw new InvalidDataException("COMPETITIVE_SELECTION_NOT_CAPTURED");
        if(boundaryStudy)File.WriteAllBytes(Path.Combine(directory,"boundary-forecast-diagnostics.json"),
            JsonSerializer.SerializeToUtf8Bytes(books.Select(c=>new {c.Id,Forecasts=c.Book.BoundaryForecastDiagnostics()}).ToArray(),Json));
        var result=new {p.Study,p.Exposure,Stress=stress,SourceSha256=sourceHash,ProtocolSha256=planHash,
            input.EvidenceManifestSha256,Selection=selection,Fits=fits,
            CommonBooks=books.Select(c=>new {c.Id,Result=HistoricalBook(c.Book,new[]{p.SelectionFrom,p.EvaluationFrom,p.End}),
                HeldOutMonetary=PavCashScore(c.Book,p.EvaluationFrom,p.End),
                Details=EconomicStudyDetails(c.Book,source,streams)}).ToArray(),
            SourceAvailability=streams.Values.Select(s=>new {s.Source.Market.Name,s.Counts}).ToArray(),
            ObserverReceipts=(estimatorStudy?cases.Where(c=>c.Observer is not null).GroupBy(c=>c.Observer).Select(g=>g.First()):
                cases.Where(c=>c.Observer is not null)).Select(c=>new {c.Id,Report=c.Observer!.Report()}).ToArray(),
            SharedPortfolioEvaluations=books.Length,SharedCapitalEur=300,
            Scope="SEVEN_FAMILY_COMPETITION_IN_EACH_COMMON_BOOK; HOURLY_CAUSAL_SHADOW_LABELS; WEEKLY_WALK_FORWARD",
            OriginalResultsModified=false,SourceBrokerRequests=0,Orders=0,CloudActivated=false,
            IndependentConfirmationCertified=false,EconomicPromotionCertified=false};
        File.WriteAllBytes(Path.Combine(directory,"result.json"),JsonSerializer.SerializeToUtf8Bytes(result,Json));
        return 0;
    }
}

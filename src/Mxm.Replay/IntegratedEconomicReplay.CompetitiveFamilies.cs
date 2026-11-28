using System.Text.Json;
using System.Diagnostics;
using System.Security.Cryptography;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record FactorialCheckpointBinding(string Protocol,string Source,string Protection,string Registry,
        string Scenario,string InputRevision,string? RunnerRevision,bool Bounded,bool Paired,bool CompactRegistry=false,bool CompactPath=false);
    sealed record FactorialCheckpointState(string Version,FactorialCheckpointBinding Binding,int Phase,long Through,long LastClock,
        Dictionary<string,HistoricalStreamState> Streams,Dictionary<string,string> Files,JsonElement[] Fits,
        JsonElement? Selection,EerEvidence.HoldingGapCheckpoint[] HoldingGaps,Dictionary<string,int> FxCounts,
        Dictionary<string,NativeMarketTimePrice> ClosedWitnesses,long Clocks,long MarketFrames,long BookAdvances,
        long ObserverAdvances,long CalibrationFits,long CalibrationLabels);
    static string FactorialFileSha(string path)
    {
        using var file=File.OpenRead(path);
        return Convert.ToHexString(SHA256.HashData(file)).ToLowerInvariant();
    }

    public static int RunCompetitiveFamilies(string protocolPath,string sourcePath,string directory,
        string protectionDirectory,string stressText,bool causalManagementStudy=false,bool estimatorStudy=false,bool earlierEstimatorStudy=false,
        bool boundaryStudy=false,bool multibarStudy=false,bool adaptiveStudy=false,bool controlledRecencyStudy=false,bool distributionStudy=false,string? valuationRegistryPath=null)
    {
        var elapsed=Stopwatch.StartNew();
        using var process=Process.GetCurrentProcess();
        long clocksProcessed=0, marketFrames=0, bookAdvances=0, observerAdvances=0;
        long calibrationFits=0, calibrationLabels=0;
        TimeSpan lastProgress=TimeSpan.MinValue;
        void Progress(string stage,long? historicalAt=null,int completedBooks=0,int? totalBooks=null,bool force=false)
        {
            var now=elapsed.Elapsed;
            if(!force&&lastProgress!=TimeSpan.MinValue&&now-lastProgress<TimeSpan.FromSeconds(15))return;
            lastProgress=now;
            process.Refresh();
            Console.WriteLine("MXM_ECONOMIC_PROGRESS "+JsonSerializer.Serialize(new
            {
                stage,scenario=stressText,historicalAt,completedBooks,totalBooks,
                remainingBooks=totalBooks.HasValue?(int?)(totalBooks.Value-completedBooks):null,
                clocksProcessed,marketFrames,bookAdvances,observerAdvances,calibrationFits,calibrationLabels,
                elapsedSeconds=now.TotalSeconds,workingSetBytes=process.WorkingSet64,
                peakWorkingSetBytes=process.PeakWorkingSet64,managedBytes=GC.GetTotalMemory(false),
                gen0=GC.CollectionCount(0),gen1=GC.CollectionCount(1),gen2=GC.CollectionCount(2)
            }));
            Console.Out.Flush();
        }
        Progress("READ_SOURCE",force:true);
        var pb=File.ReadAllBytes(protocolPath);var sb=File.ReadAllBytes(sourcePath);
        var p=JsonSerializer.Deserialize<PavMarketPlan>(pb,Json)!;
        var input=JsonSerializer.Deserialize<EerInput>(sb,Json)!;
        bool riskStudy=distributionStudy&&p.Study=="MONETARY_WITNESSED_RISK_GEOMETRY_1";
        bool factorialStudy=distributionStudy&&(p.Study=="MONETARY_MANAGEMENT_FACTORIAL_1"||riskStudy);
        bool costStudy=estimatorStudy&&!earlierEstimatorStudy&&p.Study=="MONETARY_COST_CONTEXT_GEOMETRY_1";
        decimal stress=decimal.Parse(stressText,System.Globalization.CultureInfo.InvariantCulture);
        string planHash=GeneralSha(pb),sourceHash=GeneralSha(sb);
        if(p.Study!=(riskStudy?"MONETARY_WITNESSED_RISK_GEOMETRY_1":factorialStudy?"MONETARY_MANAGEMENT_FACTORIAL_1":distributionStudy?"MONETARY_PATH_DISTRIBUTION_1":controlledRecencyStudy?"MONETARY_CONTROLLED_RECENCY_1":adaptiveStudy?"MONETARY_CAUSAL_RECENCY_COMPETITION_1":multibarStudy?"MONETARY_NET_HORIZON_CROSS_CONTEXT_1":boundaryStudy?"MONETARY_BOUNDARY_LIFECYCLE_1":costStudy?"MONETARY_COST_CONTEXT_GEOMETRY_1":earlierEstimatorStudy?"MONETARY_EARLIER_LIFECYCLE_ESTIMATION_1":estimatorStudy?"MONETARY_LIFECYCLE_ESTIMATION_1":causalManagementStudy?"MONETARY_CAUSAL_MANAGEMENT_1":"MONETARY_COMPETITIVE_FAMILIES_1")||p.Exposure!=ExposedDevelopment||
            p.Start!=input.Start||p.End!=input.End||p.SourceProtocolSha256!=input.ProtocolSha256||
            p.EvidenceManifestSha256!=input.EvidenceManifestSha256||((multibarStudy||adaptiveStudy||distributionStudy)?input.Markets.Length is not (7 or 29):input.Markets.Length!=(earlierEstimatorStudy?7:29))||
            input.Markets.Select(m=>m.Market.Name).Distinct().Count()!=input.Markets.Length||
            !(p.Start<p.SelectionFrom&&p.SelectionFrom<p.EvaluationFrom&&p.EvaluationFrom<p.End)||
            !p.Stresses.SequenceEqual(new[]{0m,.5m,1m})||!p.Stresses.Contains(stress)||
            p.Variants.Length!=(factorialStudy?8:distributionStudy?4:controlledRecencyStudy?3:adaptiveStudy?4:multibarStudy?6:boundaryStudy?13:costStudy?7:earlierEstimatorStudy?9:estimatorStudy?5:causalManagementStudy?3:2)||p.Variants.Select(v=>v.Id).Distinct().Count()!=p.Variants.Length||
            p.Variants.Any(v=>v.UniverseCount!=input.Markets.Length||!v.Profile.CompeteEconomicFamilies||
                !v.Profile.LearnFromOpportunityEpisodes||!v.Profile.ObserveFamilyDirectionsOnClosedBars||
                !v.Profile.UseMarketTimeFxValuation||!v.Profile.ReserveObservedBarGaps)||
            !p.Variants.Select(v=>v.Profile.EconomicManagement).ToHashSet().SetEquals(
                distributionStudy?new[]{NativeEconomicMechanisms.MonetaryReduce}:controlledRecencyStudy?new[]{"CAPTURE_VALUE"}:
                adaptiveStudy?new[]{"TRANSITION_VALUE","CAPTURE_VALUE",NativeEconomicMechanisms.MonetaryReduce}:
                multibarStudy?new[]{"TRANSITION_VALUE",NativeEconomicMechanisms.MonetaryReduce,"CAPTURE_VALUE",NativeEconomicMechanisms.BoundaryValue,NativeEconomicMechanisms.BoundaryReduce}:
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
            !earlierEstimatorStudy&&!costStudy&&!boundaryStudy&&!factorialStudy&&p.Variants.Any(v=>v.Profile.Pav1CompetitiveForecast is not null))
            throw new InvalidDataException("EARLIER_PAV1_FORECAST_ABLATION_BINDING");
        if((boundaryStudy||multibarStudy)&&(p.Variants.Count(v=>v.Profile.Pav1CompetitiveForecast=="DIRECT")!=2||
            p.Variants.Any(v=>v.Profile.Pav1CompetitiveForecast is not (null or "DIRECT"))))
            throw new InvalidDataException("BOUNDARY_RECOVERED_DIRECT_CONTROLS_BINDING");
        if(multibarStudy&&(!estimatorStudy||!boundaryStudy||
            p.Variants.Any(v=>!v.Profile.ReserveMarginForStopRisk)||
            p.Variants.Count(v=>v.Profile.BoundaryHorizonBars>0)!=3||
            p.Variants.Any(v=>v.Profile.BoundaryHorizonBars>0&&
                (v.Profile.EconomicManagementTimeframe is not ("M5" or "M15")||
                 v.Profile.BoundaryHorizonBars*(v.Profile.EconomicManagementTimeframe=="M5"?5:15)>30))||
            (input.Markets.Length==7&&!p.OriginalInstruments.Order().SequenceEqual(input.Markets.Select(m=>m.Market.Name).Order()))))
            throw new InvalidDataException("MULTIBAR_CROSS_CONTEXT_BINDING");
        if(adaptiveStudy&&!distributionStudy&&(!estimatorStudy||p.Variants.Any(v=>!v.Profile.ReserveMarginForStopRisk||
                (!controlledRecencyStudy&&v.Profile.LifecycleRecencyHalfLifeDays<=0)||v.Profile.LifecycleEstimator!="CENTERED_COST_CONTEXT"||
                v.Profile.Pav1CompetitiveForecast is not null)||
            (input.Markets.Length==7&&!p.OriginalInstruments.Order().SequenceEqual(input.Markets.Select(m=>m.Market.Name).Order()))))
            throw new InvalidDataException("ADAPTIVE_RECENCY_COMPETITION_BINDING");
        if(controlledRecencyStudy&&(!adaptiveStudy||
            !p.Variants.Select(v=>v.Profile.LifecycleRecencyHalfLifeDays).Order().SequenceEqual(new[]{0,14,28})||
            p.Variants.Any(v=>!v.Profile.CaptureLifecycleRecencyEvidence)||
            p.Variants.Select(v=>v.Profile with {LifecycleRecencyHalfLifeDays=0}).Distinct().Count()!=1))
            throw new InvalidDataException("CONTROLLED_RECENCY_PROFILE_PARITY");
        if(costStudy&&(p.Variants.Any(v=>!v.Profile.ReserveMarginForStopRisk)||
            p.Variants.Count(v=>v.Profile.LifecycleEstimator=="CENTERED_COST_CONTEXT")!=6)||
            !costStudy&&!boundaryStudy&&!adaptiveStudy&&!distributionStudy&&p.Variants.Any(v=>v.Profile.ReserveMarginForStopRisk||v.Profile.LifecycleEstimator=="CENTERED_COST_CONTEXT"))
            throw new InvalidDataException("COST_CONTEXT_GEOMETRY_BINDING");
        if(estimatorStudy&&p.Variants.Any(v=>v.Profile.LifecycleEstimator is null)||
            !estimatorStudy&&p.Variants.Any(v=>v.Profile.LifecycleEstimator is not null))
            throw new InvalidDataException("LIFECYCLE_ESTIMATOR_STUDY_BINDING");
        if(distributionStudy&&!factorialStudy&&(p.Variants.Any(v=>!v.Profile.CaptureOpportunityPathEvidence||!v.Profile.ReserveMarginForStopRisk)||
            p.Variants.Count(v=>v.Profile.UsePathDistributionManagement)!=1||p.Variants.Count(v=>v.Profile.RequirePathTailCapacity)!=2||
            !p.Variants.Select(v=>v.Profile.LifecycleEstimator).Order().SequenceEqual(new[]{"CENTERED_COST_CONTEXT","DISTRIBUTION_CONTEXT","DISTRIBUTION_CONTEXT","DISTRIBUTION_CONTEXT"})))
            throw new InvalidDataException("DISTRIBUTION_STUDY_ABLATION_BINDING");
        if(p.Variants.Any(v=>v.Profile.UseWitnessedPortfolioDrawdownGuard!=riskStudy))
            throw new InvalidDataException("WITNESSED_RISK_STUDY_BINDING");
        if(riskStudy)
        {
            var expected=new (string Id,string? Estimator,bool Management,string? Pav1,decimal Target)[]
            {
                ("CENTERED_GUARD","CENTERED_COST_CONTEXT",false,null,2.5m),
                ("CENTERED_MANAGEMENT_GUARD","CENTERED_COST_CONTEXT",true,null,2.5m),
                ("DISTRIBUTION_GUARD","DISTRIBUTION_CONTEXT",false,null,2.5m),
                ("DISTRIBUTION_MANAGEMENT_GUARD","DISTRIBUTION_CONTEXT",true,null,2.5m),
                ("PAV1_DIRECT_GUARD","CENTERED_COST_CONTEXT",false,"DIRECT",2.5m),
                ("PAV1_DIRECT_MANAGEMENT_GUARD","CENTERED_COST_CONTEXT",true,"DIRECT",2.5m),
                ("DISTRIBUTION_MANAGEMENT_TARGET_15","DISTRIBUTION_CONTEXT",true,null,1.5m),
                ("PAV1_DIRECT_MANAGEMENT_TARGET_15","CENTERED_COST_CONTEXT",true,"DIRECT",1.5m)
            };
            if(valuationRegistryPath is null||
                !p.Variants.Select(v=>(v.Id,v.Profile.LifecycleEstimator,v.Profile.UsePathDistributionManagement,
                    v.Profile.Pav1CompetitiveForecast,v.Profile.DistributionTargetRanges)).SequenceEqual(expected)||
                p.Variants.Any(v=>!v.Profile.CaptureOpportunityPathEvidence||!v.Profile.ReserveMarginForStopRisk||v.Profile.RequirePathTailCapacity)||
                p.Variants.Select(v=>v.Profile with {LifecycleEstimator=null,UsePathDistributionManagement=false,
                    Pav1CompetitiveForecast=null,DistributionTargetRanges=2.5m}).Distinct().Count()!=1)
                throw new InvalidDataException("WITNESSED_RISK_GEOMETRY_PROFILE_BINDING");
        }
        else if(factorialStudy)
        {
            var expected=new (string Id,string? Estimator,bool Tail,bool Management,string? Pav1)[]
            {
                ("CENTERED_CONTROL","CENTERED_COST_CONTEXT",false,false,null),
                ("CENTERED_MANAGEMENT","CENTERED_COST_CONTEXT",false,true,null),
                ("DISTRIBUTION_CONTEXT","DISTRIBUTION_CONTEXT",false,false,null),
                ("DISTRIBUTION_MANAGEMENT","DISTRIBUTION_CONTEXT",false,true,null),
                ("DISTRIBUTION_TAIL","DISTRIBUTION_CONTEXT",true,false,null),
                ("DISTRIBUTION_TAIL_MANAGEMENT","DISTRIBUTION_CONTEXT",true,true,null),
                ("PAV1_DIRECT_CONTROL","CENTERED_COST_CONTEXT",false,false,"DIRECT"),
                ("PAV1_DIRECT_MANAGEMENT","CENTERED_COST_CONTEXT",false,true,"DIRECT")
            };
            if(valuationRegistryPath is null||
                !p.Variants.Select(v=>(v.Id,v.Profile.LifecycleEstimator,v.Profile.RequirePathTailCapacity,
                    v.Profile.UsePathDistributionManagement,v.Profile.Pav1CompetitiveForecast)).SequenceEqual(expected)||
                p.Variants.Any(v=>!v.Profile.CaptureOpportunityPathEvidence||!v.Profile.ReserveMarginForStopRisk)||
                p.Variants.Select(v=>v.Profile with {LifecycleEstimator=null,RequirePathTailCapacity=false,
                    UsePathDistributionManagement=false,Pav1CompetitiveForecast=null}).Distinct().Count()!=1)
                throw new InvalidDataException("MANAGEMENT_FACTORIAL_PROFILE_BINDING");
        }
        Directory.CreateDirectory(directory);
        string scenario=EerHash(planHash+"|"+FormattableString.Invariant($"{stress:G29}"));
        Progress("BUILD_EVIDENCE",force:true);
        EerProtectionTape tape;
        using(NativeEconomicProfiler.Measure("replay.protection_restore"))
            tape=new EerProtectionTape(protectionDirectory);
        NativeReusableValuationRegistry? registry;
        using(NativeEconomicProfiler.Measure("replay.valuation_registry_restore"))
            registry=LoadValuationRegistry(valuationRegistryPath);
        var source=new EerEvidence(input){MarketTimeFx=true,ValuationTape=tape,MinimumFundingHorizonMs=distributionStudy?3_600_000L:(multibarStudy||adaptiveStudy)?1_800_000L:boundaryStudy?900_000L:0L,
            CaptureHoldingValuationGaps=multibarStudy||adaptiveStudy||distributionStudy,RecoverFreshHoldingMarks=controlledRecencyStudy||distributionStudy,
            CaptureBetweenDecisionValuationGaps=controlledRecencyStudy||distributionStudy,
            RecoverFreshRegistryHoldingMarks=factorialStudy,
            HeldRegistry=registry};
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
        long lastClock=-1;
        string? resumeFrom=Environment.GetEnvironmentVariable("MXM_FACTORIAL_RESUME_FROM");
        string? stopText=Environment.GetEnvironmentVariable("MXM_FACTORIAL_STOP_AFTER_PHASE");
        if(!factorialStudy&&(resumeFrom is not null||stopText is not null))
            throw new InvalidDataException("FACTORIAL_CHECKPOINT_STUDY_REQUIRED");
        var phaseBoundaries=new List<long>{p.SelectionFrom};
        while(phaseBoundaries[^1]<p.End)
        {
            long at=phaseBoundaries[^1],next=Math.Min(at+7*HistoricalDay,p.End);
            if(at<p.EvaluationFrom&&next>p.EvaluationFrom)next=p.EvaluationFrom;
            phaseBoundaries.Add(next);
        }
        int? stopAfter=null;
        if(stopText is not null)
        {
            if(!int.TryParse(stopText,out int phase)||phase<0||phase>=phaseBoundaries.Count-1)
                throw new InvalidDataException("FACTORIAL_CHECKPOINT_STOP_PHASE");
            stopAfter=phase;
        }
        FactorialCheckpointBinding? binding=factorialStudy?new(planHash,sourceHash,
            ProtectionFingerprint(protectionDirectory),FactorialFileSha(valuationRegistryPath!),scenario,input.EngineRevision,
            Environment.GetEnvironmentVariable("GITHUB_SHA"),
            Environment.GetEnvironmentVariable("MXM_ECONOMIC_BOUNDED_NEIGHBORS")=="1",
            Environment.GetEnvironmentVariable("MXM_ECONOMIC_PAIRED_DISTRIBUTION")=="1",
            Environment.GetEnvironmentVariable("MXM_ECONOMIC_COMPACT_REGISTRY")=="1",
            Environment.GetEnvironmentVariable("MXM_ECONOMIC_COMPACT_PATH")=="1"):null;
        var distinctObservers=(estimatorStudy?cases.Where(x=>x.Observer is not null).GroupBy(x=>x.Observer).Select(g=>g.First()):
            cases.Where(x=>x.Observer is not null)).ToArray();
        void Observe(long from,long through,bool trade)
        {
            int clocks=0;
            string stage=trade?"PORTFOLIO_REPLAY":"MATURING_OBSERVATIONS";
            Progress(stage,from,totalBooks:books.Length,force:true);
            for(long at=from+EurOffset;at<through;at+=EurStep)
            {
                source.BeginHistoricalClock();
                Ucp1Frame frame;
                using(NativeEconomicProfiler.Measure("replay.build_frame"))
                    frame=new Ucp1Frame(at,streams.Values.Select(m=>source.Frame(m,at,scenario,stress,general:true))
                        .OfType<Ucp1MarketFrame>().ToArray());
                // Count actual calls and completed clocks, never projected work.
                marketFrames+=streams.Count;
                if(trade)
                    foreach(var c in books)
                    {
                        using(NativeEconomicProfiler.Measure("replay.book_protection"))
                            tape.Between(c.Book,at-1,source,streams,scenario,stress);
                        using(NativeEconomicProfiler.Measure("replay.book_advance"))
                            source.Advance(c.Book,frame with {Protection=tape.GridCoverage(c.Book,at)},streams,scenario,stress);
                        bookAdvances++;
                    }
                using(NativeEconomicProfiler.Measure("replay.observer_advance"))
                {
                    if(estimatorStudy){foreach(var observer in sharedObservers.Values){observer.Advance(frame);observerAdvances++;}}
                    else foreach(var c in cases)if(c.Observer is not null){c.Observer.Advance(frame);observerAdvances++;}
                }
                clocksProcessed++;lastClock=at;
                Progress(stage,at,totalBooks:books.Length);
                if(++clocks%288==0)Console.WriteLine($"COMPETITIVE_FAMILIES_PROGRESS stress={stress} at={at} trade={trade} observations={clocks}");
            }
            Progress(stage,through,totalBooks:books.Length,force:true);
        }
        void Fit(long at,bool initial)
        {
            Progress("CALIBRATE",at,totalBooks:books.Length,force:true);
            using var profile=NativeEconomicProfiler.Measure("replay.calibrate");
            int completedFits=0;
            foreach(var c in cases)
            {
                Progress("CALIBRATE_BOOK",at,completedFits,cases.Length,force:true);
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
                calibrationFits++;calibrationLabels+=model.Outcomes.Length;completedFits++;
                Progress("CALIBRATE_BOOK_COMPLETE",at,completedFits,cases.Length,force:true);
                fits.Add(new {c.Id,AvailableBefore=at,model.ObservationThrough,Outcomes=model.Outcomes.Length,
                    ModelSha256=GeneralSha(JsonSerializer.SerializeToUtf8Bytes(model,Json)),
                    ByFamily=model.Outcomes.GroupBy(x=>new {x.Family,x.Side}).Select(g=>new
                    {g.Key.Family,g.Key.Side,Count=g.Count(),NetEur=g.Sum(x=>x.NetEur)}).ToArray()});
            }
            Progress("CALIBRATE_COMPLETE",at,cases.Length,cases.Length,force:true);
        }
        object? selection=null;
        void Checkpoint(string phase,int? phaseIndex=null)
        {
            using var profile=NativeEconomicProfiler.Measure("replay.checkpoint");
            Progress("WRITE_CHECKPOINT",totalBooks:books.Length,force:true);
            var root=Path.Combine(directory,"checkpoints",phase);Directory.CreateDirectory(root);
            foreach(var c in books)File.WriteAllText(Path.Combine(root,c.Id+".json"),c.Book.HistoricalEurCheckpoint());
            foreach(var c in distinctObservers)File.WriteAllBytes(Path.Combine(root,c.Id+"-observer.json"),
                JsonSerializer.SerializeToUtf8Bytes(c.Observer!.Checkpoint(),NativeHistoricalCheckpointJson.Options));
            if(phaseIndex is int index)
            {
                var names=books.Select(x=>x.Id+".json").Concat(distinctObservers.Select(x=>x.Id+"-observer.json"));
                var files=names.ToDictionary(x=>x,x=>FactorialFileSha(Path.Combine(root,x)),StringComparer.Ordinal);
                var saved=new FactorialCheckpointState("FACTORIAL_REPLAY_V1",binding!,index,phaseBoundaries[index],lastClock,
                    streams.ToDictionary(x=>x.Key,x=>new HistoricalStreamState(x.Value.Counts,x.Value.Availability),StringComparer.Ordinal),
                    files,fits.Select(x=>JsonSerializer.SerializeToElement(x,Json)).ToArray(),
                    selection is null?null:JsonSerializer.SerializeToElement(selection,Json),
                    source.SaveHoldingGaps(),source.FxEvidenceCounts,source.ClosedPriceWitnesses,clocksProcessed,
                    marketFrames,bookAdvances,observerAdvances,calibrationFits,calibrationLabels);
                string temporary=Path.Combine(root,"resume.json.tmp");
                using(var file=new FileStream(temporary,FileMode.Create,FileAccess.Write))
                {
                    JsonSerializer.Serialize(file,saved,Json);file.Flush(true);
                }
                File.Move(temporary,Path.Combine(root,"resume.json"),true);
            }
            Console.WriteLine($"COMPETITIVE_FAMILIES_CHECKPOINT {stress} {phase}");
            Progress("CHECKPOINT_WRITTEN",totalBooks:books.Length,force:true);
        }
        long current=p.SelectionFrom;int completedPhase=0;
        if(resumeFrom is not null)
        {
            Progress("RESTORE_FACTORIAL_CHECKPOINT",force:true);
            using var restoreProfile=NativeEconomicProfiler.Measure("replay.factorial_restore");
            using var file=File.OpenRead(resumeFrom);
            var saved=JsonSerializer.Deserialize<FactorialCheckpointState>(file,Json)
                ??throw new InvalidDataException("FACTORIAL_CHECKPOINT_REQUIRED");
            int phase=saved.Phase;
            if(saved.Version!="FACTORIAL_REPLAY_V1"||saved.Binding!=binding||phase<0||
                phase>=phaseBoundaries.Count-1||saved.Through!=phaseBoundaries[phase]||
                saved.Fits.Length!=cases.Length*(phase+1)||saved.Streams.Count!=streams.Count||
                saved.Selection.HasValue!=(saved.Through>=p.EvaluationFrom))
                throw new InvalidDataException("FACTORIAL_CHECKPOINT_BINDING");
            long from=phase==0?p.Start:phaseBoundaries[phase-1];
            long expectedClock=from+EurOffset+(saved.Through-from-EurOffset-1)/EurStep*EurStep;
            if(saved.LastClock!=expectedClock||saved.LastClock>=saved.Through)
                throw new InvalidDataException("FACTORIAL_CHECKPOINT_CLOCK");
            string root=Path.GetDirectoryName(Path.GetFullPath(resumeFrom))!;
            var expectedFiles=books.Select(x=>x.Id+".json").Concat(distinctObservers.Select(x=>x.Id+"-observer.json"))
                .Order(StringComparer.Ordinal).ToArray();
            if(!saved.Files.Keys.Order(StringComparer.Ordinal).SequenceEqual(expectedFiles))
                throw new InvalidDataException("FACTORIAL_CHECKPOINT_FILES");
            string CheckedPath(string name)
            {
                string path=Path.Combine(root,name);
                if(FactorialFileSha(path)!=saved.Files[name])throw new InvalidDataException("FACTORIAL_CHECKPOINT_FILE_SHA");
                return path;
            }
            foreach(var (id,stream) in streams)
            {
                var state=saved.Streams[id];
                if(state.Availability.Keys.Any(at=>at>saved.LastClock))
                    throw new InvalidDataException("FACTORIAL_CHECKPOINT_STREAM_CLOCK");
                stream.Counts=state.Counts;stream.Availability=state.Availability;
            }
            long bookClock=phase==0?-1:saved.LastClock;
            for(int i=0;i<books.Length;i++)
            {
                var (id,book)=books[i];
                var restored=RestoreHistoricalBook(File.ReadAllText(CheckedPath(id+".json")),book.PolicyName,scenario,bookClock);
                books[i]=(id,restored);
                if(i<cases.Length)
                {
                    var old=cases[i];cases[i]=(old.Id,old.Profile,old.Observer,restored);
                }
            }
            foreach(var c in distinctObservers)
            {
                using var observerFile=File.OpenRead(CheckedPath(c.Id+"-observer.json"));
                var state=JsonSerializer.Deserialize<ObserverCheckpoint>(observerFile,NativeHistoricalCheckpointJson.Options)
                    ??throw new InvalidDataException("FACTORIAL_CHECKPOINT_OBSERVER");
                c.Observer!.Restore(state,saved.LastClock);
            }
            source.RestoreHoldingGaps(saved.HoldingGaps,saved.LastClock);
            foreach(var (key,value) in saved.FxCounts)source.FxEvidenceCounts.Add(key,value);
            foreach(var (key,value) in saved.ClosedWitnesses)source.ClosedPriceWitnesses.Add(key,value);
            fits.AddRange(saved.Fits.Select(x=>(object)x));
            selection=saved.Selection.HasValue?(object)saved.Selection.Value:null;
            completedPhase=phase;current=saved.Through;lastClock=saved.LastClock;
            clocksProcessed=saved.Clocks;marketFrames=saved.MarketFrames;bookAdvances=saved.BookAdvances;
            observerAdvances=saved.ObserverAdvances;calibrationFits=saved.CalibrationFits;calibrationLabels=saved.CalibrationLabels;
            if(stopAfter.HasValue&&stopAfter.Value<=completedPhase)
                throw new InvalidDataException("FACTORIAL_CHECKPOINT_STOP_NOT_FORWARD");
            Progress("FACTORIAL_CHECKPOINT_RESTORED",current,totalBooks:books.Length,force:true);
        }
        else
        {
            Observe(p.Start,p.SelectionFrom,false);
            Fit(p.SelectionFrom,true);
            if(factorialStudy)
            {
                Checkpoint(current.ToString(System.Globalization.CultureInfo.InvariantCulture),0);
                if(stopAfter==0)return 0;
            }
        }
        while(current<p.End)
        {
            long next=phaseBoundaries[completedPhase+1];
            Observe(current,next,true);
            if(next==p.EvaluationFrom)
            {
                selection=books.Select(c=>new {c.Id,Result=HistoricalBook(c.Book,new[]{p.SelectionFrom,next}),
                    Monetary=PavCashScore(c.Book,p.SelectionFrom,next)}).ToArray();
                File.WriteAllBytes(Path.Combine(directory,"selection.json"),JsonSerializer.SerializeToUtf8Bytes(selection,Json));
            }
            completedPhase++;
            if(factorialStudy)
            {
                current=next;
                // Save after calibration, so restarting never fits an already completed boundary.
                if(current<p.End)Fit(current,false);
                Checkpoint(current.ToString(System.Globalization.CultureInfo.InvariantCulture),completedPhase);
                if(stopAfter==completedPhase)return 0;
            }
            else
            {
                Checkpoint(next.ToString(System.Globalization.CultureInfo.InvariantCulture));
                current=next;
                if(current<p.End)Fit(current,false);
            }
        }
        if(selection is null)throw new InvalidDataException("COMPETITIVE_SELECTION_NOT_CAPTURED");
        if(boundaryStudy)File.WriteAllBytes(Path.Combine(directory,"boundary-forecast-diagnostics.json"),
            JsonSerializer.SerializeToUtf8Bytes(books.Select(c=>new {c.Id,Forecasts=c.Book.BoundaryForecastDiagnostics()}).ToArray(),Json));
        if(multibarStudy||adaptiveStudy||distributionStudy)File.WriteAllBytes(Path.Combine(directory,"holding-valuation-gaps.json"),
            JsonSerializer.SerializeToUtf8Bytes(source.HoldingValuationGapReport(),Json));
        if(controlledRecencyStudy)File.WriteAllBytes(Path.Combine(directory,"held-mark-evidence-counts.json"),
            JsonSerializer.SerializeToUtf8Bytes(source.FxEvidenceCounts,Json));
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
        Progress("SCENARIO_COMPLETE",p.End,books.Length,books.Length,force:true);
        if(NativeEconomicProfiler.Enabled)
            Console.WriteLine("MXM_ECONOMIC_PROFILE "+JsonSerializer.Serialize(NativeEconomicProfiler.Snapshot()));
        return 0;
    }
}

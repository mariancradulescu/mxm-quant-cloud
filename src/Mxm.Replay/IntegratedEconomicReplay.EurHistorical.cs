using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    const long HistoricalDay = 86_400_000L;
    const string ExposedDevelopment = "PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT";
    sealed record HistoricalTrial(string Id,string Policy,string Calibration,int? MinimumEpisodes,decimal? DayPenalty)
    {
        public bool UseRecoveredLocalPayoff { get; init; }
        public bool UseExtendedLocalPayoff { get; init; }
    }
    sealed record HistoricalFit(string Id,NativeEurDevelopmentProfile Profile);
    sealed record HistoricalPlan(string Study,string Exposure,string SourceProtocolSha256,string EvidenceManifestSha256,
        long InitialFitFrom,long[] TestBoundaries,decimal[] Stresses,HistoricalFit[] Calibrations,HistoricalTrial[] Trials)
    {
        public HistoricalStopWitness? StopWitness { get; init; }
        public HistoricalFundingWitness[]? FundingWitnesses { get; init; }
    }
    sealed record HistoricalStopWitness(string Symbol,int Side,long OriginalFillAt,long OriginalCloseAt,
        decimal StopDistance,long FirstTradeTouchAt);
    sealed record HistoricalFundingWitness(string PositionId,string Symbol,int Side,decimal Units,long FromExclusive,long ClosedAt);

    public static int RunHistoricalEur(string protocolPath,string sourcePath,string reportPath,string? protectionDirectory=null)
    {
        if(File.Exists(reportPath))throw new IOException("HISTORICAL_EUR_REPORT_ALREADY_EXISTS");
        byte[] protocolBytes=File.ReadAllBytes(protocolPath);
        byte[] sourceBytes=File.ReadAllBytes(sourcePath);
        var protocol=JsonSerializer.Deserialize<HistoricalPlan>(protocolBytes,Json)
            ??throw new ArgumentException("HISTORICAL_EUR_PROTOCOL_REQUIRED");
        var input=JsonSerializer.Deserialize<EerInput>(sourceBytes,Json)
            ??throw new ArgumentException("HISTORICAL_EUR_AUTHENTIC_INPUT_REQUIRED");
        var boundaries=protocol.TestBoundaries;
        if(protocol.Exposure!=ExposedDevelopment||string.IsNullOrWhiteSpace(protocol.Study)||
            protocol.SourceProtocolSha256!=input.ProtocolSha256||protocol.EvidenceManifestSha256!=input.EvidenceManifestSha256||
            input.SourceAcquiredAt<input.End||boundaries.Length<2||protocol.InitialFitFrom<input.Start||
            protocol.InitialFitFrom%HistoricalDay!=0L||boundaries[0]<=protocol.InitialFitFrom||boundaries[^1]>input.End||
            boundaries.Select((x,i)=>x%HistoricalDay!=0L||i>0&&x<=boundaries[i-1]).Any(x=>x)||
            protocol.Stresses.Length==0||protocol.Stresses.Any(s=>s<0m)||
            protocol.Stresses.Distinct().Count()!=protocol.Stresses.Length||protocol.Calibrations.Length==0||
            protocol.Trials.Length==0||protocol.Trials.Select(t=>t.Id).Distinct(StringComparer.Ordinal).Count()!=protocol.Trials.Length||
            input.Markets.Length==0||input.Markets.Any(m=>m.CalendarStatus is null||
                !VerifiedGrid(m.ScheduledClocks)||!VerifiedGrid(m.AmbiguousCalendarClocks)||
                (m.ScheduledClocks??Array.Empty<long>()).Intersect(m.AmbiguousCalendarClocks??Array.Empty<long>()).Any()||
                m.Market.DatedDevelopment?.Contract.OriginalBrokerAuthenticated!=true))
            throw new ArgumentException("HISTORICAL_EUR_CUSTODY_OR_PROTOCOL_BINDING");

        var fitProfiles=protocol.Calibrations.ToDictionary(x=>x.Id,x=>x.Profile,StringComparer.Ordinal);
        string protocolHash=GeneralSha(protocolBytes);
        EerEvidence source;
        EerProtectionTape? protection;
        using (NativeEconomicProfiler.Measure("replay.source_construction")) source=new EerEvidence(input);
        using (NativeEconomicProfiler.Measure("replay.protection_construction"))
            protection=protectionDirectory is null?null:new EerProtectionTape(protectionDirectory);
        bool explain=protection is not null;
        if(explain!=protocol.Calibrations.Any(p=>p.Profile.ModeledStopLatencyMs is not null)||
            explain!=(protocol.StopWitness is not null))throw new ArgumentException("HISTORICAL_PROTECTION_SOURCE_REQUIRED");
        if(protocol.Calibrations.Any(p=>p.Profile.ModelFundingAtPriorClosedSessionQuote) &&
            (protocol.FundingWitnesses is not { Length:>0 } || input.Markets.Any(m=>m.ClosedRolloverClocks is null)))
            throw new ArgumentException("HISTORICAL_ROLLOVER_SCENARIO_REQUIRES_DATED_SESSION_EVIDENCE");
        var stopWitness=protection?.AuditWitness(protocol.StopWitness!);
        var fundingWitnesses=protocol.FundingWitnesses?.Select(witness=>
        {
            var market=input.Markets.Single(m=>m.Market.Name==witness.Symbol);
            var terms=market.Market.DatedDevelopment!;
            var exposure=new NativeFundingExposure(witness.PositionId,witness.Symbol,witness.Side,witness.Units,
                witness.FromExclusive,0m,false,null,witness.ClosedAt,null);
            var basis=new Dictionary<(string Symbol,long ChargeAt),long>();
            var strict=source.ModeledFunding(terms,exposure,witness.ClosedAt);
            var conditional=source.ModeledFunding(terms,exposure,witness.ClosedAt,basis);
            return new {Witness=witness,StrictEur=strict,ClosedSessionScenarioEur=conditional,
                quoteBasis=StaleRolloverWitness(basis),ActualBrokerSettlementEur=(decimal?)null};
        }).ToArray();
        var output=new List<object>();
        foreach(decimal stress in protocol.Stresses)
        {
            string scenario=EerHash(protocolHash+"|"+FormattableString.Invariant($"{stress:G29}"));
            var streams=input.Markets.ToDictionary(m=>m.Market.Name,m=>new EerStream(m),StringComparer.Ordinal);
            var probes=fitProfiles.Where(p=>!p.Value.LearnFromOpportunityEpisodes).ToDictionary(p=>p.Key,p=>new NativeUnifiedPortfolioEngine(
                NativeUnifiedPortfolioEngine.EurGeneralProbe,fundingScenarioId:scenario,eurDevelopmentProfile:p.Value),
                StringComparer.Ordinal);
            var observers=fitProfiles.Where(p=>p.Value.LearnFromOpportunityEpisodes).ToDictionary(p=>p.Key,p=>
                new EurOpportunityObserver(p.Value,scenario,stress,source,protection!,streams),StringComparer.Ordinal);
            var comparison=protocol.Trials.Select(t=>
            {
                if(!GeneralPolicies.Contains(t.Policy,StringComparer.Ordinal)||!fitProfiles.TryGetValue(t.Calibration,out var p))
                    throw new ArgumentException("HISTORICAL_EUR_UNREGISTERED_TRIAL");
                if(t.UseExtendedLocalPayoff&&!t.UseRecoveredLocalPayoff ||
                    t.UseRecoveredLocalPayoff&&t.Policy!=NativeUnifiedPortfolioEngine.EurGeneralSelect)
                    throw new ArgumentException("HISTORICAL_EUR_CONTEXT_FOR_LOCAL_DISTRIBUTION");
                var profile=p with {MinimumEpisodes=t.MinimumEpisodes??p.MinimumEpisodes,DayPenalty=t.DayPenalty??p.DayPenalty,
                    UseRecoveredLocalPayoff=t.UseRecoveredLocalPayoff,UseExtendedLocalPayoff=t.UseExtendedLocalPayoff};
                return (Trial:t,Profile:profile,Book:new NativeUnifiedPortfolioEngine(t.Policy,
                    fundingScenarioId:scenario,eurDevelopmentProfile:profile));
            }).ToArray();
            var allComparisonBooks=comparison.Select(x=>x.Book).ToArray();
            var probeBooks=probes.Values.ToArray();
            var allBooks=probeBooks.Concat(allComparisonBooks).ToArray();

            void ProfileProgress(string stage,long from,long to,long processed,long total)
            {
                if(!NativeEconomicProfiler.Enabled)return;
                Console.WriteLine("HISTORICAL_EUR_PROFILE "+JsonSerializer.Serialize(new
                {
                    Stage=stage,Stress=stress,From=from,To=to,ProcessedClocks=processed,TotalClocks=total,
                    Trials=comparison.Select(x=>x.Trial.Id).ToArray(),
                    Observers=observers.Select(x=>new {Id=x.Key,Progress=x.Value.Progress()}).ToArray(),
                    Timings=NativeEconomicProfiler.Snapshot()
                },Json));
            }

            void Observe(long from,long to,NativeUnifiedPortfolioEngine[] books)
            {
                long processed=0;
                long total=Math.Max(0L,(to-from-EurOffset+EurStep-1)/EurStep);
                ProfileProgress("OBSERVE_START",from,to,processed,total);
                for(long at=from+EurOffset;at<to;at+=EurStep)
                {
                    Ucp1MarketFrame[] markets;
                    using (NativeEconomicProfiler.Measure("replay.market_frames"))
                        markets=streams.Values.Select(s=>source.Frame(s,at,scenario,stress,general:true))
                            .OfType<Ucp1MarketFrame>().ToArray();
                    var frame=new Ucp1Frame(at,markets);
                    foreach(var book in books)
                    {
                        if(protection is not null && book.ModelsEurStopOnTicks)
                        {
                            using (NativeEconomicProfiler.Measure("replay.book_tick_protection"))
                                protection.Between(book,at-1,source,streams,scenario,stress);
                            using (NativeEconomicProfiler.Measure("replay.book_advance"))
                                source.Advance(book,frame with { Protection=protection.GridCoverage(book,at) },streams,scenario,stress);
                        }
                        else
                            using (NativeEconomicProfiler.Measure("replay.book_advance"))
                                source.Advance(book,frame,streams,scenario,stress);
                    }
                    using (NativeEconomicProfiler.Measure("replay.observers"))
                        foreach(var observer in observers.Values)observer.Advance(frame);
                    processed++;
                    if(NativeEconomicProfiler.Enabled && (processed%64==0 || processed==total))
                        ProfileProgress("OBSERVE",from,to,processed,total);
                }
            }
            Observe(protocol.InitialFitFrom,boundaries[0],probeBooks);
            var fitted=new List<object>();
            for(int i=0;i+1<boundaries.Length;i++)
            {
                long start=boundaries[i];
                ProfileProgress("CALIBRATION_START",start,boundaries[i+1],0,0);
                using (NativeEconomicProfiler.Measure("replay.calibration_boundary"))
                {
                var snapshots=probes.ToDictionary(p=>p.Key,p=>p.Value.ExportEurCalibration(),StringComparer.Ordinal);
                foreach(var (id,observer) in observers)snapshots.Add(id,observer.Export());
                foreach(var (_,model) in snapshots)
                    if(model.ObservationThrough>=start || model.Outcomes.Any(x=>x.AvailableAt>=start))
                        throw new InvalidOperationException("HISTORICAL_EUR_CALIBRATION_EXPOSED_TO_OWN_TEST");
                foreach(var (trial,_,book) in comparison)
                    if(trial.Policy is NativeUnifiedPortfolioEngine.EurGeneralSelect or NativeUnifiedPortfolioEngine.EurGeneralPooled)
                    {
                        if(i==0)book.LoadEurCalibration(snapshots[trial.Calibration]);
                        else book.UpdateEurResearchCalibration(snapshots[trial.Calibration]);
                    }
                fitted.Add(new {AvailableBefore=start,Models=snapshots.Select(m=>new
                {
                    Id=m.Key, m.Value.ObservationThrough, m.Value.LedgerEventChainSha256,
                    Hash=GeneralSha(JsonSerializer.SerializeToUtf8Bytes(m.Value,Json)),
                    Episodes=m.Value.Outcomes.Length,
                    ByFamilyDirection=m.Value.Outcomes.GroupBy(o=>new{o.Family,o.Side}).Select(g=>new
                    {g.Key.Family,g.Key.Side,Count=g.Count(),GrossEur=g.Sum(x=>x.GrossEur),NetEur=g.Sum(x=>x.NetEur)}).ToArray()
                }).ToArray()});
                }
                ProfileProgress("CALIBRATION_COMPLETE",start,boundaries[i+1],0,0);
                Observe(start,boundaries[i+1],allBooks);
                Console.WriteLine($"HISTORICAL_EUR {stress:G29} TEST {i+1}/{boundaries.Length-1} completed");
            }
            ProfileProgress("SCENARIO_REPORT_START",boundaries[0],boundaries[^1],0,0);
            using (NativeEconomicProfiler.Measure("replay.scenario_report"))
            {
            var trialResults=comparison.Select(x=>new
            {
                x.Trial.Id,x.Trial.Policy,x.Trial.Calibration,x.Profile,
                Result=HistoricalBook(x.Book,boundaries)
            }).ToArray();
            var markets=streams.Values.Select(s=>new {s.Source.Market.Name,s.Source.CalendarStatus,s.Counts}).ToArray();
            if(explain)output.Add(new {SpreadMultiplier=stress, CommissionAndDebitMultiplier=1m+stress,
                Fits=fitted,Trials=trialResults,Markets=markets,
                CalibrationBooks=probes.Select(p=>new {Id=p.Key,Details=EconomicStudyDetails(p.Value,source,streams,p.Value.ExportEurCalibration())}).ToArray(),
                OpportunityObservations=observers.Select(p=>new {Id=p.Key,Details=p.Value.Report()}).ToArray(),
                TrialDetails=comparison.Select(p=>new {p.Trial.Id,Details=EconomicStudyDetails(p.Book,source,streams)}).ToArray()});
            else output.Add(new {SpreadMultiplier=stress, CommissionAndDebitMultiplier=1m+stress,
                Fits=fitted, Trials=trialResults, Markets=markets});
            }
            ProfileProgress("SCENARIO_REPORT_COMPLETE",boundaries[0],boundaries[^1],0,0);
        }
        var summary=new
        {
            protocol.Study,protocol.Exposure,ProtocolSha256=protocolHash,SourceSha256=GeneralSha(sourceBytes),
            input.EvidenceManifestSha256,input.EngineRevision,ExecutedRevision=Environment.GetEnvironmentVariable("GITHUB_SHA"),
            protocol.InitialFitFrom,protocol.TestBoundaries,DeclaredScenarioTrialCount=protocol.Stresses.Length*protocol.Trials.Length,
            Results=output,DistilledWinnerForPromotion=false,IndependentConfirmationCertified=false,
            ContinuousDrawdownCertified=false,BrokerNetCertified=false,SourceBrokerRequests=0,Orders=0,CloudActivated=false
        };
        using (NativeEconomicProfiler.Measure("replay.final_serialization"))
        using (var file=new FileStream(reportPath,FileMode.CreateNew,FileAccess.Write))
        {
        if(explain)
            JsonSerializer.Serialize(file,new {Summary=summary,StopWitness=stopWitness,FundingWitnesses=fundingWitnesses,
                Coverage="TICK_TRIGGER_AND_CONDITIONAL_FILL_WHERE_SUPPORTED_WITH_GRID_FALLBACK",
                MarkCoverage="DECISION_AND_PROTECTION_EVENT_MARKS",BrokerFillEvidence=false},Json);
        else JsonSerializer.Serialize(file,summary,Json);
        }
        if(NativeEconomicProfiler.Enabled)
            Console.WriteLine("HISTORICAL_EUR_PROFILE_FINAL "+JsonSerializer.Serialize(NativeEconomicProfiler.Snapshot(),Json));
        return 0;
    }

    static object HistoricalBook(NativeUnifiedPortfolioEngine book,long[] boundaries)
    {
        var ledger=book.ModelSummary;
        var trips=book.CompleteModelTrips;
        var related=book.ReconciledModelEpisodes.ToDictionary(o=>o.PositionId,StringComparer.Ordinal);
        var curve=book.CommonBookEquityPath;
        var cash=curve.LastOrDefault()?.FundingCapital;
        var funding=book.FundingExposureSnapshot();
        var observations=curve.Where(p=>p.FundingCapital?.ConditionalEquityEur is >0m&&p.UsedMarginEur.HasValue)
            .Select(p=>(p.UsedMarginEur!.Value+p.FundingCapital!.PendingOpenMarginEur)/p.FundingCapital.ConditionalEquityEur!.Value)
            .ToArray();
        decimal? Net(IEnumerable<Ucp1Episode> positions)
        {
            decimal total=0m;
            foreach(var position in positions)
            {
                if(related.GetValueOrDefault(position.PositionId)?.Evidence.ClosedNetEur is not decimal value)
                    return null;
                total+=value;
            }
            return total;
        }
        const long week=604_800_000L;
        var weeks=trips.GroupBy(p=>Week(p.CloseAt)).ToDictionary(g=>g.Key,g=>g.ToArray(),StringComparer.Ordinal);
        long monday=boundaries[0]+(7L-(boundaries[0]/HistoricalDay+3L)%7L)%7L*HistoricalDay;
        var weekly=Enumerable.Range(0,(int)Math.Max(0L,(boundaries[^1]-monday)/week)).Select(i=>
        {
            string id=Week(monday+i*week);
            var closed=weeks.GetValueOrDefault(id)??Array.Empty<Ucp1Episode>();
            return new {Week=id,Rounds=closed.Length,Hard21=closed.Length>=21,
                GrossEur=closed.Sum(t=>t.GrossEur),NetEur=Net(closed)};
        }).ToArray();
        var folds=boundaries.Zip(boundaries.Skip(1)).Select(range=>
        {
            var closed=trips.Where(t=>t.CloseAt>=range.First&&t.CloseAt<range.Second).ToArray();
            return new {From=range.First,Through=range.Second,Rounds=closed.Length,
                GrossEur=closed.Sum(t=>t.GrossEur),NetEur=Net(closed)};
        }).ToArray();
        return new
        {
            ledger.CashEur,ledger.EventChainHash,ledger.OpenPositions,ledger.PendingIntents,
            InitialCapitalEur=OwnerRiskAuthority.InitialCapitalEur,
            Closed=trips.Length,ClosedGrossEur=trips.Sum(t=>t.GrossEur),ClosedNetEur=Net(trips),
            AllTerminalNetEur=ledger.OpenPositions==0&&ledger.PendingIntents==0&&funding.All(f=>f.ExactInLedger)?Net(trips):null,
            UnknownFundingWindows=funding.Count(f=>!f.ExactInLedger),
            UnknownEquityClocks=curve.Count(p=>p.FundingCapital?.ConditionalEquityEur is null),
            SampledDrawdown=cash?.MaximumSampledFundingAdjustedDrawdown,
            MaxSampledHeldPendingMarginFraction=observations.Length>0?observations.Max():(decimal?)null,
            MeanSampledHeldPendingMarginFraction=observations.Length>0?observations.Average():(decimal?)null,
            BeyondFillRisk=related.Values.Count(t=>t.Evidence.ClosedNetEur is decimal n&&-n>t.Evidence.ReservedRiskEur),
            Gaps=trips.Count(p=>p.CrossedUnknownHistory),Reductions=trips.Count(p=>p.Integrated?.PartialReduction==true),
            CommissionEur=trips.Sum(p=>p.Integrated?.CommissionsEur??0m),
            SpreadEur=trips.Sum(p=>p.Integrated?.SpreadEur??0m),
            SlippageEur=trips.Sum(p=>p.Integrated?.SlippageEur??0m),
            ConversionEur=trips.Sum(p=>p.Integrated?.ConversionEur??0m),
            FundingSettlementsEur=cash?.PostedFinancingEur,
            Hard21AllFullRegisteredWeeks=weekly.Length>0&&weekly.All(w=>w.Hard21),Weeks=weekly,Folds=folds,
            NativeDecisions=book.ResearchDecisionCounts,
            ExitReasons=trips.GroupBy(p=>p.ExitReason).ToDictionary(g=>g.Key,g=>g.Count()),
            ByMarketFamily=trips.GroupBy(p=>new{p.Symbol,p.Family,p.Side}).Select(g=>new
            {g.Key.Symbol,g.Key.Family,g.Key.Side,Rounds=g.Count(),GrossEur=g.Sum(p=>p.GrossEur),NetEur=Net(g)}).ToArray()
        };
    }
}

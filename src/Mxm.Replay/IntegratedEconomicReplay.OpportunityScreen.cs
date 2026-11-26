using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record OpportunityVariant(string Id,string Mechanism,NativeEurDevelopmentProfile Profile,bool Reference);
    sealed record OpportunityScreenPlan(string Study,string Exposure,string SourceProtocolSha256,string EvidenceManifestSha256,
        long Start,long SelectionFrom,long EvaluationFrom,long End,long SamplingIntervalMs,
        decimal[] Stresses,OpportunityVariant[] Variants);
    sealed record ScreenAttempt(long At,string Symbol,string Family,int Side,string Status,
        NativeEurOpportunity? Entry=null,NativeEurPayoff? Score=null,NativeEurCalibrationOutcome? Label=null,
        Ucp1Episode? Trip=null,long? FirstPositiveAt=null,long? FirstNegativeAt=null,long? PeakAt=null,
        int PositiveClocks=0,int NegativeClocks=0,int UnknownClocks=0,long? ResolvedAt=null);
    sealed record ScreenActive(ScreenAttempt Attempt,NativeUnifiedPortfolioEngine Book);

    // Isolated, actual native lifecycle observations. Each attempt gets its own
    // model book solely to observe a counterfactual; this is NOT common equity.
    sealed class OpportunityScreenState(OpportunityVariant variant,string scenario,decimal stress,
        EerEvidence source,EerProtectionTape protection,Dictionary<string,EerStream> streams,long interval,
        IEnumerable<NativeEurCalibrationOutcome>? seed=null)
    {
        readonly Dictionary<string,ScreenActive> active=new(StringComparer.Ordinal);
        readonly List<ScreenAttempt> attempts=new();
        readonly List<NativeEurCalibrationOutcome> labels=seed?.ToList()??new();
        readonly Dictionary<(string Symbol,string Family,int Side),List<NativeEurCalibrationOutcome>> histories=
            (seed??Array.Empty<NativeEurCalibrationOutcome>()).Where(l=>l.Context is not null)
                .GroupBy(l=>(l.Context!.Symbol,l.Family,l.Side)).ToDictionary(g=>g.Key,g=>g.ToList());
        readonly NativeUnifiedPortfolioEngine descriptor=new(NativeUnifiedPortfolioEngine.EurGeneralProbe,
            fundingScenarioId:scenario,eurDevelopmentProfile:variant.Profile);
        public OpportunityVariant Variant=>variant;
        public decimal Stress=>stress;
        public NativeEurCalibrationOutcome[] MaturedBefore(long cutoff)=>labels.Where(x=>x.AvailableAt<cutoff).ToArray();

        public void Advance(Ucp1Frame frame)
        {
            foreach(var (symbol,item) in active.ToArray())
            {
                var book=item.Book;
                protection.Between(book,frame.At-1,source,streams,scenario,stress);
                source.Advance(book,frame with {ObservationEpisodeOnly=true,Protection=protection.GridCoverage(book,frame.At)},
                    streams,scenario,stress);
                if(book.ModelSummary.OpenPositions+book.ModelSummary.PendingIntents>0)continue;
                active.Remove(symbol);
                var trip=book.CompleteModelTrips.SingleOrDefault();
                if(trip is null)
                {
                    attempts.Add(item.Attempt with {Status="UNFILLED",ResolvedAt=frame.At});
                    continue;
                }
                var label=book.ExportEurCalibration().Outcomes.SingleOrDefault();
                // A complete price path and reconciled funding are both required for a selection label.
                if(trip.CrossedUnknownHistory||trip.EconomicEvidence?.MarkCoverageComplete!=true)label=null;
                if(label is not null)
                {
                    labels.Add(label);
                    if(label.Context is not null)
                    {
                        var key=(label.Context.Symbol,label.Family,label.Side);
                        if(!histories.TryGetValue(key,out var h))histories.Add(key,h=new());
                        h.Add(label);
                    }
                }
                var path=book.CommonBookEquityPath.Where(x=>x.At>=trip.OpenAt&&x.At<=trip.CloseAt).ToArray();
                var known=path.Where(x=>x.FundingCapital?.ConditionalEquityEur is not null).ToArray();
                var positive=known.Where(x=>x.FundingCapital!.ConditionalEquityEur>300m).ToArray();
                var negative=known.Where(x=>x.FundingCapital!.ConditionalEquityEur<300m).ToArray();
                attempts.Add(item.Attempt with {Status=label is null?"UNKNOWN_CLOSED":"RECONCILED",
                    Label=label,Trip=trip,ResolvedAt=frame.At,FirstPositiveAt=positive.FirstOrDefault()?.At,
                    FirstNegativeAt=negative.FirstOrDefault()?.At,
                    PeakAt=known.OrderByDescending(x=>x.FundingCapital!.ConditionalEquityEur).FirstOrDefault()?.At,
                    PositiveClocks=positive.Length,NegativeClocks=negative.Length,UnknownClocks=path.Length-known.Length});
            }
            if(frame.At%interval!=EurOffset)return;
            // The sampling clock and overlap rule are registered before any outcome.
            var available=frame.Markets.ToDictionary(m=>m.Symbol,StringComparer.Ordinal);
            foreach(string symbol in streams.Keys.OrderBy(x=>x,StringComparer.Ordinal))
            {
                if(!available.TryGetValue(symbol,out var market))
                {
                    attempts.Add(new(frame.At,symbol,variant.Mechanism,0,"NO_MONETARY_FRAME:"+
                        streams[symbol].Availability.GetValueOrDefault(frame.At,"UNOBSERVED")));
                    continue;
                }
                var offers=descriptor.DescribeEurGeneral(market,frame.At,frame);
                if(offers.Length==0)
                {attempts.Add(new(frame.At,symbol,variant.Mechanism,0,"WAIT_NO_SIGNAL"));continue;}
                if(offers.Length!=1)throw new InvalidOperationException("OPPORTUNITY_SCREEN_ONE_MECHANISM_SIGNAL");
                var offer=offers[0];
                var attempt=new ScreenAttempt(frame.At,symbol,offer.Family,offer.Side,"PENDING");
                if(active.ContainsKey(symbol))
                {attempts.Add(attempt with {Status="WAIT_ISOLATED_OVERLAP"});continue;}
                var episode=new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
                    fundingScenarioId:scenario,eurDevelopmentProfile:variant.Profile);
                source.Advance(episode,frame with {ObservationEpisodeOnly=true,OpportunityToObserve=offer},
                    streams,scenario,stress);
                if(episode.ModelSummary.PendingIntents==0)
                {
                    var reasons=string.Join("|",episode.ResearchDecisionCounts.Keys.OrderBy(x=>x,StringComparer.Ordinal));
                    attempts.Add(attempt with {Status="WAIT_NOT_ADMITTED:"+reasons});continue;
                }
                var receipt=episode.EurOpportunityReceipts.SingleOrDefault(x=>x.At==frame.At&&
                    x.Symbol==symbol&&x.Family==offer.Family&&x.Side==offer.Side&&(x.Decision is "LONG_PENDING" or "SHORT_PENDING"));
                if(receipt is null)throw new InvalidOperationException("OPPORTUNITY_SCREEN_ADMISSION_RECEIPT");
                NativeEurPayoff? score=null;
                if(receipt.Context is { } context&&receipt.ReservedRiskEur is >0m&&receipt.NextManagementFundingCeilingEur is decimal carry&&
                    histories.TryGetValue((symbol,offer.Family,offer.Side),out var history))
                    score=NativeEconomicMechanisms.LifecyclePayoff(history,offer.Family,offer.Side,context,frame.At,
                        receipt.ReservedRiskEur.Value,receipt.KnownRoundTripCostEur+carry,
                        variant.Profile.MinimumEpisodes,variant.Profile.MinimumDays,variant.Profile.DayPenalty);
                active.Add(symbol,new(attempt with {Entry=receipt,Score=score},episode));
            }
        }

        public ScreenAttempt[] Rows(long from,long to)
            =>attempts.Concat(active.Values.Select(x=>x.Attempt with {Status="RIGHT_CENSORED"}))
                .Where(x=>from<=x.At&&x.At<to)
                .Select(x=>(x.Label is { } l&&l.AvailableAt>=to)||x.ResolvedAt>=to||x.Trip is { } t&&t.CloseAt>=to
                    ?x with {Status="RIGHT_CENSORED",Label=null,Trip=null,FirstPositiveAt=null,FirstNegativeAt=null,
                        PeakAt=null,PositiveClocks=0,NegativeClocks=0,UnknownClocks=0,ResolvedAt=null}:x).ToArray();
    }

    static bool ScpAdmits(ScreenAttempt a)=>a.Score is {GrossLowerEur:>0m,NetLowerEur:>0m};
    sealed record OpportunityStats(int Attempts,int NoFrame,int NoSignal,int Overlap,int NotAdmitted,
        int Admitted,int Unfilled,int Censored,int UnknownClosed,int KnownClosed,int PositiveNet,
        decimal GrossEur,decimal NetEur,decimal CostEur,decimal? MeanNetEur,decimal? MeanMfeEur,
        decimal? MeanMaeEur,decimal? GrossToSampledMfe,decimal? MeanDurationMinutes,int CompleteDays,
        decimal? MeanDailyNetEur,decimal? DailyNetLowerEur,int ProfitableDays,int ScoreUnsupported,int ScoreNonpositive,
        int ScoreAdmitted,decimal? MeanConditionalWinEur,decimal? MeanConditionalLossEur);
    static OpportunityStats ScreenStats(ScreenAttempt[] rows,bool scored)
    {
        bool Admits(ScreenAttempt a)=>a.Entry is not null&&(!scored||ScpAdmits(a));
        var admitted=rows.Where(Admits).ToArray();
        var known=admitted.Where(a=>a.Label is not null&&a.Trip is not null).ToArray();
        decimal gross=known.Sum(a=>a.Label!.GrossEur),net=known.Sum(a=>a.Label!.NetEur);
        decimal mfe=known.Sum(a=>Math.Max(0m,a.Trip!.SampledMfeEur));
        var days=rows.Where(a=>!a.Status.StartsWith("NO_MONETARY_FRAME:",StringComparison.Ordinal)).GroupBy(a=>a.At/HistoricalDay)
            .Where(day=>day.All(a=>!Admits(a)||a.Label is not null||a.Status=="UNFILLED"))
            .Select(day=>day.Where(a=>Admits(a)&&a.Label is not null).Sum(a=>a.Label!.NetEur)).ToArray();
        decimal? mean=days.Length==0?null:days.Average();
        decimal? lower=days.Length<2?null:mean!.Value-1.645m*(decimal)Math.Sqrt(days.Sum(d=>Math.Pow((double)(d-mean.Value),2))/
            (days.Length*(days.Length-1d)));
        var wins=known.Where(a=>a.Label!.NetEur>0m).ToArray();
        var losses=known.Where(a=>a.Label!.NetEur<0m).ToArray();
        return new(rows.Length,rows.Count(a=>a.Status.StartsWith("NO_MONETARY_FRAME:",StringComparison.Ordinal)),rows.Count(a=>a.Status=="WAIT_NO_SIGNAL"),
            rows.Count(a=>a.Status=="WAIT_ISOLATED_OVERLAP"),rows.Count(a=>a.Status.StartsWith("WAIT_NOT_ADMITTED:",StringComparison.Ordinal)),
            admitted.Length,admitted.Count(a=>a.Status=="UNFILLED"),admitted.Count(a=>a.Status=="RIGHT_CENSORED"),
            admitted.Count(a=>a.Status=="UNKNOWN_CLOSED"),known.Length,wins.Length,gross,net,gross-net,
            known.Length==0?null:net/known.Length,known.Length==0?null:known.Average(a=>a.Trip!.SampledMfeEur),
            known.Length==0?null:known.Average(a=>a.Trip!.SampledMaeEur),mfe>0m?gross/mfe:null,
            known.Length==0?null:known.Average(a=>(a.Trip!.CloseAt-a.Trip.OpenAt)/60000m),
            days.Length,mean,lower,days.Count(x=>x>0m),rows.Count(a=>a.Entry is not null&&a.Score is null),
            rows.Count(a=>a.Entry is not null&&a.Score is not null&&!ScpAdmits(a)),rows.Count(ScpAdmits),
            wins.Length==0?null:wins.Average(a=>a.Label!.NetEur),losses.Length==0?null:losses.Average(a=>a.Label!.NetEur));
    }

    static object PairedScreen(ScreenAttempt[] candidate,ScreenAttempt[] reference)
    {
        var a=candidate.Where(x=>x.Label is not null).ToDictionary(x=>(x.At,x.Symbol,x.Family,x.Side));
        var b=reference.Where(x=>x.Label is not null).ToDictionary(x=>(x.At,x.Symbol,x.Family,x.Side));
        var common=a.Keys.Intersect(b.Keys).ToArray();
        return new
        {
            MatchedDecisionSymbolFamilySide=common.Length,CandidateOnly=a.Count-common.Length,ReferenceOnly=b.Count-common.Length,
            MatchedGrossDifferenceEur=common.Length==0?(decimal?)null:common.Sum(k=>a[k].Label!.GrossEur-b[k].Label!.GrossEur),
            MatchedNetDifferenceEur=common.Length==0?(decimal?)null:common.Sum(k=>a[k].Label!.NetEur-b[k].Label!.NetEur),
            MatchedEntryUnitsDifference=common.Length==0?(decimal?)null:common.Sum(k=>a[k].Entry!.Units-b[k].Entry!.Units),
            MatchedMeanDurationDifferenceMinutes=common.Length==0?(decimal?)null:common.Average(k=>
                ((a[k].Trip!.CloseAt-a[k].Trip!.OpenAt)-(b[k].Trip!.CloseAt-b[k].Trip!.OpenAt))/60000m),
            ConditionalMatchedClosedPathsOnly=true,UnmatchedOrUnknownNotImputed=true
        };
    }

    static object ScreenReasons(ScreenAttempt[] rows)=>rows.GroupBy(x=>x.Status).ToDictionary(g=>g.Key,g=>g.Count(),StringComparer.Ordinal);

    public static int RunOpportunityScreen(string protocolPath,string sourcePath,string reportPath,string protectionDirectory)
    {
        if(File.Exists(reportPath))throw new IOException("OPPORTUNITY_SCREEN_REPORT_EXISTS");
        byte[] planBytes=File.ReadAllBytes(protocolPath),sourceBytes=File.ReadAllBytes(sourcePath);
        var plan=JsonSerializer.Deserialize<OpportunityScreenPlan>(planBytes,Json)??throw new ArgumentException("OPPORTUNITY_SCREEN_PLAN");
        var input=JsonSerializer.Deserialize<EerInput>(sourceBytes,Json)??throw new ArgumentException("OPPORTUNITY_SCREEN_SOURCE");
        if(plan.Study!="MONETARY_OPPORTUNITY_DISCOVERY_1"||plan.Exposure!=ExposedDevelopment||
            input.ProtocolSha256!=plan.SourceProtocolSha256||input.EvidenceManifestSha256!=plan.EvidenceManifestSha256||
            input.SourceAcquiredAt<input.End||plan.Start<input.Start||plan.End>input.End||
            !(plan.Start<plan.SelectionFrom&&plan.SelectionFrom<plan.EvaluationFrom&&plan.EvaluationFrom<plan.End)||
            plan.SamplingIntervalMs!=3600000L||!plan.Stresses.SequenceEqual(new[]{0m,.5m,1m})||
            new[]{plan.Start,plan.SelectionFrom,plan.EvaluationFrom,plan.End}.Any(x=>x%HistoricalDay!=0)||
            input.Markets.Any(m=>m.Market.DatedDevelopment?.Contract.OriginalBrokerAuthenticated!=true||
                m.ClosedRolloverClocks is null||m.CalendarStatus is null||!VerifiedGrid(m.ScheduledClocks)||!VerifiedGrid(m.AmbiguousCalendarClocks))||
            plan.Variants.Length==0||plan.Variants.Select(v=>v.Id).Distinct().Count()!=plan.Variants.Length||
            plan.Variants.Any(v=>v.Profile.EconomicMechanism!=v.Mechanism||v.Mechanism==NativeEconomicMechanisms.Scored||
                v.Profile.ModeledStopLatencyMs is null||!v.Profile.ObserveIntentExecutionOnTicks||
                !v.Profile.ModelFundingAtPriorClosedSessionQuote||v.Profile.LearnFromOpportunityEpisodes||
                v.Profile.CaptureStudyDiagnostics))
            throw new ArgumentException("OPPORTUNITY_SCREEN_BINDING");
        string mechanism=Environment.GetEnvironmentVariable("MXM_OPPORTUNITY_MECHANISM")??throw new ArgumentException("OPPORTUNITY_SCREEN_PARTITION");
        var variants=plan.Variants.Where(x=>x.Mechanism==mechanism).ToArray();
        if(variants.Length==0||variants.Count(v=>v.Reference)!=1)throw new ArgumentException("OPPORTUNITY_SCREEN_VARIANTS");
        string planHash=GeneralSha(planBytes),sourceHash=GeneralSha(sourceBytes);
        var source=new EerEvidence(input);
        var protection=new EerProtectionTape(protectionDirectory);
        var runs=plan.Stresses.Select(stress=>
        {
            string scenario=EerHash(planHash+"|"+FormattableString.Invariant($"{stress:G29}"));
            var streams=input.Markets.ToDictionary(m=>m.Market.Name,m=>new EerStream(m),StringComparer.Ordinal);
            return (Stress:stress,Scenario:scenario,Streams:streams,States:variants.Select(v=>
                new OpportunityScreenState(v,scenario,stress,source,protection,streams,plan.SamplingIntervalMs)).ToArray());
        }).ToArray();
        void Observe(long from,long to)
        {
            long n=0;
            for(long at=from+EurOffset;at<to;at+=EurStep)
            {
                source.BeginHistoricalClock();
                foreach(var run in runs)
                {
                    var frames=run.Streams.Values.Select(s=>source.Frame(s,at,run.Scenario,run.Stress,general:true))
                        .OfType<Ucp1MarketFrame>().ToArray();
                    var frame=new Ucp1Frame(at,frames);
                    foreach(var state in run.States)state.Advance(frame);
                }
                if(++n%288==0)Console.WriteLine($"OPPORTUNITY_SCREEN {mechanism} clock={at} processed={n} through={to}");
            }
        }
        Observe(plan.Start,plan.EvaluationFrom);
        var fit=runs.SelectMany(r=>r.States.Select(s=>new {r.Stress,s.Variant.Id,Raw=ScreenStats(s.Rows(plan.Start,plan.SelectionFrom),false),
            Scp1=ScreenStats(s.Rows(plan.Start,plan.SelectionFrom),true)})).ToArray();
        var selection=runs.SelectMany(r=>r.States.Select(s=>
        {
            var rows=s.Rows(plan.SelectionFrom,plan.EvaluationFrom);
            var baseline=r.States.Single(x=>x.Variant.Reference).Rows(plan.SelectionFrom,plan.EvaluationFrom);
            var capture=r.States.SingleOrDefault(x=>x.Variant.Id.EndsWith("__SPECIFIC_CAPTURE",StringComparison.Ordinal));
            return new {r.Stress,s.Variant.Id,Raw=ScreenStats(rows,false),Scp1=ScreenStats(rows,true),
                Reasons=ScreenReasons(rows),PairedReference=PairedScreen(rows,baseline),
                PairedMarginalVolume=s.Variant.Id.EndsWith("__MARGINAL_VOLUME",StringComparison.Ordinal)&&capture is not null
                    ?PairedScreen(rows,capture.Rows(plan.SelectionFrom,plan.EvaluationFrom)):null};
        })).ToArray();
        // Same candidate is selected across all cost scenarios. WAIT remains
        // a zero-exposure alternative; negative champions are diagnostics only.
        var candidates=variants.SelectMany(v=>new[]{false,true}.Select(scored=>
        {
            var stats=selection.Where(s=>s.Id==v.Id).Select(s=>scored?s.Scp1:s.Raw).ToArray();
            decimal? score=stats.All(s=>s.KnownClosed>0&&s.DailyNetLowerEur.HasValue)
                ?stats.Min(s=>s.DailyNetLowerEur):null;
            return new {v.Id,Scored=scored,Score=score,KnownGrossPositive=stats.All(s=>s.GrossEur>0m)};
        })).ToArray();
        var ordered=candidates.Where(c=>c.Score.HasValue)
            .OrderByDescending(c=>c.Score).ThenBy(c=>c.Id,StringComparer.Ordinal).ThenBy(c=>c.Scored).ToArray();
        var bestRaw=ordered.FirstOrDefault(c=>!c.Scored);
        var bestScp=ordered.FirstOrDefault(c=>c.Scored);
        var accepted=ordered.FirstOrDefault(c=>c.Score>0m&&c.KnownGrossPositive);
        var selected=variants.Where(v=>v.Reference||v.Id==bestRaw?.Id||v.Id==bestScp?.Id||v.Id==accepted?.Id).ToArray();
        if(selected.Any(v=>v.Id.EndsWith("__MARGINAL_VOLUME",StringComparison.Ordinal)))
            selected=selected.Concat(variants.Where(v=>v.Id.EndsWith("__SPECIFIC_CAPTURE",StringComparison.Ordinal)))
                .DistinctBy(v=>v.Id).ToArray();
        // New independent episode cohorts begin at the chronological holdout.
        // No open pre-boundary attempt is treated as a closed outcome.
        for(int i=0;i<runs.Length;i++)
        {
            var r=runs[i];
            runs[i]=(r.Stress,r.Scenario,r.Streams,selected.Select(v=>
                new OpportunityScreenState(v,r.Scenario,r.Stress,source,protection,r.Streams,plan.SamplingIntervalMs,
                    r.States.Single(s=>s.Variant.Id==v.Id).MaturedBefore(plan.EvaluationFrom))).ToArray());
        }
        Observe(plan.EvaluationFrom,plan.End);
        var held=runs.SelectMany(r=>r.States.Select(s=>
        {
            var rows=s.Rows(plan.EvaluationFrom,plan.End);
            var baseline=r.States.Single(x=>x.Variant.Reference).Rows(plan.EvaluationFrom,plan.End);
            var capture=r.States.SingleOrDefault(x=>x.Variant.Id.EndsWith("__SPECIFIC_CAPTURE",StringComparison.Ordinal));
            return new {r.Stress,s.Variant.Id,Raw=ScreenStats(rows,false),Scp1=ScreenStats(rows,true),
                Reasons=ScreenReasons(rows),PairedReference=PairedScreen(rows,baseline),
                PairedMarginalVolume=s.Variant.Id.EndsWith("__MARGINAL_VOLUME",StringComparison.Ordinal)&&capture is not null
                    ?PairedScreen(rows,capture.Rows(plan.EvaluationFrom,plan.End)):null,
                Episodes=rows.Where(a=>a.Entry is not null).Select(a=>new
                {
                    a.At,a.Symbol,a.Family,a.Side,a.Status,Units=a.Entry!.Units,a.Entry.ReservedRiskEur,
                    a.Entry.KnownRoundTripCostEur,a.Entry.CurrentMarginEstimateEur,
                    RiskAtFillEur=a.Trip?.EntryRiskEur,Gap=a.Trip?.CrossedUnknownHistory,PartialReduction=a.Trip?.Integrated?.PartialReduction,
                    ScoreNetLowerEur=a.Score?.NetLowerEur,ScoreGrossLowerEur=a.Score?.GrossLowerEur,Scp1Admitted=ScpAdmits(a),
                    AvailableAt=a.Label?.AvailableAt,NetEur=a.Label?.NetEur,GrossEur=a.Label?.GrossEur,
                    OpenAt=a.Trip?.OpenAt,CloseAt=a.Trip?.CloseAt,SampledMfeEur=a.Trip?.SampledMfeEur,SampledMaeEur=a.Trip?.SampledMaeEur,
                    ExitReason=a.Trip?.ExitReason,FirstBarrier=a.Trip?.Integrated?.FirstObservedBarrier,
                    a.FirstPositiveAt,a.FirstNegativeAt,a.PeakAt,a.PositiveClocks,a.NegativeClocks,a.UnknownClocks
                }).ToArray()};
        })).ToArray();
        File.WriteAllBytes(reportPath,JsonSerializer.SerializeToUtf8Bytes(new
        {
            plan.Study,Mechanism=mechanism,plan.Start,plan.SelectionFrom,plan.EvaluationFrom,plan.End,
            plan.SamplingIntervalMs,ProtocolSha256=planHash,SourceSha256=sourceHash,input.EvidenceManifestSha256,
            Variants=variants,Fit=fit,Selection=selection,Candidates=candidates,BestRawDiagnostic=bestRaw,
            BestScp1Diagnostic=bestScp,SelectedDecision=accepted is null?"WAIT":accepted.Id+(accepted.Scored?"/SCP1":"/RAW"),
            HeldOut=held,Scp1Scope="CAUSAL_SHADOW_GATE_ON_ISOLATED_EPISODES_NOT_COMMON_BOOK",
            Scp1OverlapLimitation="SHADOW_WAIT_DOES_NOT_RELEASE_RAW_OBSERVER_SLOT; NOT_AN_EXECUTED_SCORED_POLICY",
            Missingness="NO_FRAME_AND_UNRESOLVED_EXCLUDED_FROM_CONDITIONAL_MEANS; CENSORED_NOT_ZERO",
            CompleteDaysBasis="OBSERVED_MONETARY_CLOCKS_WITH_NO_UNRESOLVED_ADMITTED_EPISODES",
            MfeBasis="SAMPLED_REALIZED_EPISODE_PATH_NOT_EXECUTABLE_MAXIMUM",
            SharedPortfolioEvaluations=0,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false,SourceBrokerRequests=0
        },Json));
        return 0;
    }
}

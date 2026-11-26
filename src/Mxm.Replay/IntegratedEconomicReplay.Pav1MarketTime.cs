using System.Text.Json;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record PavMarketVariant(string Id,int UniverseCount,NativeEurDevelopmentProfile Profile);
    sealed record PavMarketPlan(string Study,string Exposure,string SourceProtocolSha256,string EvidenceManifestSha256,
        long Start,long SelectionFrom,long EvaluationFrom,long End,decimal[] Stresses,string[] OriginalInstruments,
        PavMarketVariant[] Variants);
    sealed record PavMarketCase(PavMarketVariant Variant,NativeUnifiedPortfolioEngine Book,EerEvidence Source,
        Dictionary<string,EerStream> Streams,string Scenario);

    static object PavCashScore(NativeUnifiedPortfolioEngine book,long from,long through)
    {
        var trips=book.CompleteModelTrips.Where(t=>t.CloseAt>=from&&t.CloseAt<through).ToArray();
        var settled=book.ReconciledModelEpisodes.Where(e=>e.AvailableAt<through).ToDictionary(e=>e.PositionId);
        decimal? Net(IEnumerable<Ucp1Episode> rows)
        {
            decimal n=0m;
            foreach(var t in rows)
            {if(settled.GetValueOrDefault(t.PositionId)?.Evidence.ClosedNetEur is not decimal value)return null;n+=value;}
            return n;
        }
        var daily=Enumerable.Range(0,(int)((through-from)/HistoricalDay)).Select(i=>
        {
            long day=from+i*HistoricalDay;
            var closed=trips.Where(t=>t.CloseAt>=day&&t.CloseAt<day+HistoricalDay).ToArray();
            return new {Day=day,Closed=closed.Length,GrossEur=closed.Sum(t=>t.GrossEur),NetEur=Net(closed)};
        }).ToArray();
        var days=daily.Where(d=>d.NetEur.HasValue).Select(d=>d.NetEur!.Value).ToArray();
        decimal? net=Net(trips),mean=days.Length>0?days.Average():null;
        decimal? lower=days.Length>1?mean!.Value-1.645m*(decimal)Math.Sqrt(days.Sum(d=>Math.Pow((double)(d-mean.Value),2))/
            (days.Length*(days.Length-1d))):null;
        var terminal=book.CommonBookEquityPath.LastOrDefault()?.FundingCapital;
        decimal? capitalGain=terminal?.ConditionalEquityEur-300m;
        bool fullyKnown=net.HasValue&&daily.All(d=>d.NetEur.HasValue)&&capitalGain.HasValue&&book.FundingExposureSnapshot().All(w=>w.ExactInLedger);
        decimal? score=fullyKnown&&trips.Length>0&&lower.HasValue?Math.Min(lower.Value,
            Math.Min(net!.Value,capitalGain!.Value)/Math.Max(1m,daily.Length)):null;
        return new {Closed=trips.Length,GrossEur=trips.Sum(t=>t.GrossEur),NetEur=net,Daily=daily,
            Days=daily.Length,KnownDays=days.Length,MeanDailyClosedNetEur=mean,DailyClosedNetLowerEur=lower,
            TerminalConditionalEquityGainEur=capitalGain,UnresolvedWindows=book.FundingExposureSnapshot().Count(w=>!w.ExactInLedger),
            Score=score,FullyKnownConditionalMonetaryEvidence=fullyKnown,
            Limitation="RESEARCH_ONLY_DAY_CLUSTER_STATISTIC; NO_INDEPENDENT_CONFIRMATION; TERMINAL_EQUITY_INCLUDES_OPEN_HOLDINGS"};
    }

    public static int RunPavMarketTime(string protocolPath,string sourcePath,string directory,string protectionDirectory,string stressText)
    {
        var planBytes=File.ReadAllBytes(protocolPath);var sourceBytes=File.ReadAllBytes(sourcePath);
        var p=JsonSerializer.Deserialize<PavMarketPlan>(planBytes,Json)!;
        var input=JsonSerializer.Deserialize<EerInput>(sourceBytes,Json)!;
        decimal stress=decimal.Parse(stressText,System.Globalization.CultureInfo.InvariantCulture);
        bool Grid(long[]? rows)=>rows is null||rows.SequenceEqual(rows.OrderBy(x=>x).Distinct())&&
            rows.All(t=>t>=input.Start&&t<input.End+7*HistoricalDay&&t%EurStep==EurOffset);
        if(p.Study!="PAV1_MARKET_TIME_FX_1"||p.Exposure!="PROJECT_EXPOSED_CONDITIONAL_DEVELOPMENT"||
            p.SourceProtocolSha256!=input.ProtocolSha256||p.EvidenceManifestSha256!=input.EvidenceManifestSha256||
            p.Start!=input.Start||p.End!=input.End||!(p.Start<p.SelectionFrom&&p.SelectionFrom<p.EvaluationFrom&&p.EvaluationFrom<p.End)||
            input.Markets.Length!=25||p.OriginalInstruments.Length!=21||p.OriginalInstruments.Distinct().Count()!=21||
            p.OriginalInstruments.Any(n=>!input.Markets.Any(m=>m.Market.Name==n))||!input.ExtendedEconomicContext||
            !p.Stresses.SequenceEqual(new[]{0m,.5m,1m})||!p.Stresses.Contains(stress)||
            p.Variants.Length!=13||p.Variants.Select(v=>v.Id).Distinct().Count()!=13||
            input.Markets.Any(m=>!Grid(m.ScheduledClocks)||!Grid(m.AmbiguousCalendarClocks))||
            p.Variants.Any(v=>v.UniverseCount is not (21 or 25)||v.Profile.EconomicMechanism!=NativeEconomicMechanisms.Transition||
                !v.Profile.KeepAdmissionRiskAtFill||!v.Profile.ResizeWithinAdmissionRiskAtFill||
                v.Profile.ModelFundingAtPriorClosedSessionQuote||!v.Profile.ObserveIntentExecutionOnTicks||v.Profile.ModeledStopLatencyMs is null||
                v.Profile.LearnFromOpportunityEpisodes||v.Profile.CaptureStudyDiagnostics))
            throw new ArgumentException("PAV1_MARKET_TIME_BINDING");
        string planHash=GeneralSha(planBytes),sourceHash=GeneralSha(sourceBytes);
        Directory.CreateDirectory(directory);
        var tape=new EerProtectionTape(protectionDirectory);
        var sources=new[]{new EerEvidence(input),new EerEvidence(input){MarketTimeFx=true,ValuationTape=tape}};
        var streamsByCount=new[]{21,25}.ToDictionary(count=>count,count=>input.Markets.Where(m=>count==25||p.OriginalInstruments.Contains(m.Market.Name))
            .ToDictionary(m=>m.Market.Name,m=>new EerStream(m),StringComparer.Ordinal));
        var cases=p.Variants.Select(v=>
        {
            string scenario=EerHash(planHash+"|"+FormattableString.Invariant($"{stress:G29}"));
            return new PavMarketCase(v,new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralProbe,
                fundingScenarioId:scenario,eurDevelopmentProfile:v.Profile),sources[v.Profile.UseMarketTimeFxValuation?1:0],streamsByCount[v.UniverseCount],scenario);
        }).ToList();
        foreach(bool conditional in new[]{false,true})
        {
            var profile=p.Variants.First(v=>v.Profile.UseMarketTimeFxValuation==conditional).Profile;
            var v=new PavMarketVariant(conditional?"CASH_MARKET_TIME":"CASH_STRICT",25,profile);
            string scenario=EerHash(planHash+"|"+FormattableString.Invariant($"{stress:G29}"));
            cases.Add(new(v,new NativeUnifiedPortfolioEngine(NativeUnifiedPortfolioEngine.EurGeneralCash,
                fundingScenarioId:scenario,eurDevelopmentProfile:profile),sources[conditional?1:0],streamsByCount[25],scenario));
        }
        void Observe(long from,long through)
        {
            int processed=0;
            for(long at=from+EurOffset;at<through;at+=EurStep)
            {
                foreach(var s in sources)s.BeginHistoricalClock();
                // Frame caches are scoped to clock/mode/universe. Scenario is
                // bound by the native call; no future point enters a frame.
                var frames=new Dictionary<(bool Mode,int Count),Ucp1Frame>();
                foreach(var c in cases)
                {
                    var key=(c.Source.MarketTimeFx,c.Variant.UniverseCount);
                    if(!frames.TryGetValue(key,out var frame))
                    {
                        var markets=c.Streams.Values.Select(s=>c.Source.Frame(s,at,c.Scenario,stress,general:true)).OfType<Ucp1MarketFrame>().ToArray();
                        frame=new(at,markets);frames.Add(key,frame);
                    }
                    tape.Between(c.Book,at-1,c.Source,c.Streams,c.Scenario,stress);
                    c.Source.Advance(c.Book,frame with {Protection=tape.GridCoverage(c.Book,at)},c.Streams,c.Scenario,stress);
                }
                if(++processed%288==0)Console.WriteLine($"PAV1_MARKET_TIME_PROGRESS stress={stressText} clock={at} clocks={processed} books={cases.Count}");
            }
        }
        void Checkpoint(string phase)
        {
            var root=Path.Combine(directory,"checkpoints",phase);Directory.CreateDirectory(root);
            foreach(var c in cases)File.WriteAllText(Path.Combine(root,c.Variant.Id+".json"),c.Book.HistoricalEurCheckpoint());
            Console.WriteLine($"PAV1_MARKET_TIME_CHECKPOINT stress={stressText} phase={phase} books={cases.Count}");
        }
        Observe(p.SelectionFrom,p.EvaluationFrom);
        var selection=cases.Select(c=>new {c.Variant.Id,Result=HistoricalBook(c.Book,new[]{p.SelectionFrom,p.EvaluationFrom}),
            Monetary=PavCashScore(c.Book,p.SelectionFrom,p.EvaluationFrom)}).ToArray();
        File.WriteAllBytes(Path.Combine(directory,"selection.json"),JsonSerializer.SerializeToUtf8Bytes(selection,Json));
        Checkpoint("SELECTION_BEFORE_LATER");
        Observe(p.EvaluationFrom,p.End);
        Checkpoint("TERMINAL");
        var output=new {p.Study,p.Exposure,Stress=stress,ProtocolSha256=planHash,SourceSha256=sourceHash,input.EvidenceManifestSha256,
            p.Start,p.SelectionFrom,p.EvaluationFrom,p.End,Selection=selection,
            CommonBooks=cases.Select(c=>new {c.Variant.Id,c.Variant.UniverseCount,c.Variant.Profile,
                Result=HistoricalBook(c.Book,new[]{p.SelectionFrom,p.EvaluationFrom,p.End}),
                KnownClosedNetSubtotalEur=c.Book.ReconciledModelEpisodes.Sum(e=>e.Evidence.ClosedNetEur??0m),
                HeldOutMonetary=PavCashScore(c.Book,p.EvaluationFrom,p.End),
                Details=EconomicStudyDetails(c.Book,c.Source,c.Streams),
                Forecasts=HistoricalForecasts(c.Book)}).ToArray(),
            SourceAvailability=streamsByCount[25].Select(x=>new {Symbol=x.Key,x.Value.Counts}).ToArray(),
            FxEvidence=sources.Select(s=>new {Conditional=s.MarketTimeFx,Counts=s.FxEvidenceCounts,Witnesses=s.ClosedPriceWitnesses}).ToArray(),
            SharedPortfolioEvaluations=cases.Count,CheckpointPhases=2,
            FxBasis="TWO_HOURS_OPEN_SESSION_AGE_WITH_FOUR_DAY_AUTHENTIC_LATEST_PREFIX_CAP; VERIFIED_CALENDAR; MARK_ONLY_CLOSED_HOLDINGS; CONDITIONAL_NOT_BROKER_SETTLEMENT",
            SelectionBasis="FROZEN_CHRONOLOGICAL_COMMON_BOOK_DAILY_NET_LOWER_AND_TERMINAL_EQUITY; FINAL_CROSS_STRESS_SELECTION_COMBINED_FROM_SELECTION_SNAPSHOTS_ONLY",
            MarketExpansionBasis="FOUR_ADDITIONAL_MARKETS_ONLY_AT_AUTHENTIC_AVAILABLE_CLOCKS_NOV23_25; NO_BACKFILLED_QUOTES",
            OriginalResultsModified=false,SourceBrokerRequests=0,EconomicPromotionCertified=false,IndependentConfirmationCertified=false,Orders=0,CloudActivated=false};
        File.WriteAllBytes(Path.Combine(directory,"result.json"),JsonSerializer.SerializeToUtf8Bytes(output,Json));
        Console.WriteLine($"PAV1_MARKET_TIME_COMPLETE stress={stressText} books={cases.Count}");
        return 0;
    }
}

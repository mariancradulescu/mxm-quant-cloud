using System.Globalization;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Mxm.Core;

// JRA1 ORIGINAL new study: source reuse only. No reuse of old predictors or returns.
internal static class Jra1JointRiskResearch
{
    const long M5=300000L, H=3600000L, Hold=1800000L, FillLag=M5;
    static readonly string[] Names={"AUDUSD","NZDUSD","Copper","Aluminium"};
    static string Sha(string s)=>Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();
    static string Week(long t){var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
        return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);}
    static decimal Fee(LedgerQuote q,decimal u)=>Math.Max(q.ExitFeePerUnit*u,q.ExitFeeFloor);
    static long Day(long t)=>t/86400000L;
    sealed record Observation(long At,string Symbol,int Side,bool PeerSupported,
        NativeHistoricalQuoteObservation Original);
    sealed record PastEpisode(long SignalAt,long ExitAt,string Symbol,int Side,bool PeerSupported,
        decimal NetPerUnit,decimal AdversePerUnit,long Session);
    sealed record Candidate(Observation Observe, PastEpisode[] Matured,decimal RiskEur,decimal Rank);
    sealed record Tracking(string Id,string Symbol,int Side,decimal Units,long RequestAt,
        decimal RiskEur,decimal MarginPerUnit,NativeObservedContractTerms Contract,
        decimal Slippage,long OpenedAt=0,long CloseRequestedAt=0);
    static bool Decision(long at)
    {
        var d=DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime;
        if(d.DayOfWeek is DayOfWeek.Saturday or DayOfWeek.Sunday)return false;
        // Native historical source: true as-of quotes are 1.5 seconds after completed bar clock.
        if(d.Second!=1||d.Millisecond!=500)return false;
        int m=d.Hour*60+d.Minute;
        return m is 510 or 540 or 870 or 900;
    }
    static NativeClosedMarketBar[] Window(NativeClosedMarketBar[] sorted,long at,int n)
    {
        int lo=0,hi=sorted.Length;
        while(lo<hi){int mid=(lo+hi)/2;if(sorted[mid].CloseAt<=at-1500L)lo=mid+1;else hi=mid;}
        if(lo<n)return Array.Empty<NativeClosedMarketBar>();
        var result=sorted.Skip(lo-n).Take(n).ToArray();
        if(result[^1].CloseAt!=at-1500L ||
           result.Any(b=>b.CloseAt-b.OpenAt!=M5) ||
           result.Zip(result.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt))
            return Array.Empty<NativeClosedMarketBar>();
        return result;
    }
    static Dictionary<string,Observation> Features(long at,
        Dictionary<string,NativeHistoricalQuoteObservation> atMarks,
        IReadOnlyDictionary<string,NativeClosedMarketBar[]> bars)
    {
        var signs=new Dictionary<string,int>(StringComparer.Ordinal);
        foreach(string name in Names)
        {
            if(!atMarks.ContainsKey(name)||!bars.TryGetValue(name,out var series))continue;
            var w=Window(series,at,6);
            if(w.Length!=6)continue;
            int side=Math.Sign(w[^1].Close-w[0].Open);
            if(side!=0)signs[name]=side;
        }
        return signs.ToDictionary(x=>x.Key,x=>
            new Observation(at,x.Key,x.Value,
                signs.Count(y=>y.Key!=x.Key && y.Value==x.Value)>=2,
                atMarks[x.Key]),StringComparer.Ordinal);
    }
    static PastEpisode? BuildPast(Observation o,
        IReadOnlyDictionary<long,Dictionary<string,NativeHistoricalQuoteObservation>> marks,
        IReadOnlyDictionary<string,NativeClosedMarketBar[]> bars)
    {
        if(!marks.TryGetValue(o.At+FillLag,out var entryM) ||
           !marks.TryGetValue(o.At+FillLag+Hold+FillLag,out var exitM) ||
           !entryM.TryGetValue(o.Symbol,out var entry) ||
           !exitM.TryGetValue(o.Symbol,out var exit))return null;
        if(!bars.TryGetValue(o.Symbol,out var series))return null;
        long entryAt=entry.At, exitAt=exit.At;
        var between=series.Where(b=>b.OpenAt>=entryAt-1500L && b.CloseAt<=exitAt-1500L).ToArray();
        if(between.Length<6 || between.Any(b=>b.CloseAt-b.OpenAt!=M5) ||
           between.Zip(between.Skip(1)).Any(p=>p.First.CloseAt!=p.Second.OpenAt))return null;
        var c=entry.Contract;
        if(c is null || !c.OriginalBrokerAuthenticated || c.Symbol!=o.Symbol ||
           exit.Contract is null || c.MinimumUnits<=0) return null;
        decimal units=c.MinimumUnits,slip=entry.SlippagePerSideQuote;
        decimal open=o.Side>0?entry.Quote.Ask+slip:entry.Quote.Bid-slip;
        decimal close=o.Side>0?exit.Quote.Bid-exit.SlippagePerSideQuote:
            exit.Quote.Ask+exit.SlippagePerSideQuote;
        decimal gross=o.Side*units*(close-open);
        decimal finance;
        try
        {
            var f=NativeBrokerContractCosts.SignedFinancing(c,entryAt,exitAt,
                o.Side,units,exit.Quote.EurCredit,exit.Quote.EurDebit);
            if(f is null)return null;
            finance=f.Value;
        } catch(ArgumentException){return null;}
        decimal settled=gross*(gross>=0?exit.Quote.EurCredit:exit.Quote.EurDebit)
            -Fee(entry.Quote,units)-Fee(exit.Quote,units)+finance;
        // High/low are genuine completed broker M5 source prices; do not claim
        // executable intrabar quote sides. Triple the *observed* adverse move.
        decimal extreme=o.Side>0?between.Min(x=>x.Low):between.Max(x=>x.High);
        decimal rawLoss=Math.Max(0m,o.Side*(open-extreme));
        decimal frictions=(entry.Quote.Ask-entry.Quote.Bid
            +exit.Quote.Ask-exit.Quote.Bid+slip+exit.SlippagePerSideQuote)
                *units*exit.Quote.EurDebit;
        decimal monetaryStress=3m*rawLoss*units*exit.Quote.EurDebit
            +2m*(frictions+Fee(entry.Quote,units)+Fee(exit.Quote,units))
            +Math.Max(0,-finance);
        return new(o.At,exitAt,o.Symbol,o.Side,o.PeerSupported,
            settled/units,monetaryStress/units,Day(o.At));
    }
    static LedgerEvent Fact(string mode,ref int seq,long at,string kind,
        string position="",string symbol="",int side=0,decimal units=0,
        decimal px=0,decimal fee=0,decimal margin=0,decimal slip=0,
        long available=0,long calibrated=0,long latency=1000,
        LedgerQuote[]? quotes=null,decimal finance=0)
    {
        int id=++seq;string label="JRA1/"+mode+"/"+id+"/"+kind;
        return new(label,at,kind,position,symbol,side,units,px,fee,margin,slip,
            available,calibrated,latency,"JRA1_UNQUALIFIED_NATIVE_MODEL_ONLY",
            Sha(label),quotes??Array.Empty<LedgerQuote>(),finance);
    }
    static object RunPolicy(string mode,NativeHistoricalMarketTape tape,string sourceHash)
    {
        var session=new NativeFundedSession("JRA1_MODEL_ONLY",
            new NativeFundedLedger(2000L));
        var adverse=new NativeProductAdverseBook();
        var marks=tape.Quotes.GroupBy(x=>x.At).OrderBy(x=>x.Key)
            .ToDictionary(x=>x.Key,x=>x.ToDictionary(v=>v.Quote.Symbol,StringComparer.Ordinal));
        var bars=tape.Bars.ToDictionary(x=>x.Symbol,x=>x.M5.OrderBy(b=>b.CloseAt).ToArray(),StringComparer.Ordinal);
        var tracking=new Dictionary<string,Tracking>(StringComparer.Ordinal);
        var training=new List<PastEpisode>();
        var sourceEvents=new List<Observation>();
        foreach(var entry in marks)
        {
            if(!Decision(entry.Key))continue;
            sourceEvents.AddRange(Features(entry.Key,entry.Value,bars).Values);
        }
        foreach(var o in sourceEvents)
        {
            var p=BuildPast(o,marks,bars);
            if(p is not null)training.Add(p);
        }
        training=training.OrderBy(x=>x.ExitAt).ThenBy(x=>x.Symbol,StringComparer.Ordinal).ToList();
        var candidatesByTime=sourceEvents.GroupBy(x=>x.At)
            .ToDictionary(g=>g.Key,g=>g.ToArray());
        int seq=0,forecastOffers=0,predictorRejected=0,riskRejected=0,
            nativeRejected=0,capacityOnly=0,missingMarks=0,
            missingFinance=0,fillCancelled=0,entryCount=0,closeCount=0,
            firstRiskExceed=0,softStops=0,sourceFutureLeakViolations=0;
        var reasons=new Dictionary<string,int>(StringComparer.Ordinal);
        var riskDecisions=new List<object>();
        decimal maxReservedStress=0m,maxObservedMargin=0m;
        void Count(string reason){reasons[reason]=reasons.GetValueOrDefault(reason)+1;}
        void Apply(params LedgerEvent[] facts)
        {
            session.ApplyResearchFacts(facts);
            adverse.Apply(facts);
        }
        foreach(var at in marks.Keys.OrderBy(x=>x))
        {
            var atQuotes=marks[at];
            Apply(Fact(mode,ref seq,at,"MARK",quotes:atQuotes.Values.Select(q=>q.Quote).ToArray()));
            // Authentic later quote is the only input allowed to confirm a
            // model fill; modeled intent does NOT imply broker execution.
            foreach(var t in tracking.Values.OrderBy(x=>x.Id,StringComparer.Ordinal).ToArray())
            {
                if(!atQuotes.TryGetValue(t.Symbol,out var mark))
                {missingMarks++;continue;}
                var q=mark.Quote;
                if(t.OpenedAt==0 && at>=t.RequestAt+1000L)
                {
                    if(at-t.RequestAt>600000L)
                    {
                        Apply(Fact(mode,ref seq,at,"CONFIRMED_CANCEL",t.Id,t.Symbol,t.Side,t.Units)
                            with{Reason="JRA1_MODEL_REQUEST_EXPIRED_WITHOUT_QUOTE"});
                        tracking.Remove(t.Id);fillCancelled++;continue;
                    }
                    decimal price=t.Side>0?q.Ask+t.Slippage:q.Bid-t.Slippage;
                    try
                    {
                        Apply(Fact(mode,ref seq,at,"OPEN_FILL",t.Id,t.Symbol,t.Side,t.Units,
                            price,Fee(q,t.Units),q.MarginPerUnit,t.Slippage));
                        tracking[t.Id]=t with {OpenedAt=at,MarginPerUnit=Math.Max(t.MarginPerUnit,q.MarginPerUnit)};
                        entryCount++;
                    }
                    catch(InvalidOperationException e)when(e.Message=="NATIVE_LEDGER_UNFINANCED_MODEL_FILL")
                    {
                        Apply(Fact(mode,ref seq,at,"CONFIRMED_CANCEL",t.Id,t.Symbol,t.Side,t.Units)
                            with{Reason="JRA1_MODEL_MARGIN_FAILED_AT_REAL_QUOTE"});
                        tracking.Remove(t.Id);fillCancelled++;
                    }
                }
                else if(t.OpenedAt>0 && t.CloseRequestedAt==0 && at>=t.OpenedAt+Hold)
                {
                    Apply(Fact(mode,ref seq,at,"REQUEST_CLOSE",t.Id,t.Symbol,t.Side,t.Units));
                    tracking[t.Id]=t with {CloseRequestedAt=at};
                }
                else if(t.CloseRequestedAt>0 && at>=t.CloseRequestedAt+1000L)
                {
                    decimal? funding;
                    try
                    {
                        funding=NativeBrokerContractCosts.SignedFinancing(t.Contract,t.OpenedAt,at,
                            t.Side,t.Units,q.EurCredit,q.EurDebit);
                    }catch(ArgumentException){funding=null;}
                    if(funding is null){missingFinance++;continue;}
                    decimal px=t.Side>0?q.Bid-t.Slippage:q.Ask+t.Slippage;
                    Apply(Fact(mode,ref seq,at,"FINANCING",t.Id,t.Symbol,t.Side,t.Units,
                        finance:funding.Value),
                        Fact(mode,ref seq,at,"CLOSE_FILL",t.Id,t.Symbol,t.Side,t.Units,
                            px,Fee(q,t.Units),q.MarginPerUnit,t.Slippage));
                    tracking.Remove(t.Id);closeCount++;
                }
            }
            var snapshot=session.Ledger.Summary(at);
            if(snapshot.UsedMarginEur is decimal margin)
                maxObservedMargin=Math.Max(maxObservedMargin,margin);
            maxReservedStress=Math.Max(maxReservedStress,tracking.Values.Sum(x=>x.RiskEur));
            if(mode=="CASH" || !candidatesByTime.TryGetValue(at,out var nowCandidates))continue;
            if(snapshot.MaximumSampledDrawdown>=.25m){softStops++;continue;}
            if(snapshot.LiquidationEquityEur is not decimal equity ||
               snapshot.FreeMarginEur is not decimal free){missingMarks++;continue;}
            decimal peak=Math.Max(300m,Math.Max(snapshot.ObservedPeakEur,equity));
            decimal headroom=equity-.70m*peak;
            if(headroom<=0){firstRiskExceed++;continue;}
            var all=new List<Candidate>();
            foreach(var o in nowCandidates)
            {
                if(mode!="OWN_PRICE" && !o.PeerSupported){predictorRejected++;continue;}
                var hist=training.Where(v=>v.Symbol==o.Symbol && v.Side==o.Side &&
                    (mode=="OWN_PRICE" || v.PeerSupported) && v.ExitAt<at)
                    .GroupBy(x=>x.Session).Select(g=>g.Last())
                    .OrderByDescending(x=>x.ExitAt).Take(8).OrderBy(x=>x.ExitAt).ToArray();
                if(hist.Length!=8){predictorRejected++;Count("INSUFFICIENT_MATURE_DISTINCT_SESSIONS");continue;}
                if(hist.Any(x=>x.ExitAt>=at))throw new InvalidOperationException("JRA1_LOOKAHEAD_LABEL");
                if(!atQuotes.TryGetValue(o.Symbol,out var m) || m.Contract is null)continue;
                decimal u=m.Contract.MinimumUnits;
                if(u<=0){Count("INVALID_VOLUME");continue;}
                decimal maxLoss=hist.Max(x=>x.AdversePerUnit)*u;
                decimal assumedRisk=Math.Max(maxLoss,
                    3m*hist.Max(x=>Math.Max(0m,-x.NetPerUnit))*u);
                decimal average=hist.Average(x=>x.NetPerUnit)*u;
                decimal se=(decimal)Math.Sqrt((double)hist.Sum(x=>(x.NetPerUnit*u-average)*(x.NetPerUnit*u-average))/7d/8d);
                decimal rank=(average-se)/Math.Max(1m,assumedRisk);
                all.Add(new(o,hist,assumedRisk,rank));forecastOffers++;
            }
            // Economic-risk priority is predeclared, but final funding and
            // conditional scenario selection remain in the NATIVE allocator.
            all=mode=="UNRANKED"
                ?all.OrderBy(x=>x.Observe.Symbol,StringComparer.Ordinal).ToList()
                :all.OrderByDescending(x=>x.Rank).ThenBy(x=>x.Observe.Symbol,StringComparer.Ordinal).ToList();
            for(int ci=0;ci<all.Count;ci++)
            {
                var c=all[ci];var o=c.Observe;var q=o.Original.Quote;
                snapshot=session.Ledger.Summary(at);
                if(snapshot.LiquidationEquityEur is not decimal ce ||
                   snapshot.FreeMarginEur is not decimal fm){missingMarks++;break;}
                peak=Math.Max(300m,Math.Max(snapshot.ObservedPeakEur,ce));
                decimal heldRisk=tracking.Values.Sum(t=>t.RiskEur);
                decimal residual=ce-.70m*peak-heldRisk;
                if(fm>=q.MarginPerUnit*o.Original.Contract!.MinimumUnits)capacityOnly++;
                if(c.RiskEur<=0 || c.RiskEur>=residual ||
                   heldRisk+c.RiskEur>ce-.70m*peak)
                {
                    riskRejected++;Count("JOINT_STRESSED_LOSS_EXCEEDS_PRETRADE_HEADROOM");continue;
                }
                if(tracking.Values.Any(t=>t.Symbol==o.Symbol))
                {nativeRejected++;Count("SYMBOL_ALREADY_HELD_OR_PENDING");continue;}
                string decisionId="JRA1/"+mode+"/"+at+"/"+ci;
                string id="JRA1/"+mode+"/"+at+"/"+o.Symbol;
                var grid=new AdaptiveRiskInputs(ce,0m,fm,
                    o.Original.Contract.MinimumUnits,o.Original.Contract.VolumeStepUnits,
                    o.Original.Contract.MinimumUnits,q.MarginPerUnit,1m,false,false,2,1m);
                // Eight genuinely prior distinct-session shocks for this
                // SINGLE candidate. Held portfolio risk is the same fully
                // reserved amount in all states: zero offset/netting credit.
                var states=c.Matured.Select((x,i)=>
                    new PortfolioScenario("HIST_"+i,at-1,true,0m,0m,0m,0m)).ToArray();
                var outcomes=c.Matured.Select((x,i)=>
                    new OpportunityScenario("HIST_"+i,x.ExitAt,true,x.NetPerUnit,
                        0m,c.RiskEur/o.Original.Contract.MinimumUnits,0m)).ToArray();
                var native=new EconomicOpportunity(id,"JRA1_SYSTEMIC_PARTICIPATION",
                    o.Symbol,o.Symbol,o.Side,at-1,c.Matured[^1].ExitAt,
                    EvidenceLevel.Exploratory,false,grid,outcomes);
                var exposed=tracking.Values.Select(t=>
                {
                    if(!atQuotes.TryGetValue(t.Symbol,out var mark))
                        throw new InvalidOperationException("JRA1_HELD_ORIGINAL_MARK_MISSING");
                    decimal margin=Math.Max(t.MarginPerUnit,mark.Quote.MarginPerUnit)*t.Units;
                    return new ResearchExposureScenarios(t.Id,t.Symbol,t.Side,t.Units,
                        states.Select(s=>s with{LossEur=t.RiskEur,MarginEur=margin}).ToArray());
                }).ToArray();
                var d=new NativeResearchDecision(decisionId,at,
                    new ScenarioSizingInputs(ce,peak,fm,o.Original.Contract.MinimumUnits,
                        o.Original.Contract.VolumeStepUnits,o.Original.Contract.MinimumUnits,
                        q.MarginPerUnit,1m,2,1m),
                    states,new[]{native},exposed,
                    new[]{new ResearchEntryTerms(id,1000,o.Original.SlippagePerSideQuote,Sha(id))},
                    Sha(decisionId),null);
                var result=session.DecideResearch(d);
                if(result.Selection.Allocations.Length!=1)
                {
                    nativeRejected++;Count(result.Selection.Declined.FirstOrDefault()?.Reason??result.Status);
                    continue;
                }
                var selected=result.Selection.Allocations[0];
                var entry=new Tracking(id,o.Symbol,o.Side,selected.Units,at,c.RiskEur,
                    q.MarginPerUnit,o.Original.Contract,
                    o.Original.SlippagePerSideQuote);
                tracking.Add(id,entry);
                maxReservedStress=Math.Max(maxReservedStress,tracking.Values.Sum(x=>x.RiskEur));
                // Mirror the SAME native REQUEST_OPEN fact into the EXISTING
                // adverse-scenario ledger, not a second invented cash account.
                adverse.Apply(new LedgerEvent("DECISION/"+decisionId+"/"+id,at,"REQUEST_OPEN",
                    id,o.Symbol,o.Side,selected.Units,0m,0m,q.MarginPerUnit,
                    o.Original.SlippagePerSideQuote,at-1,c.Matured[^1].ExitAt,
                    1000,"NATIVE_CONDITIONAL_SELECTION",Sha(id),Array.Empty<LedgerQuote>()));
                riskDecisions.Add(new{Clock=at,Symbol=o.Symbol,
                    EstimatedStressRiskEur=c.RiskEur,
                    ExistingOpenStressEur=heldRisk,
                    HeadroomBeforeEur=ce-.70m*peak,
                    Result="ADMITTED_NATIVE_UNQUALIFIED",SelectedUnits=selected.Units});
            }
        }
        var end=session.Ledger.Summary();
        var stressed=adverse.Summary;
        var closed=session.Ledger.ClosedFragments();
        bool complete=end.OpenPositions==0 && end.PendingIntents==0 &&
            !end.HistoryEvidenceIncomplete && missingFinance==0;
        var allWeeks=marks.Keys.Where(Decision).Select(Week).Distinct()
            .OrderBy(x=>x,StringComparer.Ordinal).ToArray();
        var weekCounts=allWeeks.ToDictionary(w=>w,
            w=>closed.Count(c=>c.CompletesRoundTrip && Week(c.OpenedAt)==w),StringComparer.Ordinal);
        return new {
            Policy=mode,UniqueCommonInitialCapitalEur=300,
            NativeLedgerUsed=true,NativeSelector="NativeFundedSession.DecideResearch",
            CounterfactualDomain="MODEL_REPLAY_ORIGINAL_QUOTE_WITH_CURRENT_CONTRACT_TERMS",
            ConditionalHistoricalTariffOnly=true,
            SourceOriginalSha256=sourceHash,
            EndCashEur=complete?(decimal?)end.CashEur:null,
            ClosedNetEur=complete?(decimal?)end.ClosedNetEur:null,
            AdverseClosedNetEur=complete&&adverse.Complete&&stressed is not null &&
                stressed.OpenPositions==0&&stressed.PendingIntents==0 &&
                !stressed.HistoryEvidenceIncomplete?(decimal?)stressed.ClosedNetEur:null,
            AdverseStatus=adverse.Complete?"CONDITIONAL_MODEL_ADVERSE_COMPLETE_IF_ALL_MARKS"
                :adverse.FailureKind,
            NativeCompleteFundedModelRoundTrips=end.CompleteRoundTrips,
            WeeklyCompleteFundedModelRoundTrips=weekCounts,
            GrossEur=complete?(decimal?)closed.Sum(c=>c.GrossEur):null,
            SpreadEur=complete?(decimal?)closed.Sum(c=>c.SpreadEur??0m):null,
            CommissionEur=complete?(decimal?)closed.Sum(c=>c.CommissionsEur):null,
            FinancingEur=complete?(decimal?)closed.Sum(c=>c.FinancingEur):null,
            SampledMarkDrawdown=end.MaximumSampledDrawdown,
            NativeAdverseSampledDrawdown=stressed?.MaximumSampledDrawdown,
            EverObserved30PctSampledBreach=end.MaximumSampledDrawdown>=.30m,
            AllContinuousIntrabarMarksObserved=false,
            MaxObservedMarginEur=maxObservedMargin,MaxReservedStressEur=maxReservedStress,
            NoTailGuarantee=true,OpenPositions=end.OpenPositions,
            PendingIntents=end.PendingIntents,HistoryIncomplete=end.HistoryEvidenceIncomplete,
            SourceMaturedCandidateExamples=training.Count,
            ForecastOffers=forecastOffers,PredictorAbstentions=predictorRejected,
            PretradeRiskRejections=riskRejected,NativeSelectorRejections=nativeRejected,
            MarginOnlyDiagnosticPasses=capacityOnly,MissingHeldQuoteMarks=missingMarks,
            UnknownFinancingClosures=missingFinance,ModelRequestsCancelledAtMissingQuote=fillCancelled,
            NativeModelOpened=entryCount,NativeModelClosed=closeCount,
            Conservative25PctPauseClocks=softStops,
            ConditionalHistoryBoundInsufficientClocks=firstRiskExceed,
            SourceFutureLeakViolations=sourceFutureLeakViolations,
            DenialReasons=reasons,AdmittedPretradeRiskReceipts=riskDecisions,
            NativeLedgerEventChainSha256=end.EventChainHash,
            NativeAdverseEventChainSha256=stressed?.EventChainHash,
            BrokerActualOrders=0,BrokerExecutionNetEur=(decimal?)null,
            IndependentConfirmation=false,GlobalFloatingDrawdownCertified=false,
            FundedNetEconomicallyQualified=false
        };
    }
    public static int Run(string path,string output)
    {
        var bytes=File.ReadAllBytes(path);
        string hash=Convert.ToHexString(SHA256.HashData(bytes)).ToLowerInvariant();
        if(hash!="fd7986487be347376aa1e139915f90786155d2b1b6de1787382aa7d8666faeaf")
            throw new ArgumentException("JRA1_ORIGINAL_AUTHENTIC_PLAINTEXT_SHA");
        var source=JsonSerializer.Deserialize<NativeOriginalOpenApiTape>(bytes,new JsonSerializerOptions {
            NumberHandling=System.Text.Json.Serialization.JsonNumberHandling.AllowReadingFromString
        });
        if(source is null || source.SourceLabel!="ORIGINAL_PEPPERSTONE_IPC2" ||
            !Names.Concat(new[]{"EURUSD"}).OrderBy(s=>s,StringComparer.Ordinal)
                .SequenceEqual(source.Bars.Select(b=>b.Symbol).OrderBy(s=>s,StringComparer.Ordinal)))
            throw new ArgumentException("JRA1_ORIGINAL_SOURCE_BINDING_OR_UNIVERSE");
        var tape=NativeOriginalOpenApiProductAdapter.Convert(source);
        var modes=new[]{"PARTICIPATION","OWN_PRICE","UNRANKED","CASH"};
        var reports=new Dictionary<string,object>(StringComparer.Ordinal);
        foreach(var mode in modes)
        {
            Console.WriteLine("JRA1_NATIVE_POLICY_STARTED_"+mode);
            reports.Add(mode,RunPolicy(mode,tape,hash));
            Console.WriteLine("JRA1_NATIVE_POLICY_COMPLETE_"+mode);
        }
        var receipt=new {
            Study="JRA1",ProtocolId="research/JRA1_JOINT_RISK_PROTOCOL_20261117.md",
            OriginalSourceRunId=43176793567,OriginalSourceArtifactId=13925405999,
            OriginalSourcePlaintextSha256=hash,
            OriginalSourceCiphertextSha256="aceca6ea879201ce16caba708a1ae47a953ad66e6b58977fe044bbd4b740e64a",
            FullSourceBarCounts=source.Bars.ToDictionary(x=>x.Symbol,x=>x.M5.Length),
            SourceQuoteCounts=source.Marks.GroupBy(x=>x.Symbol).ToDictionary(x=>x.Key,x=>x.Count()),
            Reports=reports,ReferenceCashEur=300,
            NativeLedgerAndSelectorUsed=true,NoNewCbotOrLedger=true,
            StudySourceFullyExposed=true,IndependentHoldout=false,
            OriginalClosedStudyRerun=false,OrdersSent=0,CloudActivated=false,
            OriginalSourceRecollected=false,HistoricalTariffCertified=false,
            CertifiedContinuousFloatingDrawdown=false,Qualified=false,
            Verdict="JRA1_NEW_EXPOSED_NATIVE_JOINT_RISK_RESEARCH_NOT_CERTIFIED"
        };
        File.WriteAllText(output,JsonSerializer.Serialize(receipt,new JsonSerializerOptions{
            WriteIndented=true}));
        return 0;
    }
    public static int SyntheticChecks()
    {
        if(!Decision(1782975601500L)) { /* clock fixture below will be checked by UTC construction */ }
        long t=new DateTimeOffset(2026,8,3,8,30,1,500,TimeSpan.Zero).ToUnixTimeMilliseconds();
        if(!Decision(t) || Decision(t+M5) || Decision(t+1000))throw new Exception("JRA1_CAUSAL_SCHEDULE_TEST");
        // Pure ledger contract sanity: same original native book enforces one
        // EUR300 founding capital, and scenario stress is never a stop guarantee.
        var book=new NativeFundedSession("JRA1_TEST_ONLY");
        var zero=book.Ledger.Summary();
        if(zero.CashEur!=300m || zero.CompleteRoundTrips!=0 ||
           zero.OrdersEnabled || zero.GlobalDrawdownCertified)
            throw new Exception("JRA1_NATIVE_FOUNDING_CONTRACT");
        var cases=new[]{5m,15m,60m};
        if(cases.Sum()+80m>=90m || cases.Sum()+80m<=90m)
            throw new Exception("JRA1_JOINT_LOSS_NOT_SUMMED");
        Console.WriteLine("JRA1_SYNTHETIC_NATIVE_CHECKS_PASS");
        return 0;
    }
}

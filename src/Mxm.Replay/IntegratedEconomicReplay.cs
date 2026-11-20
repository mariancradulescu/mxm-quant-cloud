using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static partial class IntegratedEconomicReplay
{
    sealed record SourceQuote(long At,long BidAt,long AskAt,decimal Bid,decimal Ask,NativeObservedQuotePath Path);
    sealed record SourceMarket(string Name,string Class,NativeObservedContractTerms Contract,
        decimal TickSize,bool ShortAllowed,int TradingMode,bool CostTermsComplete,NativeObservedVolume[] Margin,
        NativeClosedMarketBar[] M5,NativeClosedMarketBar[] M15,NativeClosedMarketBar[] H1,SourceQuote[] Quotes,
        int ActiveHours,int RequestedTickHours,int[][] Schedule,string ScheduleTimeZone,
        NativeProtectionDistances? Protection)
    {
        public Dictionary<string, AdditionalBars>? AdditionalTimeframes { get; init; }
    }
    sealed record AdditionalBars(string Source, NativeClosedMarketBar[] Bars);
    sealed record Source(long Start,long End,string SourceRun,string ProtocolSha256,SourceMarket[] Markets,
        long ManagementIntervalMs=60_000L);

    sealed class BarPrefix
    {
        readonly NativeClosedMarketBar[] bars;
        readonly int window;
        int completed;
        public BarPrefix(NativeClosedMarketBar[] bars,int window)
        {
            this.bars=bars;
            this.window=window;
        }
        public NativeClosedMarketBar[] Observe(long at)
        {
            while(completed<bars.Length && bars[completed].CloseAt<at) completed++;
            return bars[Math.Max(0,completed-window)..completed];
        }
    }

    sealed class MarketStream
    {
        public readonly SourceMarket Source;
        readonly Dictionary<long,SourceQuote> quotes;
        readonly BarPrefix m5,m15,h1;
        public int AcceptedMarks {get;private set;}
        public MarketStream(SourceMarket source)
        {
            Source=source;
            quotes=source.Quotes.ToDictionary(x=>x.At);
            m5=new(source.M5,5);
            m15=new(source.M15,3);
            h1=new(source.H1,6);
        }
        public SourceQuote? At(long at)=>quotes.TryGetValue(at,out var value)?value:null;
        public Ucp1MarketFrame? Frame(long at,SourceQuote fx)
        {
            var m=Source;
            var q=At(at);
            if(q is null || !m.CostTermsComplete || m.TradingMode!=0 ||
               !m.Contract.OriginalBrokerAuthenticated || m.Margin.Length==0 || m.Contract.Symbol!=m.Name ||
               q.BidAt>at || q.AskAt>at || at-q.BidAt>30_000 || at-q.AskAt>30_000)
                return null;
            LedgerQuote quote;
            try
            {
                quote=NativeIntegratedEconomicPolicy.BuildQuote(m.Contract,at,q.Bid,q.Ask,
                    fx.Bid,fx.Ask,m.Margin,m.TickSize);
            }
            catch(ArgumentException) {return null;}
            catch(InvalidOperationException) {return null;}
            AcceptedMarks++;
            return new(m.Name,quote,m.Contract,m5.Observe(at),m15.Observe(at),
                NativeIntegratedEconomicPolicy.Slippage(q.Bid,q.Ask,m.TickSize,false),
                "ORIGINAL_NATIVE_BARS_AND_OBSERVED_EXECUTABLE_SIDES",
                new NativeIntegratedMarket(h1.Observe(at),m.Margin,m.ShortAllowed,m.TickSize,q.Path)
                { Protection=m.Protection });
        }
    }

    static readonly JsonSerializerOptions Json=new()
    {
        NumberHandling=JsonNumberHandling.AllowReadingFromString,WriteIndented=true
    };

    static string Week(long stamp)
    {
        var t=DateTimeOffset.FromUnixTimeMilliseconds(stamp).UtcDateTime;
        return ISOWeek.GetYear(t)+"-W"+ISOWeek.GetWeekOfYear(t).ToString("00",CultureInfo.InvariantCulture);
    }

    // The best hindsight mark on a minimum-volume solo path is not a portfolio.
    static object ReachablePath(Ucp1Frame[] frames)
    {
        var counts=new Dictionary<string,int>(StringComparer.Ordinal);
        var netBestBySymbol=new Dictionary<string,decimal>(StringComparer.Ordinal);
        var seen=new Dictionary<string,long>(StringComparer.Ordinal);
        void Count(string key)=>counts[key]=counts.GetValueOrDefault(key)+1;
        for(int i=0;i<frames.Length-1;i++)
        {
            var frame=frames[i];
            foreach(var market in frame.Markets)
            {
                var context=market.Integrated!;
                if(market.M5.Length==0 || frame.At<=market.M5[^1].CloseAt ||
                   market.M5[^1].CloseAt<=seen.GetValueOrDefault(market.Symbol))
                    continue;
                seen[market.Symbol]=market.M5[^1].CloseAt;
                foreach(var signal in NativeIntegratedEconomicPolicy.Describe(market,frame.At))
                {
                    string suffix="/"+market.Symbol+"/"+signal.Family;
                    Count("OBSERVED_PROPOSAL"+suffix);
                    var minimum=context.Volumes.FirstOrDefault(v=>v.Units==market.Contract.MinimumUnits);
                    if(minimum is null || NativeIntegratedEconomicPolicy.Terms(signal,market,minimum,false)
                       is not { } terms || terms.MarginEur>=300m || terms.RiskEur>=90m)
                        continue;
                    Count("MINIMUM_SOLO_MODEL_ELIGIBLE"+suffix);
                    var open=frames[i+1].Markets.FirstOrDefault(x=>x.Symbol==market.Symbol);
                    if(open is null || open.Integrated!.Path?.Complete!=true)
                    {
                        Count("OPEN_OR_PATH_UNKNOWN"+suffix);
                        continue;
                    }
                    int side=signal.Side;
                    decimal entry=side>0?open.Quote.Ask+terms.ExecutionSlippage:open.Quote.Bid-terms.ExecutionSlippage;
                    if(side*(entry-signal.Stop)<=0m || side*(signal.Target-entry)<=0m)
                    {
                        Count("OPEN_GEOMETRY_INVALIDATED"+suffix);
                        continue;
                    }
                    decimal entryFee=Math.Max(open.Quote.ExitFeeFloor,terms.Units*open.Quote.ExitFeePerUnit);
                    decimal best=decimal.MinValue;
                    string barrier="RIGHT_CENSORED";
                    for(int j=i+2;j<frames.Length;j++)
                    {
                        var next=frames[j].Markets.FirstOrDefault(x=>x.Symbol==market.Symbol);
                        if(next?.Integrated?.Path is not {Complete:true} path) break;
                        bool stop=side>0?path.BidLow<=signal.Stop:path.AskHigh>=signal.Stop;
                        bool target=side>0?path.BidHigh>=signal.Target:path.AskLow<=signal.Target;
                        if(stop || target)
                        {
                            barrier=stop&&target?"AMBIGUOUS_BOTH":stop?"INVALIDATION_FIRST":"TARGET_FIRST";
                            break;
                        }
                        var q=next.Quote;
                        decimal exit=side>0?q.Bid-terms.ExecutionSlippage:q.Ask+terms.ExecutionSlippage;
                        decimal quotePnl=side*(exit-entry)*terms.Units;
                        decimal net=quotePnl*(quotePnl>=0?q.EurCredit:q.EurDebit)
                            -entryFee-Math.Max(q.ExitFeeFloor,terms.Units*q.ExitFeePerUnit);
                        best=Math.Max(best,net);
                    }
                    Count(barrier+suffix);
                    if(best>0m)
                    {
                        Count("POSITIVE_HINDSIGHT_OBSERVED_MARK"+suffix);
                        netBestBySymbol[market.Symbol]=netBestBySymbol.GetValueOrDefault(market.Symbol)+best;
                    }
                }
            }
        }
        return new { Counts=counts, SumPositiveSoloBestMarksEur=netBestBySymbol,
            Interpretation="EXPOSED_HINDSIGHT_SOLO_MINIMUM_VOLUME_PATH_DIAGNOSTIC" };
    }

    static long UtcDay(long t)=>t/86_400_000L;

    static bool? PotentialRollover(Ucp1Episode trip,NativeObservedContractTerms contract)
    {
        if(contract.SwapTimeUtcMinute is not (>=0 and <1440) ||
            contract.SwapPeriodHours is not (>0 and <=24)) return null;
        long phase=contract.SwapTimeUtcMinute.Value*60_000L;
        long period=contract.SwapPeriodHours.Value*3_600_000L;
        return (trip.CloseAt-phase)/period>(trip.OpenAt-phase)/period;
    }

    static object LifecycleReport(NativeUnifiedPortfolioEngine engine,Ucp1Episode[] trips,
        Ucp1CurvePoint[] curve,Dictionary<string,NativeObservedContractTerms> contracts,long evaluationStart)
    {
        var r=trips.Select(x=>x.R!.Value).OrderBy(x=>x).ToArray();
        var age=trips.Select(x=>x.CloseAt-x.OpenAt).OrderBy(x=>x).ToArray();
        var wins=trips.Where(x=>x.NetEur>0m).ToArray();
        var losses=trips.Where(x=>x.NetEur<0m).ToArray();
        var summary=engine.ModelSummary;
        var calibration=engine.IntegratedCalibration()!;
        return new {
            calibration.Cells,calibration.Cancelled,
            MedianHoldMs=age.Length==0?(long?)null:age[age.Length/2],
            CompleteWithinTwoMinutes=age.Count(x=>x<=120_000L),
            RegimeExits=trips.Count(x=>x.ExitReason.EndsWith("INTEGRATED_NEW_M15_THESIS_INVALIDATION",StringComparison.Ordinal)),
            LegacyRegimeExits=trips.Count(x=>x.ExitReason.EndsWith("CLOSED_BAR_REGIME_INVALIDATION",StringComparison.Ordinal)),
            PlannedNetTargetNonpositive=trips.Count(x=>x.Integrated!.InitialPlannedRewardEur<=0m),
            MeanWinEur=wins.Length==0?(decimal?)null:wins.Average(x=>x.NetEur),
            MeanLossEur=losses.Length==0?(decimal?)null:losses.Average(x=>x.NetEur),
            MeanPlannedRewardToRisk=trips.Length==0?(decimal?)null:trips.Average(x=>x.Integrated!.PlannedRewardToRisk),
            MaxStressedEntryRiskEur=trips.Length==0?(decimal?)null:trips.Max(x=>x.Integrated!.Thesis!.StressedRiskAtFillEur),
            WorstR=r.Length==0?(decimal?)null:r[0],
            FifthPercentileR=r.Length==0?(decimal?)null:r[(int)Math.Floor((r.Length-1)*.05)],
            LessThanMinusTwoR=r.Count(x=>x< -2m),
            BeyondStressedRisk=trips.Count(x=>x.NetEur< -x.Integrated!.Thesis!.StressedRiskAtFillEur),
            Costs=new { Commission=trips.Sum(x=>x.Integrated!.CommissionsEur),
                Spread=trips.Sum(x=>x.Integrated!.SpreadEur),Slippage=trips.Sum(x=>x.Integrated!.SlippageEur),
                Conversion=trips.Sum(x=>x.Integrated!.ConversionEur) },
            RolloverPotential=trips.Count(x=>PotentialRollover(x,contracts[x.Symbol])==true),
            RolloverTermsUnknown=trips.Count(x=>PotentialRollover(x,contracts[x.Symbol]) is null),
            summary.ObservedPeakEur,summary.MaximumSampledDrawdown,
            EquityByUtcDay=curve.Where(x=>x.At>=evaluationStart).GroupBy(x=>UtcDay(x.At)).Select(group=>{
                var known=group.Where(x=>x.EquityEur is not null).ToArray();
                return new { Day=DateTimeOffset.FromUnixTimeMilliseconds(group.Key*86_400_000L).ToString("yyyy-MM-dd"),
                    LastCashEur=group.Last().CashEur, LastSampledEquityEur=known.LastOrDefault()?.EquityEur,
                    MinimumSampledEquityEur=known.Length>0?known.Min(x=>x.EquityEur):null,
                    MaximumSampledEquityEur=known.Length>0?known.Max(x=>x.EquityEur):null,
                    UnknownExposureMarks=group.Count(x=>x.Held>0&&x.EquityEur is null) };
            }).ToArray(),
        };
    }

    public static int Run(string inputFile,string outputDirectory,bool coherent=false,bool completePolicy=false)
    {
        using var stream=File.OpenRead(inputFile);
        var source=JsonSerializer.Deserialize<Source>(stream,Json)
            ??throw new ArgumentException("INTEGRATED_VERIFIED_SOURCE_MISSING");
        long spacing=coherent||completePolicy?NativeIntegratedLifecycle.IntervalMs:60_000L;
        if(source.Start<=0 || source.End-source.Start!=(completePolicy?12*NativeCompletePolicy.Week:21*86_400_000L) || source.ManagementIntervalMs!=spacing ||
           source.ProtocolSha256.Length!=64 || source.SourceRun.Length==0 ||
           !source.SourceRun.All(char.IsAsciiDigit) ||
           source.Markets.Select(x=>x.Name).Distinct(StringComparer.Ordinal).Count()!=source.Markets.Length)
            throw new ArgumentException("INTEGRATED_FROZEN_SOURCE_SCOPE_INVALID");
        var markets=source.Markets.Select(m=>new MarketStream(m)).ToArray();
        var fx=markets.Single(m=>m.Source.Name=="EURUSD");
        var frames=new List<Ucp1Frame>();
        for(long at=source.Start+NativeIntegratedEconomicPolicy.ClockOffsetMs;at<source.End;at+=spacing)
        {
            if (completePolicy)
            {
                long minute = at % NativeCompletePolicy.Day / 60_000L;
                var weekday = DateTimeOffset.FromUnixTimeMilliseconds(at).UtcDateTime.DayOfWeek;
                if (minute<479 || minute>=665 || weekday is DayOfWeek.Saturday or DayOfWeek.Sunday) continue;
            }
            var conversion=fx.At(at);
            var observed=conversion is null?Array.Empty<Ucp1MarketFrame>():markets
                 .Select(m=>m.Frame(at,conversion)).OfType<Ucp1MarketFrame>().ToArray();
            frames.Add(new Ucp1Frame(at,observed));
        }
        var clocks=frames.ToArray();
        if (completePolicy)
        {
            Directory.CreateDirectory(outputDirectory);
            using var economy=File.Create(Path.Combine(outputDirectory,"economic.json"));
            var completeCoverage=markets.Select(x=>new {
                x.Source.Name,x.Source.Class,x.Source.ActiveHours,x.Source.RequestedTickHours,
                M5=x.Source.M5.Length,M15=x.Source.M15.Length,H1=x.Source.H1.Length,
                x.Source.Protection,x.Source.Margin,x.AcceptedMarks
            }).ToArray();
            var result=NativeCompletePolicyResearch.Run(clocks,source.Start,source.End,
                source.Markets.ToDictionary(x=>x.Name,x=>x.Contract,StringComparer.Ordinal));
            JsonSerializer.Serialize(economy,new { Study="COMPLETE_POLICY_EXECUTABLE_QUOTE_RESIDENCE",
                source.SourceRun,source.ProtocolSha256,SourceCoverage=completeCoverage,Result=result },Json);
            return 0;
        }
        var diagnostic=coherent?null:ReachablePath(clocks);
        var policies=coherent?NativeIntegratedLifecycle.Policies:NativeIntegratedEconomicPolicy.Policies
            .Concat(new[]{"INTEGRATED_FIRST_MIN_ADVERSE","INTEGRATED_STRUCTURE_BUDGET_ADVERSE"}).ToArray();
        long evaluationStart=source.Start+NativeIntegratedLifecycle.CalibrationMs;
        var weeks=Enumerable.Range(coherent?1:0,coherent?2:3).Select(i=>Week(source.Start+i*7*86400000L)).ToArray();
        var contracts=source.Markets.ToDictionary(x=>x.Name,x=>x.Contract,StringComparer.Ordinal);
        (string Policy, decimal NetEur, object Report, object? Lifecycle) Evaluate(string policy)
        {
            var engine=new NativeUnifiedPortfolioEngine(policy);
            foreach(var frame in clocks) engine.Advance(frame);
            var valid=engine.ModelSummary;
            var trips=engine.CompleteModelTrips;
            var curve=engine.CommonBookEquityPath;
            var events=engine.OriginalModelEvents;
            var check=new NativeFundedLedger();
            foreach(var fact in events) check.Apply(fact);
            if(check.Summary()!=valid)
                throw new InvalidOperationException("INTEGRATED_ORIGINAL_LEDGER_RECONCILIATION");
            var weekly=weeks.Select(w=>{
                var match=trips.Where(t=>Week(t.CloseAt)==w).ToArray();
                var value=curve.LastOrDefault(x=>Week(x.At)==w && x.EquityEur is not null);
                return new { Week=w, Completed=match.Length, NetEur=match.Sum(x=>x.NetEur),
                    LastObservedEquityEur=value?.EquityEur, Hard21ModelOnly=match.Length>=21 };
            }).ToArray();
            var report=new {
                Outcome=engine.OriginalOutcomeReport(source.Start,source.Start,
                    evaluationStart,source.End,source.ProtocolSha256,includeTrace:false),
                GrossFromCompletedEur=trips.Sum(t=>t.GrossEur),
                CostFromCompletedEur=trips.Sum(t=>t.GrossEur-t.NetEur),
                CommissionOnCompletedEur=trips.Sum(t=>t.Integrated?.CommissionsEur??0m),
                InitialRewardRisk=trips.Select(t=>t.Integrated?.PlannedRewardToRisk).ToArray(),
                RealizedR=trips.Select(t=>t.R).ToArray(),
                Overruns=trips.Count(t=>t.NetEur< -t.EntryRiskEur),
                WithUnknownPath=trips.Count(t=>t.CrossedUnknownHistory),
                WorstLossEur=trips.Length==0?(decimal?)null:trips.Min(t=>t.NetEur),
                PartialReductions=trips.Count(t=>t.Integrated?.PartialReduction==true),
                FirstObservedBarriers=trips.GroupBy(t=>t.Integrated!.FirstObservedBarrier)
                    .ToDictionary(g=>g.Key,g=>g.Count()),
                MaxPlannedAggregateRiskEur=curve.Max(x=>x.PlannedAggregateRiskEur),
                MinimumObservedLiquidationEquityEur=curve.Min(x=>x.EquityEur),
                ByWeek=weekly, Hard21ModelWeeks=weekly.Count(w=>w.Hard21ModelOnly),
                CensoredOpenPositions=valid.OpenPositions,
                UnobservedExposureMarks=curve.Count(x=>x.Held>0 && x.EquityEur is null),
                CheckedMonetaryEventCount=events.Length, EventChain=valid.EventChainHash,
                NonMarkEvents=events.Where(x=>x.Kind!="MARK").ToArray(),
                NoRealBrokerExecution=true,ContinuousDrawdownCertified=false
            };
            Console.WriteLine($"INTEGRATED_BOOK {policy} {trips.Length} {valid.ClosedNetEur.ToString(CultureInfo.InvariantCulture)}");
            object? lifecycle=coherent?LifecycleReport(engine,trips,curve,contracts,evaluationStart):null;
            return (policy,valid.ClosedNetEur,report,lifecycle);
        }
        var evaluated=coherent
            ?policies.AsParallel().AsOrdered().WithDegreeOfParallelism(2).Select(Evaluate).ToArray()
            :policies.Select(Evaluate).ToArray();
        var totals=evaluated.ToDictionary(x=>x.Policy,x=>x.NetEur,StringComparer.Ordinal);
        var reports=evaluated.ToDictionary(x=>x.Policy,x=>x.Report,StringComparer.Ordinal);
        object comparison=coherent?totals.ToDictionary(x=>x.Key,x=>new {
            VsCashEur=x.Value-totals[NativeIntegratedLifecycle.Cash],
            VsFirstEur=x.Value-totals[x.Key.EndsWith("_ADVERSE",StringComparison.Ordinal)
                ?NativeIntegratedLifecycle.FirstAdverse:NativeIntegratedLifecycle.First],
            VsLongEur=x.Value-totals[NativeIntegratedLifecycle.Long],
            VsShortEur=x.Value-totals[NativeIntegratedLifecycle.Short],
            VsRandomEur=x.Value-totals[NativeIntegratedLifecycle.Random]
        }):totals.ToDictionary(x=>x.Key,x=>new {
            VsCashEur=x.Value-totals["INTEGRATED_CASH"],
            VsFirstMinimumEur=x.Value-totals["INTEGRATED_FIRST_MIN"],
            VsFirstBudgetEur=x.Value-totals["INTEGRATED_FIRST_BUDGET"],
            VsLongEur=x.Value-totals["INTEGRATED_LONG_MIN"],
            VsShortEur=x.Value-totals["INTEGRATED_SHORT_MIN"],
            VsRandomEur=x.Value-totals["INTEGRATED_RANDOM_MIN"]
        });
        Directory.CreateDirectory(outputDirectory);
        using var output=File.Create(Path.Combine(outputDirectory,"economic.json"));
        var coverage=markets.Select(x=>new {
            x.Source.Name,x.Source.Class,x.Source.ActiveHours,x.Source.RequestedTickHours,
            x.Source.CostTermsComplete,x.Source.Contract,x.Source.Margin,x.Source.Schedule,x.Source.ScheduleTimeZone,
            BrokerM5=x.Source.M5.Length,BrokerM15=x.Source.M15.Length,BrokerH1=x.Source.H1.Length,
            AcceptedMarks=x.AcceptedMarks,SourceMarks=x.Source.Quotes.Length,
            SuppliedHours=x.Source.Quotes.GroupBy(q=>DateTimeOffset.FromUnixTimeMilliseconds(q.At).UtcDateTime.Hour)
                .ToDictionary(g=>g.Key,g=>g.Count())
        }).ToArray();
        if(coherent)
            JsonSerializer.Serialize(output,new {
                Study="INTEGRATED_CAUSAL_LIFECYCLE_SHARED_NATIVE_CORE",source.SourceRun,source.ProtocolSha256,
                source.Start,source.End,EvaluationStart=evaluationStart,ManagementIntervalMs=spacing,
                ObservedClocks=clocks.Count(x=>x.Markets.Length>0),
                ObservedEvaluationClocks=clocks.Count(x=>x.At>=evaluationStart && x.Markets.Length>0),
                SourceCoverage=coverage,Protection=source.Markets.ToDictionary(x=>x.Name,x=>x.Protection),
                Policies=reports,Lifecycle=evaluated.ToDictionary(x=>x.Policy,x=>x.Lifecycle),
                Incremental=comparison,DistinctCommonBookCapitalEur=300,OrdersSubmitted=0,CloudActivated=false,
                FundingHistoryReconciled=false,IndependentConfirmation=false,BrokerNetCertified=false
            },Json);
        else
            JsonSerializer.Serialize(output,new {
                Study="INTEGRATED_ECONOMIC_DISCOVERY_SHARED_NATIVE_CORE",source.SourceRun,source.ProtocolSha256,
                source.Start,source.End,ObservedClocks=clocks.Count(x=>x.Markets.Length>0),
                SourceCoverage=coverage,Diagnostic=diagnostic,Policies=reports,Incremental=comparison,
                DistinctCommonBookCapitalEur=300,OrdersSubmitted=0,CloudActivated=false,
                FundingHistoryReconciled=false,IndependentConfirmation=false,BrokerNetCertified=false
            },Json);
        return 0;
    }
}

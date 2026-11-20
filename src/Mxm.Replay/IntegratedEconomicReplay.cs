using System.Globalization;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

internal static class IntegratedEconomicReplay
{
    sealed record SourceQuote(long At,long BidAt,long AskAt,decimal Bid,decimal Ask,NativeObservedQuotePath Path);
    sealed record SourceMarket(string Name,string Class,NativeObservedContractTerms Contract,
        decimal TickSize,bool ShortAllowed,int TradingMode,bool CostTermsComplete,NativeObservedVolume[] Margin,
        NativeClosedMarketBar[] M5,NativeClosedMarketBar[] M15,NativeClosedMarketBar[] H1,SourceQuote[] Quotes,
        int ActiveHours,int RequestedTickHours,int[][] Schedule,string ScheduleTimeZone);
    sealed record Source(long Start,long End,string SourceRun,string ProtocolSha256,SourceMarket[] Markets);

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
                new(h1.Observe(at),m.Margin,m.ShortAllowed,m.TickSize,q.Path));
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

    public static int Run(string inputFile,string outputDirectory)
    {
        using var stream=File.OpenRead(inputFile);
        var source=JsonSerializer.Deserialize<Source>(stream,Json)
            ??throw new ArgumentException("INTEGRATED_VERIFIED_SOURCE_MISSING");
        if(source.Start<=0 || source.End-source.Start!=21*86400000L ||
           source.ProtocolSha256.Length!=64 || source.SourceRun.Length==0 ||
           !source.SourceRun.All(char.IsAsciiDigit) ||
           source.Markets.Select(x=>x.Name).Distinct(StringComparer.Ordinal).Count()!=source.Markets.Length)
            throw new ArgumentException("INTEGRATED_FROZEN_SOURCE_SCOPE_INVALID");
        var markets=source.Markets.Select(m=>new MarketStream(m)).ToArray();
        var fx=markets.Single(m=>m.Source.Name=="EURUSD");
        var frames=new List<Ucp1Frame>();
        for(long at=source.Start+NativeIntegratedEconomicPolicy.ClockOffsetMs;at<source.End;at+=60_000)
        {
            var conversion=fx.At(at);
            var observed=conversion is null?Array.Empty<Ucp1MarketFrame>():markets
                 .Select(m=>m.Frame(at,conversion)).OfType<Ucp1MarketFrame>().ToArray();
            frames.Add(new Ucp1Frame(at,observed));
        }
        var clocks=frames.ToArray();
        var diagnostic=ReachablePath(clocks);
        var policies=NativeIntegratedEconomicPolicy.Policies
            .Concat(new[]{"INTEGRATED_FIRST_MIN_ADVERSE","INTEGRATED_STRUCTURE_BUDGET_ADVERSE"}).ToArray();
        var reports=new Dictionary<string,object>(StringComparer.Ordinal);
        var totals=new Dictionary<string,decimal>(StringComparer.Ordinal);
        var weeks=Enumerable.Range(0,3).Select(i=>Week(source.Start+i*7*86400000L)).ToArray();
        foreach(var policy in policies)
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
            totals.Add(policy,valid.ClosedNetEur);
            var weekly=weeks.Select(w=>{
                var match=trips.Where(t=>Week(t.CloseAt)==w).ToArray();
                var value=curve.LastOrDefault(x=>Week(x.At)==w && x.EquityEur is not null);
                return new { Week=w, Completed=match.Length, NetEur=match.Sum(x=>x.NetEur),
                    LastObservedEquityEur=value?.EquityEur, Hard21ModelOnly=match.Length>=21 };
            }).ToArray();
            reports.Add(policy,new {
                Outcome=engine.OriginalOutcomeReport(source.Start,source.Start,
                    source.Start+7*86400000L,source.End,source.ProtocolSha256,includeTrace:false),
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
            });
            Console.WriteLine($"INTEGRATED_BOOK {policy} {trips.Length} {valid.ClosedNetEur.ToString(CultureInfo.InvariantCulture)}");
        }
        var comparison=totals.ToDictionary(x=>x.Key,x=>new {
            VsCashEur=x.Value-totals["INTEGRATED_CASH"],
            VsFirstMinimumEur=x.Value-totals["INTEGRATED_FIRST_MIN"],
            VsFirstBudgetEur=x.Value-totals["INTEGRATED_FIRST_BUDGET"],
            VsLongEur=x.Value-totals["INTEGRATED_LONG_MIN"],
            VsShortEur=x.Value-totals["INTEGRATED_SHORT_MIN"],
            VsRandomEur=x.Value-totals["INTEGRATED_RANDOM_MIN"]
        });
        Directory.CreateDirectory(outputDirectory);
        using var output=File.Create(Path.Combine(outputDirectory,"economic.json"));
        JsonSerializer.Serialize(output,new {
            Study="INTEGRATED_ECONOMIC_DISCOVERY_SHARED_NATIVE_CORE",source.SourceRun,source.ProtocolSha256,
            source.Start,source.End,ObservedClocks=clocks.Count(x=>x.Markets.Length>0),
            SourceCoverage=markets.Select(x=>new {
                x.Source.Name,x.Source.Class,x.Source.ActiveHours,x.Source.RequestedTickHours,
                x.Source.CostTermsComplete,x.Source.Contract,x.Source.Margin,x.Source.Schedule,x.Source.ScheduleTimeZone,
                BrokerM5=x.Source.M5.Length,BrokerM15=x.Source.M15.Length,BrokerH1=x.Source.H1.Length,
                AcceptedMarks=x.AcceptedMarks,SourceMarks=x.Source.Quotes.Length,
                SuppliedHours=x.Source.Quotes.GroupBy(q=>DateTimeOffset.FromUnixTimeMilliseconds(q.At).UtcDateTime.Hour)
                    .ToDictionary(g=>g.Key,g=>g.Count())
            }).ToArray(),
            Diagnostic=diagnostic,Policies=reports,Incremental=comparison,
            DistinctCommonBookCapitalEur=300,OrdersSubmitted=0,CloudActivated=false,
            FundingHistoryReconciled=false,IndependentConfirmation=false,BrokerNetCertified=false
        },Json);
        return 0;
    }
}

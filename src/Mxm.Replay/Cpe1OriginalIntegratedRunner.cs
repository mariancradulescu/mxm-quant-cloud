using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;
using Mxm.Core;

// CPE1 genuine CLOSED M5/M15 SOURCE -> existing Core.Advance, no other
// economic engine, no fake BID/ASK history. All 2025-26 data are EXPOSED.
internal sealed record Cpe1SourceInput(V32Tape Tape,Rvc1OriginalFunding[] Funding);

internal static partial class Cpe1OriginalIntegratedRunner
{
    const long M5=300000L,M15=900000L;
    static readonly decimal[] Stress={1m,1.5m,2m};
    static readonly string[] Policies={"CPE1_ECONOMIC","CPE1_SIMPLE","CPE1_CASH"};
    static readonly JsonSerializerOptions Json=new(){
        NumberHandling=JsonNumberHandling.AllowReadingFromString,
        WriteIndented=true};
    static string Sha(string s)=>Convert.ToHexString(
        SHA256.HashData(Encoding.UTF8.GetBytes(s))).ToLowerInvariant();

    sealed class Source
    {
        public readonly V32Market Market;
        public readonly V32Bar[] M5Bars,M15Bars;
        public readonly Dictionary<long,V32Bar> OpenM5;
        readonly List<NativeClosedMarketBar> seenM5=new(),seenM15=new();
        NativeClosedMarketBar[]? closedM5,closedM15;
        public NativeClosedMarketBar[] ClosedM5=>closedM5??=seenM5.ToArray();
        public NativeClosedMarketBar[] ClosedM15=>closedM15??=seenM15.ToArray();
        int next5,next15;
        public Source(V32Market market)
        {
            Market=market;
            M5Bars=market.Bars.GetValueOrDefault("M5")?.OrderBy(x=>x.OpenAt).ToArray()
                ??Array.Empty<V32Bar>();
            M15Bars=market.Bars.GetValueOrDefault("M15")?.OrderBy(x=>x.OpenAt).ToArray()
                ??Array.Empty<V32Bar>();
            OpenM5=M5Bars.ToDictionary(x=>x.OpenAt);
        }
        static NativeClosedMarketBar Bar(V32Bar b,long width)
            =>new(b.OpenAt,b.OpenAt+width,b.Open,b.High,b.Low,b.Close,b.TickVolume);
        public void Advance(long t)
        {
            while(next5<M5Bars.Length && M5Bars[next5].OpenAt+M5<t)
            {
                seenM5.Add(Bar(M5Bars[next5++],M5));
                if(seenM5.Count>5)seenM5.RemoveAt(0);
                closedM5=null;
            }
            while(next15<M15Bars.Length && M15Bars[next15].OpenAt+M15<t)
            {
                seenM15.Add(Bar(M15Bars[next15++],M15));
                if(seenM15.Count>3)seenM15.RemoveAt(0);
                closedM15=null;
            }
        }
    }
    static NativeObservedContractTerms? Contract(V32Terms? t,
        IReadOnlyDictionary<string,Rvc1OriginalFunding> recovered)
    {
        if(t?.QuoteAsset!="USD" || t.MinimumUnits is not >0m ||
           t.StepUnits is not >0m || t.MaximumUnits is not >0m ||
           t.LotUnits is not >0m || t.CommissionType is null ||
           t.PreciseRateWire is null || t.MinimumCommissionType is null ||
           t.PreciseMinimumWire is null || t.PnlConversionFeeBps is null ||
           t.SpreadBps is not >0m || t.MarginMinimumEur is not >0m)
            return null;
        recovered.TryGetValue(t.Symbol,out var terms);
        bool original=terms?.OriginalBrokerAuthenticated==true &&
            terms.ObservedAtUtcMs==t.ObservedAtUtcMs;
        return new NativeObservedContractTerms(t.Symbol,t.QuoteAsset,
            t.ObservedAtUtcMs,t.MinimumUnits.Value,t.StepUnits.Value,
            t.MaximumUnits.Value,t.LotUnits.Value,t.CommissionType.Value,
            t.PreciseRateWire.Value,t.MinimumCommissionType.Value,
            t.PreciseMinimumWire.Value,t.MinimumCommissionAsset,
            t.PnlConversionFeeBps.Value,t.SwapCalculationType,
            t.LongSwap,t.ShortSwap,t.PipPosition,t.SwapPeriodHours,
            t.SwapTimeUtcMinute,t.TripleSwapWeekday,
            original?terms!.ChargeSwapAtWeekends:null,
            original?terms!.SkipSwapPeriods:null,
            true,false);
    }
    static LedgerQuote? ModeledQuote(V32Bar bar,V32Terms source,
        NativeObservedContractTerms contract,V32Bar fx,decimal multiplier,
        out decimal slippage)
    {
        slippage=0m;
        if(bar.Open<=0m || fx.Open<=0m || source.SpreadBps is not >0m ||
           source.MarginMinimumEur is not >0m)return null;
        // Conditional current-tariff/spread model, NOT historical broker bid/ask.
        decimal spread=bar.Open*source.SpreadBps.Value*multiplier/10000m;
        slippage=spread/2m;
        decimal bid=bar.Open-spread/2m,ask=bar.Open+spread/2m;
        decimal wedge=.00025m*multiplier,fxmid=1m/fx.Open;
        if(bid<=0m||fxmid<=0m||wedge>=1m)return null;
        try
        {
            decimal? assetFx=contract.MinimumCommissionAsset switch{
                null=>null,"USD"=>fxmid,"EUR"=>1m,_=>null};
            var c=NativeBrokerContractCosts.Quote(contract,
                new NativeMarketCostContext(bar.OpenAt,bid,ask,
                    fxmid*(1m-wedge),fxmid*(1m+wedge),fxmid,
                    assetFx,source.MarginMinimumEur.Value,
                    contract.MinimumUnits,slippage));
            return c.Quote with {
                ExitFeePerUnit=c.Quote.ExitFeePerUnit*multiplier,
                ExitFeeFloor=c.Quote.ExitFeeFloor*multiplier,
                LiquidationSlippagePerSide=slippage
            };
        }
        catch(ArgumentException){return null;}
        catch(InvalidOperationException){return null;}
    }

    static Ucp1Frame SourceFrame(long at, V32Bar conversion, decimal multiplier,
        KeyValuePair<string,(Source Source,NativeObservedContractTerms Contract)>[] orderedContracts,
        Dictionary<string,int> unknownQuotes)
    {
        var frames=new List<Ucp1MarketFrame>();
        foreach(var (symbol, (source, contract)) in orderedContracts)
        {
            if(!source.OpenM5.TryGetValue(at,out var bar))continue;
            var quote=ModeledQuote(bar,source.Market.Terms!,contract,
                conversion,multiplier,out var slip);
            if(quote is null)
            {
                unknownQuotes[symbol]=unknownQuotes.GetValueOrDefault(symbol)+1;
                continue;
            }
            frames.Add(new Ucp1MarketFrame(symbol,quote,contract,
                source.ClosedM5,source.ClosedM15,slip,
                "GENUINE_CLOSED_BARS_CONDITIONAL_CURRENT_CONTRACT_M5_OPEN"));
        }
        return new Ucp1Frame(at,frames.ToArray());
    }

    public static int Run(string sourceFile,string outputFile,string frozenSha,
        Cpe1ReplayProgress? progress=null)
    {
        progress?.Report("READ_NATIVE_INPUT");
        if(frozenSha.Length!=64)throw new ArgumentException("CPE1_PROTOCOL_HASH");
        var payload=JsonSerializer.Deserialize<Cpe1SourceInput>(
            File.ReadAllText(sourceFile),Json)
            ??throw new ArgumentException("CPE1_AUTHENTIC_SOURCE_NOT_DESERIALIZED");
        if(payload.Tape.DevelopmentOnly!=true ||
           payload.Tape.SourceRuns.Length!=5 ||
           payload.Tape.Markets.Length<2)
            throw new ArgumentException("CPE1_AUTHENTIC_GLOBALLY_EXPOSED_SCOPE");
        var recovered=payload.Funding.ToDictionary(x=>x.Symbol,StringComparer.Ordinal);
        var sources=payload.Tape.Markets.Select(x=>new Source(x))
            .ToDictionary(x=>x.Market.Symbol,StringComparer.Ordinal);
        if(!sources.ContainsKey("EURUSD")||!sources.ContainsKey("GBPUSD"))
            throw new ArgumentException("CPE1_FX_SOURCE_IDENTITY");
        var contracts=sources.Values.Select(x=>new {
            Source=x,Contract=Contract(x.Market.Terms,recovered)})
            .Where(x=>x.Contract is not null)
            .ToDictionary(x=>x.Source.Market.Symbol,
                x=>(x.Source,x.Contract!),StringComparer.Ordinal);
        if(!contracts.ContainsKey("EURUSD")||!contracts.ContainsKey("GBPUSD"))
            throw new ArgumentException("CPE1_AUTHENTIC_BASE_FX_UNPRICED");
        var times=sources.Values.SelectMany(x=>x.M5Bars.Select(b=>b.OpenAt))
            .Distinct().OrderBy(x=>x).ToArray();
        if(times.Length<500)throw new ArgumentException("CPE1_SOURCE_TIMESTAMPS_INSUFFICIENT");
        var groups=Stress.Select(stress=>Policies.Select(policy=>
            new {Stress=stress,Policy=policy,
                Engine=new NativeUnifiedPortfolioEngine(policy)})
            .ToArray()).ToArray();
        var books=groups.SelectMany(x=>x).ToArray();
        var orderedContracts=contracts.OrderBy(x=>x.Key,StringComparer.Ordinal).ToArray();
        var unknownQuotes=new Dictionary<string,int>(StringComparer.Ordinal);
        var first=times[0];var last=times[^1];
        progress?.Report("ADVANCE_SOURCE_CLOCKS",0,times.Length,force:true);
        for(int i=0;i<times.Length;i++)
        {
            long t=times[i];
            foreach(var source in sources.Values)source.Advance(t);
            if(!sources["EURUSD"].OpenM5.TryGetValue(t,out var conversion))
            {
                var emptyFrame=new Ucp1Frame(t,Array.Empty<Ucp1MarketFrame>());
                foreach(var book in books)book.Engine.Advance(emptyFrame);
            }
            else foreach(var group in groups)
            {
                var frame=SourceFrame(t,conversion,group[0].Stress,orderedContracts,unknownQuotes);
                foreach(var book in group)book.Engine.Advance(frame);
            }
            progress?.Report("ADVANCE_SOURCE_CLOCKS",i+1,times.Length,force:i==0);
        }
        string Week(long t)
        {
            var d=DateTimeOffset.FromUnixTimeMilliseconds(t).UtcDateTime;
            return ISOWeek.GetYear(d)+"-W"+ISOWeek.GetWeekOfYear(d).ToString("00",CultureInfo.InvariantCulture);
        }
        var weeks=new HashSet<string>(StringComparer.Ordinal);
        for(var day=DateTimeOffset.FromUnixTimeMilliseconds(first).UtcDateTime.Date;
            day<=DateTimeOffset.FromUnixTimeMilliseconds(last).UtcDateTime.Date;
            day=day.AddDays(1))
            weeks.Add(Week(new DateTimeOffset(day,TimeSpan.Zero).ToUnixTimeMilliseconds()));
        var reports=books.Select((x,index)=>{
            int book=index+1;
            var trips=x.Engine.CompleteModelTrips;
            var summary=x.Engine.ModelSummary;
            bool financeKnown=trips.All(p=>p.EconomicEvidence?.ConditionalNetKnown==true);
            bool flat=summary.OpenPositions==0&&summary.PendingIntents==0;
            var gross=trips.Sum(p=>p.GrossEur);
            var nominalNet=trips.Sum(p=>p.NetEur);
            // Per-episode claims REQUIRE original contract financing to have
            // been authenticated and every roll accounted. Censored positions
            // are NOT silently marked at a future hypothetical exit.
            bool completeConditionalModelBook=flat&&financeKnown &&
                !summary.HistoryEvidenceIncomplete&&
                summary.LiquidationEquityEur is not null;
            // Identical original Core events, replayed through the EXISTING
            // native funded ledger; never a competing capital-account model.
            var reconciled=new NativeFundedLedger();
            var events=x.Engine.OriginalModelEvents;
            progress?.Report("RECONCILE_BOOK_EVENTS",0,events.Length,book,force:true);
            for(int i=0;i<events.Length;i++)
            {
                reconciled.Apply(events[i]);
                progress?.Report("RECONCILE_BOOK_EVENTS",i+1,events.Length,book);
            }
            var verify=reconciled.Summary();
            if(verify.CashEur!=summary.CashEur ||
               verify.EventChainHash!=summary.EventChainHash ||
               verify.OpenPositions!=summary.OpenPositions ||
               verify.PendingIntents!=summary.PendingIntents ||
               verify.CompleteRoundTrips!=summary.CompleteRoundTrips)
                throw new InvalidOperationException("CPE1_ORIGINAL_NATIVE_EVENT_CHAIN_EUR300_RECONCILIATION");
            progress?.Report("SCORE_AND_REPORT_BOOK",0,1,book,force:true);
            var curve=x.Engine.CommonBookEquityPath;
            // The shared scorecard explicitly rejects negative free margin.
            // Preserve such an observed funding breach as UNKNOWN scorecard,
            // rather than silently clamp free capital to zero.
            bool validScorecardMarks=!curve.Any(p=>p.EquityEur is decimal eq &&
                p.UsedMarginEur is decimal margin && eq-margin<0m);
            var score=validScorecardMarks?NativePerformanceScorecard.Calculate(
                new NativeEconomicScorecardInput(
                    x.Policy,
                    reconciled.ClosedFragments(),
                    curve.Select(p=>new NativeEconomicMark(p.At,p.EquityEur,
                        p.UsedMarginEur,p.EquityEur-p.UsedMarginEur,p.Held,
                        p.EquityEur is not null&&p.UsedMarginEur is not null)).ToArray(),
                    trips.Where(p=>p.EconomicEntry is {ReservedRiskEur:>0m})
                        .Select(p=>new NativeEntryRisk(p.PositionId,
                            p.EconomicEntry!.ReservedRiskEur,
                            p.EconomicEntry.DecisionAt,
                            frozenSha)).ToArray(),
                    weeks.ToArray(),300m,
                    completeConditionalModelBook?(decimal?)nominalNet:null,
                    0m,completeConditionalModelBook,false,false)):null;
            var report=x.Engine.OriginalOutcomeReport(first,first+(last-first)/3,
                first+2*(last-first)/3,last,Sha(payload.Tape.ProtocolSha256),false);
            var completedByWeek=trips.GroupBy(p=>Week(p.CloseAt))
                .ToDictionary(g=>g.Key,g=>g.Count(),StringComparer.Ordinal);
            var bookReport=new {
                x.Policy,x.Stress,
                SourceWeeks=weeks.Count,
                ConditionalClosedGrossEur=gross,
                ConditionalClosedNetBeforeUnknownFinancingEur=nominalNet,
                ClosedConditionalModelNetEurWhenFundingFieldsAvailable=financeKnown?
                    (decimal?)nominalNet:null,
                FullyClosedReconciledConditionalModelNetEur=completeConditionalModelBook?
                    (decimal?)nominalNet:null,
                HistoricalBrokerNetCertified=false,
                Completed=trips.Length,
                GrossWinnerCount=trips.Count(p=>p.GrossEur>0m),
                ClosedUnknownFinancing=trips.Count(p=>p.EconomicEvidence?.ConditionalNetKnown!=true),
                ProjectedRewardRiskMissing=trips.Count(p=>p.EconomicEvidence is null),
                CompletedByWeek=weeks.OrderBy(w=>w,StringComparer.Ordinal)
                    .ToDictionary(w=>w,w=>completedByWeek.GetValueOrDefault(w)),
                AllEligibleWeeksHARD21=weeks.Count>0&&weeks.All(w=>
                    completedByWeek.GetValueOrDefault(w)>=21),
                CashEur=summary.CashEur,EquityEur=summary.LiquidationEquityEur,
                SampledDd=summary.MaximumSampledDrawdown,
                Held=summary.OpenPositions,Pending=summary.PendingIntents,
                summary.HistoryEvidenceIncomplete,summary.EventChainHash,
                IndependentFundedLedgerEventChainReconciled=true,
                NativeEconomicScorecard=score,
                NativeScorecardUnqualifiedNegativeFreeMargin=!validScorecardMarks,
                UnreconciledHistoricalFinancing=x.Engine.Cpe1UnreconciledFunding,
                GrossMeanPerCompleted=trips.Length>0?(decimal?)gross/trips.Length:null,
                MeanGrossR=trips.Any(p=>p.EconomicEvidence?.RealizedGrossR is not null)?
                    (decimal?)trips.Where(p=>p.EconomicEvidence?.RealizedGrossR is not null)
                        .Average(p=>p.EconomicEvidence!.RealizedGrossR!.Value):null,
                EntryReasons=trips.GroupBy(p=>p.Family)
                    .ToDictionary(g=>g.Key,g=>g.Count()),
                ExitReasons=trips.GroupBy(p=>p.ExitReason)
                    .ToDictionary(g=>g.Key,g=>g.Count()),
                IndividualEpisodes=trips,
                PartialReductionAvailability=x.Policy=="CPE1_CASH"?"NOT_APPLICABLE":
                    "NOT_LEGAL_AT_FROZEN_MINIMUM_ENTRY_UNITS",
                ConditionalFullEngineReportNetIncludesUnverifiedFunding=!financeKnown,
                ConditionalFullEngineReport=report
            };
            progress?.Report("SCORE_AND_REPORT_BOOK",1,1,book);
            return bookReport;
        }).ToArray();
        var receipt=new {
            Study="CPE1_ONE_IN_EXISTING_NATIVE_UCP1_COMPLETE_CYCLE",
            FrozenProtocolSha256=frozenSha,OriginalSourceRuns=payload.Tape.SourceRuns,
            SourceAllPreviouslyExposed=true,IndependentEvaluation=false,
            GenuineM5SourceClocks=times.Length,WeeksIncludingNoTrade=weeks.Count,
            OfficialFundingRecovered=recovered.Values.Where(x=>
                x.OriginalBrokerAuthenticated&&x.ChargeSwapAtWeekends is not null&&
                x.SkipSwapPeriods is not null).Select(x=>x.Symbol).OrderBy(x=>x).ToArray(),
            UnknownCurrentCostQuotes=unknownQuotes,
            BookSummaries=reports,OrderRequests=0,CloudActivated=false,
            HistoricalExactBrokerFillsCertified=false,
            HistoricalCostContinuityCertified=false,IntrabarDdCertified=false,
            TradingQualification="DEVELOPMENT_EXPOSED_ONLY_NO_BROKER_CERTIFICATION"
        };
        progress?.Report("WRITE_NATIVE_RECEIPT",0,1,force:true);
        File.WriteAllText(outputFile,JsonSerializer.Serialize(receipt,Json)+"\n");
        progress?.Report("WRITE_NATIVE_RECEIPT",1,1);
        return 0;
    }
}
